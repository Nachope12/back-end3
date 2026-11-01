from rest_framework import serializers

from .models import Cliente


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ["id", "nombre", "email", "telefono", "direccion", "creado_en"]
        read_only_fields = ["creado_en"]
