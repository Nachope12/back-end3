from django.urls import include, path
from rest_framework.routers import DefaultRouter

from clientes.api import ClienteViewSet
from despacho.api import EntregaViewSet, RutaViewSet
from inventario.api import InsumoViewSet, MovimientoViewSet, ProductoViewSet
from pedidos.api import CotizacionViewSet, PedidoViewSet

router = DefaultRouter()
router.register("clientes", ClienteViewSet)
router.register("insumos", InsumoViewSet)
router.register("productos", ProductoViewSet)
router.register("movimientos", MovimientoViewSet)
router.register("cotizaciones", CotizacionViewSet)
router.register("pedidos", PedidoViewSet)
router.register("rutas", RutaViewSet)
router.register("entregas", EntregaViewSet)

urlpatterns = [path("", include(router.urls))]
