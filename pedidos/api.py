from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core import roles as r
from core.exceptions import ErrorDeNegocio

from .models import COLUMNAS_KANBAN, Cotizacion, Estado, Pedido
from .serializers import CotizacionSerializer, PedidoDetalleSerializer, PedidoSerializer


class CotizacionViewSet(viewsets.ModelViewSet):
    queryset = Cotizacion.objects.select_related("cliente").prefetch_related("items__producto")
    serializer_class = CotizacionSerializer
    roles_lectura = (r.VENTAS,)
    roles_escritura = (r.VENTAS,)
    filter_backends = [filters.SearchFilter]
    search_fields = ["cliente__nombre", "diseno"]

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        """Aprueba la cotización y genera el pedido."""
        pedido = self.get_object().aprobar(request.user)
        return Response(PedidoSerializer(pedido).data, status=201)

    @action(detail=True, methods=["post"])
    def rechazar(self, request, pk=None):
        cot = self.get_object()
        cot.rechazar()
        return Response(CotizacionSerializer(cot).data)

    @action(detail=True, methods=["get"])
    def requerimiento(self, request, pk=None):
        filas = self.get_object().requerimiento()
        return Response([{"insumo": f["insumo"].nombre, "necesario": f["necesario"], "stock": f["stock"],
                          "falta": f["falta"]} for f in filas])


class PedidoViewSet(viewsets.ModelViewSet):
    queryset = Pedido.objects.select_related("cliente").prefetch_related("detalles__producto", "historial")
    roles_lectura = (r.VENTAS, r.COCINA, r.REPARTO)
    roles_escritura = (r.VENTAS,)
    roles_acciones = {
        "cambiar_estado": (r.COCINA,),
        "cancelar": (r.VENTAS,),
        "kanban": (r.VENTAS, r.COCINA),
        "requerimiento": (r.VENTAS, r.COCINA),
    }
    filter_backends = [filters.SearchFilter]
    search_fields = ["cliente__nombre", "diseno"]

    def get_serializer_class(self):
        return PedidoDetalleSerializer if self.action == "retrieve" else PedidoSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        estado = self.request.query_params.get("estado")
        return qs.filter(estado=estado) if estado else qs

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)

    @action(detail=True, methods=["post"])
    def cambiar_estado(self, request, pk=None):
        """Mueve el pedido en el tablero. Body: {"estado": "EN_PREPARACION"}.
        Al pasar a «En preparación» descuenta los insumos según el BOM."""
        pedido = self.get_object()
        nuevo = request.data.get("estado")
        if nuevo not in Estado.values or nuevo == Estado.CANCELADO:
            raise ErrorDeNegocio("Estado no válido para el tablero.")
        pedido.cambiar_estado(nuevo, request.user)
        return Response(PedidoSerializer(pedido).data)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        pedido = self.get_object()
        pedido.cancelar(request.user)
        return Response(PedidoSerializer(pedido).data)

    @action(detail=False, methods=["get"])
    def kanban(self, request):
        """Pedidos agrupados por columna del tablero de cocina."""
        pedidos = self.get_queryset().filter(estado__in=[c for c, _ in COLUMNAS_KANBAN])
        columnas = []
        for codigo, nombre in COLUMNAS_KANBAN:
            columnas.append({
                "estado": codigo, "nombre": nombre,
                "pedidos": PedidoSerializer([p for p in pedidos if p.estado == codigo], many=True).data,
            })
        return Response({"columnas": columnas})

    @action(detail=True, methods=["get"])
    def requerimiento(self, request, pk=None):
        filas = self.get_object().requerimiento()
        return Response([{"insumo": f["insumo"].nombre, "necesario": f["necesario"], "stock": f["stock"],
                          "falta": f["falta"]} for f in filas])
