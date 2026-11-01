from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from core.exceptions import ErrorDeNegocio, StockInsuficiente, TransicionInvalida, mensaje_error
from core.validators import validar_anticipacion
from django.core.exceptions import ValidationError
from inventario.models import Insumo, MovimientoInventario
from inventario.services import registrar_movimiento

HORAS_URGENTE = 6


class Estado(models.TextChoices):
    RECIBIDO = "RECIBIDO", "Recibido"
    EN_PREPARACION = "EN_PREPARACION", "En preparación"
    HORNEADO_DECORADO = "HORNEADO_DECORADO", "Horneado / Decorado"
    CONTROL_CALIDAD = "CONTROL_CALIDAD", "Control de calidad"
    LISTO = "LISTO", "Listo"
    ENTREGADO = "ENTREGADO", "Entregado"
    CANCELADO = "CANCELADO", "Cancelado"


# Columnas del tablero Kanban de cocina
COLUMNAS_KANBAN = [(e.value, e.label) for e in (
    Estado.RECIBIDO, Estado.EN_PREPARACION, Estado.HORNEADO_DECORADO, Estado.CONTROL_CALIDAD, Estado.LISTO)]

# Flujo permitido: avanza paso a paso; control de calidad puede devolver a horneado/decorado
TRANSICIONES = {
    Estado.RECIBIDO: (Estado.EN_PREPARACION, Estado.CANCELADO),
    Estado.EN_PREPARACION: (Estado.HORNEADO_DECORADO,),
    Estado.HORNEADO_DECORADO: (Estado.CONTROL_CALIDAD,),
    Estado.CONTROL_CALIDAD: (Estado.LISTO, Estado.HORNEADO_DECORADO),
    Estado.LISTO: (Estado.ENTREGADO,),
}
AVANCE = {
    Estado.RECIBIDO: Estado.EN_PREPARACION,
    Estado.EN_PREPARACION: Estado.HORNEADO_DECORADO,
    Estado.HORNEADO_DECORADO: Estado.CONTROL_CALIDAD,
    Estado.CONTROL_CALIDAD: Estado.LISTO,
}


def calcular_requerimiento(lineas):
    """lineas: iterable de (producto, cantidad). Devuelve lista de dicts con necesario/stock/falta por insumo."""
    necesidad = {}
    for producto, cantidad in lineas:
        for item in producto.bom.all():
            necesidad[item.insumo] = necesidad.get(item.insumo, Decimal("0")) + item.cantidad * cantidad
    filas = []
    for insumo, necesario in sorted(necesidad.items(), key=lambda kv: kv[0].nombre):
        falta = max(necesario - insumo.stock, Decimal("0"))
        filas.append({"insumo": insumo, "necesario": necesario, "stock": insumo.stock, "falta": falta})
    return filas


