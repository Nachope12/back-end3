from rest_framework import serializers

from core.exceptions import ErrorDeNegocio
from core.serializers import EscrituraAnidadaMixin
from core.validators import validar_anticipacion

from .models import Cotizacion, CotizacionItem, DetallePedido, HistorialEstado, Pedido


class _LineaSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    precio_unitario = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)


class CotizacionItemSerializer(_LineaSerializer):
    class Meta:
        model = CotizacionItem
        fields = ["id", "producto", "producto_nombre", "cantidad", "precio_unitario", "subtotal"]


class DetallePedidoSerializer(_LineaSerializer):
    class Meta:
        model = DetallePedido
        fields = ["id", "producto", "producto_nombre", "cantidad", "precio_unitario", "subtotal"]


class CotizacionSerializer(EscrituraAnidadaMixin, serializers.ModelSerializer):
    items = CotizacionItemSerializer(many=True, allow_empty=False)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)

    campo_anidado = "items"
    modelo_hijo = CotizacionItem
    fk_hijo = "cotizacion"

    class Meta:
        model = Cotizacion
        fields = ["id", "cliente", "cliente_nombre", "diseno", "fecha_entrega", "estado", "total", "items",
                  "creado_por", "creado_en"]
        read_only_fields = ["estado", "total", "creado_por", "creado_en"]

    def validate_fecha_entrega(self, valor):
        if self.instance is None:
            validar_anticipacion(valor)
        return valor

    def update(self, instance, validated_data):
        if not instance.es_editable:
            raise ErrorDeNegocio("Solo se pueden editar cotizaciones pendientes.")
        return super().update(instance, validated_data)


class HistorialSerializer(serializers.ModelSerializer):
    usuario = serializers.CharField(source="usuario.username", read_only=True, default=None)

    class Meta:
        model = HistorialEstado
        fields = ["fecha", "de", "a", "usuario"]


class PedidoSerializer(EscrituraAnidadaMixin, serializers.ModelSerializer):
    detalles = DetallePedidoSerializer(many=True, allow_empty=False)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    urgente = serializers.BooleanField(read_only=True)

    campo_anidado = "detalles"
    modelo_hijo = DetallePedido
    fk_hijo = "pedido"

    class Meta:
        model = Pedido
        fields = ["id", "cliente", "cliente_nombre", "cotizacion", "diseno", "notas", "fecha_entrega",
                  "direccion_entrega", "estado", "estado_display", "urgente", "total", "insumos_descontados",
                  "detalles", "creado_por", "creado_en"]
        read_only_fields = ["estado", "total", "insumos_descontados", "cotizacion", "creado_por", "creado_en"]

    def validate_fecha_entrega(self, valor):
        if self.instance is None:
            validar_anticipacion(valor)
        return valor

    def update(self, instance, validated_data):
        if not instance.es_editable:
            raise ErrorDeNegocio("Solo se pueden editar pedidos en estado «Recibido».")
        return super().update(instance, validated_data)


class PedidoDetalleSerializer(PedidoSerializer):
    historial = HistorialSerializer(many=True, read_only=True)

    class Meta(PedidoSerializer.Meta):
        fields = PedidoSerializer.Meta.fields + ["historial"]
