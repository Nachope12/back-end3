from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from core import roles as r

from .models import Entrega, Ruta
from .serializers import ConfirmarEntregaSerializer, EntregaSerializer, FallidaSerializer, RutaSerializer


def _solo_propias(qs, user, campo):
    """Un repartidor solo ve sus rutas; ventas y administración ven todas."""
    if r.tiene_rol(user, r.VENTAS):
        return qs
    return qs.filter(**{campo: user})


class RutaViewSet(viewsets.ModelViewSet):
    queryset = Ruta.objects.select_related("repartidor").prefetch_related("entregas__pedido__cliente")
    serializer_class = RutaSerializer
    roles_lectura = (r.VENTAS, r.REPARTO)
    roles_escritura = (r.VENTAS,)
    roles_acciones = {"iniciar": (r.VENTAS, r.REPARTO)}

    def get_queryset(self):
        return _solo_propias(super().get_queryset(), self.request.user, "repartidor")

    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        ruta = self.get_object()
        ruta.iniciar()
        return Response(RutaSerializer(ruta).data)


class EntregaViewSet(viewsets.ModelViewSet):
    queryset = Entrega.objects.select_related("pedido__cliente", "ruta")
    serializer_class = EntregaSerializer
    roles_lectura = (r.VENTAS, r.REPARTO)
    roles_escritura = (r.VENTAS,)
    roles_acciones = {"confirmar": (r.REPARTO,), "fallida": (r.REPARTO,)}
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        return _solo_propias(super().get_queryset(), self.request.user, "ruta__repartidor")

    @action(detail=True, methods=["post"])
    def confirmar(self, request, pk=None):
        """Confirma la entrega con firma digital (data URL PNG) y/o foto del comprobante."""
        entrega = self.get_object()
        s = ConfirmarEntregaSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        entrega.confirmar(d["receptor_nombre"], d.get("firma", ""), d.get("foto"), request.user)
        return Response(EntregaSerializer(entrega).data)

    @action(detail=True, methods=["post"])
    def fallida(self, request, pk=None):
        entrega = self.get_object()
        s = FallidaSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        entrega.marcar_fallida(s.validated_data["motivo"])
        return Response(EntregaSerializer(entrega).data)
