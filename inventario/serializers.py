from rest_framework import serializers

from core.serializers import EscrituraAnidadaMixin

from .models import Insumo, ItemBOM, MovimientoInventario, Producto


class InsumoSerializer(serializers.ModelSerializer):
    estado_stock = serializers.CharField(read_only=True)

    class Meta:
        model = Insumo
        fields = ["id", "nombre", "unidad", "stock", "stock_minimo", "costo_unitario", "perecible",
                  "fecha_vencimiento", "proveedor", "activo", "estado_stock"]

    def update(self, instance, validated_data):
        validated_data.pop("stock", None)  # el stock solo cambia mediante movimientos auditados
        return super().update(instance, validated_data)


class ItemBOMSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)

    class Meta:
        model = ItemBOM
        fields = ["id", "insumo", "insumo_nombre", "cantidad"]


class ProductoSerializer(EscrituraAnidadaMixin, serializers.ModelSerializer):
    bom = ItemBOMSerializer(many=True, allow_empty=False)
    costo_insumos = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    precio_sugerido = serializers.DecimalField(max_digits=14, decimal_places=0, read_only=True)

    campo_anidado = "bom"
    modelo_hijo = ItemBOM
    fk_hijo = "producto"

    class Meta:
        model = Producto
        fields = ["id", "nombre", "descripcion", "porciones", "tiempo_preparacion_min", "mano_obra",
                  "margen_pct", "activo", "bom", "costo_insumos", "precio_sugerido"]


class MovimientoSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)
    usuario_nombre = serializers.CharField(source="usuario.username", read_only=True, default=None)

    class Meta:
        model = MovimientoInventario
        fields = ["id", "fecha", "insumo", "insumo_nombre", "tipo", "delta", "stock_resultante",
                  "pedido", "usuario_nombre", "nota"]


class MovimientoCrearSerializer(serializers.Serializer):
    insumo = serializers.PrimaryKeyRelatedField(queryset=Insumo.objects.filter(activo=True))
    tipo = serializers.ChoiceField(choices=[MovimientoInventario.Tipo.ENTRADA, MovimientoInventario.Tipo.MERMA,
                                            MovimientoInventario.Tipo.AJUSTE])
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=2)
    nota = serializers.CharField(required=False, allow_blank=True, max_length=255)
