from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Insumo(models.Model):
    class Unidad(models.TextChoices):
        GRAMO = "g", "gramos"
        MILILITRO = "ml", "mililitros"
        UNIDAD = "un", "unidades"

    nombre = models.CharField("nombre", max_length=120, unique=True)
    unidad = models.CharField("unidad", max_length=2, choices=Unidad.choices, default=Unidad.GRAMO)
    stock = models.DecimalField("stock actual", max_digits=12, decimal_places=2, default=0,
                                validators=[MinValueValidator(0)])
    stock_minimo = models.DecimalField("stock mínimo", max_digits=12, decimal_places=2, default=0,
                                       validators=[MinValueValidator(0)])
    costo_unitario = models.DecimalField("costo por unidad", max_digits=12, decimal_places=4, default=0,
                                         validators=[MinValueValidator(0)],
                                         help_text="Costo en pesos por cada gramo, mililitro o unidad.")
    perecible = models.BooleanField("perecible", default=False)
    fecha_vencimiento = models.DateField("vence el", null=True, blank=True)
    proveedor = models.CharField("proveedor", max_length=120, blank=True)
    activo = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "insumo"
        verbose_name_plural = "insumos"

    def __str__(self):
        return f"{self.nombre} ({self.get_unidad_display()})"

    @property
    def bajo_minimo(self):
        return self.stock <= self.stock_minimo

    @property
    def por_vencer(self):
        if not self.fecha_vencimiento:
            return False
        return self.fecha_vencimiento <= timezone.localdate() + timedelta(days=settings.DIAS_ALERTA_VENCIMIENTO)

    @property
    def estado_stock(self):
        if self.fecha_vencimiento and self.fecha_vencimiento < timezone.localdate():
            return "VENCIDO"
        if self.bajo_minimo:
            return "BAJO"
        if self.por_vencer:
            return "POR_VENCER"
        return "OK"

    @property
    def estado_stock_display(self):
        return {"VENCIDO": "Vencido", "BAJO": "Bajo el mínimo", "POR_VENCER": "Por vencer", "OK": "En orden"}[
            self.estado_stock]


class Producto(models.Model):
    """Producto de pastelería. Su Lista de Materiales (BOM) define los insumos que consume."""

    nombre = models.CharField("nombre", max_length=150, unique=True)
    descripcion = models.TextField("descripción", blank=True)
    porciones = models.PositiveIntegerField("porciones", default=1)
    tiempo_preparacion_min = models.PositiveIntegerField("tiempo de preparación (min)", default=60)
    mano_obra = models.DecimalField("mano de obra", max_digits=12, decimal_places=2, default=0,
                                    validators=[MinValueValidator(0)])
    margen_pct = models.DecimalField("margen (%)", max_digits=5, decimal_places=2, default=30,
                                     validators=[MinValueValidator(0)])
    activo = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "producto"
        verbose_name_plural = "productos"

    def __str__(self):
        return self.nombre

    def costo_insumos(self):
        total = Decimal("0")
        for item in self.bom.all():
            total += item.cantidad * item.insumo.costo_unitario
        return total

    def precio_sugerido(self):
        base = self.costo_insumos() + Decimal(str(self.mano_obra))
        factor = 1 + Decimal(str(self.margen_pct)) / 100
        return (base * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


class ItemBOM(models.Model):
    """Línea de la Lista de Materiales: cuánto insumo se usa por cada unidad de producto."""

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="bom")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="usos_bom")
    cantidad = models.DecimalField("cantidad por unidad", max_digits=12, decimal_places=2,
                                   validators=[MinValueValidator(Decimal("0.01"))])

    class Meta:
        verbose_name = "ítem de la lista de materiales"
        verbose_name_plural = "lista de materiales (BOM)"
        constraints = [models.UniqueConstraint(fields=["producto", "insumo"], name="bom_unico_por_insumo")]

    def __str__(self):
        return f"{self.producto}: {self.cantidad} {self.insumo.unidad} de {self.insumo.nombre}"


class MovimientoInventario(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada (compra)"
        CONSUMO = "CONSUMO", "Consumo por pedido"
        MERMA = "MERMA", "Merma / pérdida"
        AJUSTE = "AJUSTE", "Ajuste de inventario"
        DEVOLUCION = "DEVOLUCION", "Devolución"

    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices)
    delta = models.DecimalField("variación", max_digits=12, decimal_places=2)
    stock_resultante = models.DecimalField("stock resultante", max_digits=12, decimal_places=2)
    pedido = models.ForeignKey("pedidos.Pedido", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="movimientos")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    nota = models.CharField("nota", max_length=255, blank=True)
    fecha = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "movimiento de inventario"
        verbose_name_plural = "movimientos de inventario"

    def __str__(self):
        return f"{self.get_tipo_display()} {self.delta} {self.insumo.nombre}"
