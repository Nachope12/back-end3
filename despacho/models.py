import base64
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.utils import timezone

from core.exceptions import ErrorDeNegocio
from pedidos.models import Estado as EstadoPedido
from pedidos.models import Pedido

MAX_FIRMA_BYTES = 1_000_000


class Ruta(models.Model):
    class Estado(models.TextChoices):
        PLANIFICADA = "PLANIFICADA", "Planificada"
        EN_CURSO = "EN_CURSO", "En curso"
        COMPLETADA = "COMPLETADA", "Completada"

    nombre = models.CharField("nombre", max_length=120)
    fecha = models.DateField("fecha de despacho")
    repartidor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="rutas", verbose_name="repartidor")
    estado = models.CharField("estado", max_length=12, choices=Estado.choices, default=Estado.PLANIFICADA)
    creado_en = models.DateTimeField("creada el", auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "nombre"]
        verbose_name = "ruta de despacho"
        verbose_name_plural = "rutas de despacho"

    def __str__(self):
        return f"{self.nombre} ({self.fecha:%d/%m/%Y})"

    @property
    def es_editable(self):
        return self.estado != self.Estado.COMPLETADA

    def iniciar(self):
        if self.estado != self.Estado.PLANIFICADA:
            raise ErrorDeNegocio("Solo se pueden iniciar rutas planificadas.")
        if not self.entregas.exists():
            raise ErrorDeNegocio("La ruta no tiene entregas asignadas.")
        self.estado = self.Estado.EN_CURSO
        self.save(update_fields=["estado"])

    def actualizar_estado(self):
        """La ruta se completa cuando ya no quedan entregas pendientes."""
        if self.estado == self.Estado.EN_CURSO and not self.entregas.filter(estado=Entrega.Estado.PENDIENTE).exists():
            self.estado = self.Estado.COMPLETADA
            self.save(update_fields=["estado"])

    @property
    def resumen(self):
        total = self.entregas.count()
        hechas = self.entregas.filter(estado=Entrega.Estado.ENTREGADA).count()
        return f"{hechas}/{total} entregadas"


class Entrega(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ENTREGADA = "ENTREGADA", "Entregada"
        FALLIDA = "FALLIDA", "Fallida"

    ruta = models.ForeignKey(Ruta, on_delete=models.CASCADE, related_name="entregas")
    pedido = models.ForeignKey(Pedido, on_delete=models.PROTECT, related_name="entregas")
    orden = models.PositiveIntegerField("orden en la ruta", default=1)
    estado = models.CharField("estado", max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    receptor_nombre = models.CharField("recibió", max_length=150, blank=True)
    firma = models.ImageField("firma digital", upload_to="firmas/%Y/%m/", blank=True)
    foto = models.ImageField("comprobante fotográfico", upload_to="comprobantes/%Y/%m/", blank=True)
    observaciones = models.CharField("observaciones", max_length=255, blank=True)
    entregada_en = models.DateTimeField("fecha de entrega", null=True, blank=True)

    class Meta:
        ordering = ["ruta", "orden"]
        verbose_name = "entrega"
        verbose_name_plural = "entregas"

    def __str__(self):
        return f"Entrega de {self.pedido} en {self.ruta}"

    def clean(self):
        if self._state.adding and self.pedido_id:
            if self.pedido.estado != EstadoPedido.LISTO:
                raise ValidationError("Solo se pueden despachar pedidos en estado «Listo».")
            if Entrega.objects.filter(pedido=self.pedido).exclude(estado=self.Estado.FALLIDA).exists():
                raise ValidationError("Este pedido ya está asignado a una ruta.")

    @transaction.atomic
    def confirmar(self, receptor, firma_dataurl="", foto=None, usuario=None):
        """Confirma la entrega con firma digital (canvas) y/o comprobante fotográfico."""
        if self.estado != self.Estado.PENDIENTE:
            raise ErrorDeNegocio("Esta entrega ya fue resuelta.")
        if not (firma_dataurl or foto):
            raise ErrorDeNegocio("Debes adjuntar la firma del receptor o una foto del comprobante.")
        if not receptor.strip():
            raise ErrorDeNegocio("Indica quién recibió el pedido.")
        if firma_dataurl:
            prefijo = "data:image/png;base64,"
            if not firma_dataurl.startswith(prefijo):
                raise ErrorDeNegocio("La firma no tiene un formato válido.")
            try:
                datos = base64.b64decode(firma_dataurl[len(prefijo):], validate=True)
            except Exception:
                raise ErrorDeNegocio("La firma no tiene un formato válido.")
            if len(datos) > MAX_FIRMA_BYTES:
                raise ErrorDeNegocio("La firma es demasiado grande.")
            self.firma.save(f"firma-{self.pedido_id}-{uuid.uuid4().hex[:8]}.png", ContentFile(datos), save=False)
        if foto:
            self.foto = foto
        self.receptor_nombre = receptor.strip()
        self.estado = self.Estado.ENTREGADA
        self.entregada_en = timezone.now()
        self.save()
        self.pedido.cambiar_estado(EstadoPedido.ENTREGADO, usuario)
        if self.ruta.estado == Ruta.Estado.PLANIFICADA:
            self.ruta.estado = Ruta.Estado.EN_CURSO
            self.ruta.save(update_fields=["estado"])
        self.ruta.actualizar_estado()

    @transaction.atomic
    def marcar_fallida(self, motivo):
        if self.estado != self.Estado.PENDIENTE:
            raise ErrorDeNegocio("Esta entrega ya fue resuelta.")
        if not motivo.strip():
            raise ErrorDeNegocio("Indica el motivo de la entrega fallida.")
        self.estado = self.Estado.FALLIDA
        self.observaciones = motivo.strip()
        self.save(update_fields=["estado", "observaciones"])
        self.ruta.actualizar_estado()