class Cotizacion(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"

    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.PROTECT, related_name="cotizaciones")
    diseno = models.TextField("diseño / descripción", help_text="Sabores, decoración, mensaje, referencias.")
    fecha_entrega = models.DateTimeField("fecha y hora de entrega")
    estado = models.CharField("estado", max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    total = models.DecimalField("total", max_digits=12, decimal_places=2, default=0)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="cotizaciones")
    creado_en = models.DateTimeField("creada el", auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "cotización"
        verbose_name_plural = "cotizaciones"

    def __str__(self):
        return f"Cotización #{self.pk} · {self.cliente}"

    def clean(self):
        if self._state.adding and self.fecha_entrega:
            validar_anticipacion(self.fecha_entrega)

    @property
    def es_editable(self):
        return self.estado == self.Estado.PENDIENTE

    def recalcular_total(self):
        total = sum((i.subtotal for i in self.items.all()), Decimal("0"))
        self.total = total
        Cotizacion.objects.filter(pk=self.pk).update(total=total)

    def requerimiento(self):
        return calcular_requerimiento((i.producto, i.cantidad) for i in
                                      self.items.select_related("producto").prefetch_related("producto__bom__insumo"))

    @transaction.atomic
    def aprobar(self, usuario=None):
        """Convierte la cotización en un pedido (estado Recibido)."""
        if self.estado != self.Estado.PENDIENTE:
            raise ErrorDeNegocio("Solo se pueden aprobar cotizaciones pendientes.")
        items = list(self.items.select_related("producto"))
        if not items:
            raise ErrorDeNegocio("La cotización no tiene productos.")
        try:
            validar_anticipacion(self.fecha_entrega)
        except ValidationError as e:
            raise ErrorDeNegocio(mensaje_error(e) + " Edita la fecha de entrega antes de aprobar.")
        pedido = Pedido.objects.create(
            cliente=self.cliente, cotizacion=self, diseno=self.diseno, fecha_entrega=self.fecha_entrega,
            direccion_entrega=self.cliente.direccion, creado_por=usuario,
        )
        for i in items:
            DetallePedido.objects.create(pedido=pedido, producto=i.producto, cantidad=i.cantidad,
                                         precio_unitario=i.precio_unitario)
        pedido.recalcular_total()
        self.estado = self.Estado.APROBADA
        self.save(update_fields=["estado"])
        return pedido

    def rechazar(self):
        if self.estado != self.Estado.PENDIENTE:
            raise ErrorDeNegocio("Solo se pueden rechazar cotizaciones pendientes.")
        self.estado = self.Estado.RECHAZADA
        self.save(update_fields=["estado"])


class CotizacionItem(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey("inventario.Producto", on_delete=models.PROTECT, related_name="+")
    cantidad = models.PositiveIntegerField("cantidad", default=1, validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField("precio unitario", max_digits=12, decimal_places=2, null=True,
                                          blank=True, validators=[MinValueValidator(0)],
                                          help_text="Vacío = precio sugerido del producto.")

    class Meta:
        verbose_name = "ítem de cotización"
        verbose_name_plural = "ítems de cotización"

    def save(self, *args, **kwargs):
        if self.precio_unitario is None:
            self.precio_unitario = self.producto.precio_sugerido()
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return (self.precio_unitario or 0) * self.cantidad

    def __str__(self):
        return f"{self.cantidad} × {self.producto}"


class Pedido(models.Model):
    cliente = models.ForeignKey("clientes.Cliente", on_delete=models.PROTECT, related_name="pedidos")
    cotizacion = models.OneToOneField(Cotizacion, null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name="pedido")
    diseno = models.TextField("diseño / descripción")
    notas = models.TextField("notas internas", blank=True)
    fecha_entrega = models.DateTimeField("fecha y hora de entrega")
    direccion_entrega = models.CharField("dirección de entrega", max_length=255, blank=True)
    estado = models.CharField("estado", max_length=20, choices=Estado.choices, default=Estado.RECIBIDO)
    total = models.DecimalField("total", max_digits=12, decimal_places=2, default=0)
    insumos_descontados = models.BooleanField("insumos descontados", default=False)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="pedidos_creados")
    creado_en = models.DateTimeField("creado el", auto_now_add=True)
    actualizado_en = models.DateTimeField("actualizado el", auto_now=True)

    class Meta:
        ordering = ["fecha_entrega"]
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"

    def __str__(self):
        return f"Pedido #{self.pk} · {self.cliente}"

    def clean(self):
        if self._state.adding and self.fecha_entrega:
            validar_anticipacion(self.fecha_entrega)

    def save(self, *args, **kwargs):
        nuevo = self._state.adding
        if not self.direccion_entrega and self.cliente_id:
            self.direccion_entrega = self.cliente.direccion
        super().save(*args, **kwargs)
        if nuevo:
            HistorialEstado.objects.create(pedido=self, de="", a=self.estado, usuario=self.creado_por)

    # ---- consultas útiles ----
    @property
    def es_editable(self):
        return self.estado == Estado.RECIBIDO

    @property
    def urgente(self):
        if self.estado in (Estado.LISTO, Estado.ENTREGADO, Estado.CANCELADO):
            return False
        return self.fecha_entrega <= timezone.now() + timedelta(hours=HORAS_URGENTE)

    @property
    def siguiente_estado(self):
        return AVANCE.get(self.estado)

    @property
    def siguiente_etiqueta(self):
        sig = AVANCE.get(self.estado)
        return Estado(sig).label if sig else ""

    @property
    def resumen_productos(self):
        return ", ".join(f"{d.cantidad}× {d.producto.nombre}" for d in self.detalles.all())

    def recalcular_total(self):
        total = sum((d.subtotal for d in self.detalles.all()), Decimal("0"))
        self.total = total
        Pedido.objects.filter(pk=self.pk).update(total=total)

    def requerimiento(self):
        return calcular_requerimiento((d.producto, d.cantidad) for d in
                                      self.detalles.select_related("producto").prefetch_related("producto__bom__insumo"))

    # ---- lógica de negocio ----
    @transaction.atomic
    def descontar_insumos(self, usuario=None):
        """Descuenta del inventario los insumos del BOM de cada producto. Todo o nada."""
        if self.insumos_descontados:
            return
        necesidad = {fila["insumo"].pk: fila["necesario"] for fila in self.requerimiento()}
        bloqueados = list(Insumo.objects.select_for_update().filter(pk__in=necesidad.keys()).order_by("pk"))
        faltantes = [
            f"{i.nombre}: faltan {necesidad[i.pk] - i.stock:.2f} {i.unidad}"
            for i in bloqueados if i.stock < necesidad[i.pk]
        ]
        if faltantes:
            raise StockInsuficiente(faltantes)
        for insumo in bloqueados:
            registrar_movimiento(insumo, MovimientoInventario.Tipo.CONSUMO, necesidad[insumo.pk],
                                 usuario=usuario, pedido=self, nota=f"Pedido #{self.pk}")
        self.insumos_descontados = True
        self.save(update_fields=["insumos_descontados"])

    @transaction.atomic
    def cambiar_estado(self, nuevo, usuario=None):
        """Mueve el pedido en el flujo Kanban validando la transición."""
        actual = Pedido.objects.select_for_update().get(pk=self.pk)  # evita doble clic / carreras
        self.estado = actual.estado
        self.insumos_descontados = actual.insumos_descontados
        permitidos = TRANSICIONES.get(self.estado, ())
        if nuevo not in permitidos:
            raise TransicionInvalida(
                f"No se puede pasar de «{Estado(self.estado).label}» a «{Estado(nuevo).label}»."
            )
        if self.estado == Estado.RECIBIDO and nuevo == Estado.EN_PREPARACION:
            if not self.detalles.exists():
                raise ErrorDeNegocio("El pedido no tiene productos.")
            self.descontar_insumos(usuario)
        anterior = self.estado
        self.estado = nuevo
        self.save(update_fields=["estado", "actualizado_en"])
        HistorialEstado.objects.create(pedido=self, de=anterior, a=nuevo, usuario=usuario)

    def cancelar(self, usuario=None):
        self.cambiar_estado(Estado.CANCELADO, usuario)


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey("inventario.Producto", on_delete=models.PROTECT, related_name="+")
    cantidad = models.PositiveIntegerField("cantidad", default=1, validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField("precio unitario", max_digits=12, decimal_places=2, null=True,
                                          blank=True, validators=[MinValueValidator(0)],
                                          help_text="Vacío = precio sugerido del producto.")

    class Meta:
        verbose_name = "detalle del pedido"
        verbose_name_plural = "detalles del pedido"

    def save(self, *args, **kwargs):
        if self.precio_unitario is None:
            self.precio_unitario = self.producto.precio_sugerido()
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return (self.precio_unitario or 0) * self.cantidad

    def __str__(self):
        return f"{self.cantidad} × {self.producto}"


class HistorialEstado(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="historial")
    de = models.CharField("desde", max_length=20, blank=True)
    a = models.CharField("hasta", max_length=20)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    fecha = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        ordering = ["fecha", "id"]
        verbose_name = "historial de estado"
        verbose_name_plural = "historial de estados"

    def __str__(self):
        return f"{self.pedido} {self.de or '—'} → {self.a}"

    @property
    def de_display(self):
        return Estado(self.de).label if self.de else "—"

    @property
    def a_display(self):
        return Estado(self.a).label
