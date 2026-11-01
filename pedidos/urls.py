from django.urls import path

from core import roles as r
from core.crud import crud_urls

from . import views
from .forms import CotizacionForm, CotizacionItemFormSet, DetallePedidoFormSet, PedidoForm
from .models import Cotizacion, Estado, Pedido

urlpatterns = crud_urls(
    "cotizacion", Cotizacion,
    columns=[("N°", "id"), ("Cliente", "cliente"), ("Entrega", "fecha_entrega", "fechahora"),
             ("Estado", "estado", "badge"), ("Total", "total", "money")],
    titulo="cotización", plural="Cotizaciones",
    roles_ver=(r.VENTAS,), roles_editar=(r.VENTAS,),
    form_class=CotizacionForm, formset_class=CotizacionItemFormSet, detalle=True,
    search_fields=("cliente__nombre", "diseno"),
    queryset=Cotizacion.objects.select_related("cliente"),
    filtro=("estado", list(Cotizacion.Estado.choices)),
) + crud_urls(
    "pedido", Pedido,
    columns=[("N°", "id"), ("Cliente", "cliente"), ("Entrega", "fecha_entrega", "fechahora"),
             ("Estado", "estado", "badge"), ("Total", "total", "money")],
    titulo="pedido", plural="Pedidos personalizados",
    roles_ver=(r.VENTAS, r.COCINA, r.REPARTO), roles_editar=(r.VENTAS,),
    form_class=PedidoForm, formset_class=DetallePedidoFormSet, detalle=True,
    search_fields=("cliente__nombre", "diseno"),
    queryset=Pedido.objects.select_related("cliente"),
    filtro=("estado", list(Estado.choices)),
) + [
    path("cotizacion/<int:pk>/", views.CotizacionDetalleView.as_view(), name="cotizacion_detail"),
    path("cotizacion/<int:pk>/aprobar/", views.CotizacionAccionView.as_view(accion="aprobar"),
         name="cotizacion_aprobar"),
    path("cotizacion/<int:pk>/rechazar/", views.CotizacionAccionView.as_view(accion="rechazar"),
         name="cotizacion_rechazar"),
    path("pedido/<int:pk>/", views.PedidoDetalleView.as_view(), name="pedido_detail"),
    path("pedido/<int:pk>/cancelar/", views.PedidoCancelarView.as_view(), name="pedido_cancelar"),
    path("cocina/", views.KanbanView.as_view(), name="kanban"),
]
