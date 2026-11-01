"""Operaciones de inventario con bloqueo de filas para evitar stock negativo."""
from decimal import Decimal

from django.db import transaction

from core.exceptions import ErrorDeNegocio, StockInsuficiente

from .models import Insumo, MovimientoInventario

SIGNO = {
    MovimientoInventario.Tipo.ENTRADA: 1,
    MovimientoInventario.Tipo.DEVOLUCION: 1,
    MovimientoInventario.Tipo.CONSUMO: -1,
    MovimientoInventario.Tipo.MERMA: -1,
}


@transaction.atomic
def registrar_movimiento(insumo, tipo, cantidad, usuario=None, pedido=None, nota=""):
    """Aplica un movimiento al stock. En AJUSTE la cantidad lleva signo; en el resto es positiva."""
    cantidad = Decimal(cantidad)
    insumo = Insumo.objects.select_for_update().get(pk=insumo.pk)
    if tipo == MovimientoInventario.Tipo.AJUSTE:
        delta = cantidad
        if delta == 0:
            raise ErrorDeNegocio("El ajuste no puede ser cero.")
    else:
        if cantidad <= 0:
            raise ErrorDeNegocio("La cantidad debe ser mayor que cero.")
        delta = SIGNO[tipo] * cantidad
    nuevo = insumo.stock + delta
    if nuevo < 0:
        raise StockInsuficiente([f"{insumo.nombre}: faltan {-nuevo} {insumo.unidad}"])
    insumo.stock = nuevo
    insumo.save(update_fields=["stock"])
    return MovimientoInventario.objects.create(
        insumo=insumo, tipo=tipo, delta=delta, stock_resultante=nuevo,
        usuario=usuario, pedido=pedido, nota=nota,
    )
