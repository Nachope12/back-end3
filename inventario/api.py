from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core import roles as r

from .models import Insumo, MovimientoInventario, Producto
from .serializers import (InsumoSerializer, MovimientoCrearSerializer, MovimientoSerializer,
                          ProductoSerializer)
from .services import registrar_movimiento


class InsumoViewSet(viewsets.ModelViewSet):
    queryset = Insumo.objects.all()
    serializer_class = InsumoSerializer
    roles_lectura = (r.VENTAS, r.COCINA)
    roles_escritura = (r.COCINA,)
    filter_backends = [filters.SearchFilter]
    search_fields = ["nombre", "proveedor"]


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.prefetch_related("bom__insumo")
    serializer_class = ProductoSerializer
    roles_lectura = (r.VENTAS, r.COCINA)
    roles_escritura = (r.COCINA,)
    filter_backends = [filters.SearchFilter]
    search_fields = ["nombre"]


class MovimientoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = MovimientoInventario.objects.select_related("insumo", "usuario")
    serializer_class = MovimientoSerializer
    roles_lectura = (r.COCINA, r.VENTAS)
    roles_acciones = {"registrar": (r.COCINA,)}

    @action(detail=False, methods=["post"])
    def registrar(self, request):
        """Registra una entrada, merma o ajuste de stock."""
        s = MovimientoCrearSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        mov = registrar_movimiento(d["insumo"], d["tipo"], d["cantidad"], request.user, nota=d.get("nota", ""))
        return Response(MovimientoSerializer(mov).data, status=status.HTTP_201_CREATED)
