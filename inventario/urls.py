from django.urls import path

from core import roles as r
from core.crud import crud_urls

from . import views
from .forms import InsumoForm, ItemBOMFormSet, ProductoForm
from .models import Insumo, MovimientoInventario, Producto

urlpatterns = crud_urls(
    "insumo", Insumo,
    columns=[("Insumo", "nombre"), ("Unidad", "unidad"), ("Stock", "stock"), ("Mínimo", "stock_minimo"),
             ("Estado", "estado_stock", "badge"), ("Vence", "fecha_vencimiento", "fecha"), ("Proveedor", "proveedor")],
    titulo="insumo", plural="Insumos en bodega",
    roles_ver=(r.COCINA, r.VENTAS), roles_editar=(r.COCINA,),
    form_class=InsumoForm, search_fields=("nombre", "proveedor"),
    filtro=("unidad", list(Insumo.Unidad.choices)),
) + crud_urls(
    "producto", Producto,
    columns=[("Producto", "nombre"), ("Porciones", "porciones"), ("Costo insumos", "costo_insumos", "money"),
             ("Precio sugerido", "precio_sugerido", "money"), ("Activo", "activo")],
    titulo="producto", plural="Productos y recetas (BOM)",
    roles_ver=(r.COCINA, r.VENTAS), roles_editar=(r.COCINA,),
    form_class=ProductoForm, formset_class=ItemBOMFormSet, detalle=True, search_fields=("nombre",),
    queryset=Producto.objects.prefetch_related("bom__insumo"),
) + crud_urls(
    "movimiento", MovimientoInventario,
    columns=[("Fecha", "fecha", "fechahora"), ("Insumo", "insumo"), ("Tipo", "tipo"), ("Variación", "delta"),
             ("Stock resultante", "stock_resultante"), ("Pedido", "pedido"), ("Usuario", "usuario"), ("Nota", "nota")],
    titulo="movimiento", plural="Movimientos de inventario",
    roles_ver=(r.COCINA, r.VENTAS), roles_editar=(r.COCINA,),
    search_fields=("insumo__nombre", "nota"), permitir=(),
    queryset=MovimientoInventario.objects.select_related("insumo", "usuario", "pedido"),
    filtro=("tipo", list(MovimientoInventario.Tipo.choices)), url_nuevo="movimiento_create",
) + [
    path("producto/<int:pk>/", views.ProductoDetalleView.as_view(), name="producto_detail"),
    path("movimiento/registrar/", views.MovimientoCrearView.as_view(), name="movimiento_create"),
]
