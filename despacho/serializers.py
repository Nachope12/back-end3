from rest_framework import serializers

from .models import Entrega, Ruta


class EntregaSerializer(serializers.ModelSerializer):
    pedido_resumen = serializers.CharField(source="pedido.__str__", read_only=True)
    direccion = serializers.CharField(source="pedido.direccion_entrega", read_only=True)
    firma_url = serializers.SerializerMethodField()
    foto_url = serializers.SerializerMethodField()

    class Meta:
        model = Entrega
        fields = ["id", "ruta", "pedido", "pedido_resumen", "direccion", "orden", "estado", "receptor_nombre",
                  "firma_url", "foto_url", "observaciones", "entregada_en"]
        read_only_fields = ["estado", "receptor_nombre", "observaciones", "entregada_en"]

    def get_firma_url(self, obj):
        return obj.firma.url if obj.firma else None

    def get_foto_url(self, obj):
        return obj.foto.url if obj.foto else None

    def validate(self, datos):
        if self.instance is None:  # reglas al asignar un pedido a una ruta
            Entrega(**datos).clean()
        return datos


class RutaSerializer(serializers.ModelSerializer):
    entregas = EntregaSerializer(many=True, read_only=True)
    repartidor_nombre = serializers.CharField(source="repartidor.username", read_only=True, default=None)

    class Meta:
        model = Ruta
        fields = ["id", "nombre", "fecha", "repartidor", "repartidor_nombre", "estado", "entregas"]
        read_only_fields = ["estado"]


class ConfirmarEntregaSerializer(serializers.Serializer):
    receptor_nombre = serializers.CharField(max_length=150)
    firma = serializers.CharField(required=False, allow_blank=True,
                                  help_text="Firma como data URL PNG (data:image/png;base64,...)")
    foto = serializers.ImageField(required=False)


class FallidaSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=255)
