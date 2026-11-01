from django.urls import path

from core import roles as r
from core.crud import crud_urls

from . import views
from .forms import RutaForm
from .models import Ruta

urlpatterns = crud_urls(
    "ruta", Ruta,
    columns=[("Ruta", "nombre"), ("Fecha", "fecha", "fecha"), ("Repartidor", "repartidor"),
             ("Estado", "estado", "badge"), ("Avance", "resumen")],
    titulo="ruta", plural="Rutas de despacho",
    roles_ver=(r.VENTAS, r.REPARTO), roles_editar=(r.VENTAS,),
    form_class=RutaForm, detalle=True, search_fields=("nombre", "repartidor__username"),
    queryset=Ruta.objects.select_related("repartidor"),
    filtro_usuario=views.rutas_visibles,
    filtro=("estado", list(Ruta.Estado.choices)),
) + [
    path("ruta/<int:pk>/", views.RutaDetalleView.as_view(), name="ruta_detail"),
    path("ruta/<int:pk>/iniciar/", views.RutaAccionView.as_view(accion="iniciar"), name="ruta_iniciar"),
    path("ruta/<int:pk>/agregar/", views.RutaAccionView.as_view(accion="agregar"), name="ruta_agregar"),
    path("entrega/<int:pk>/confirmar/", views.EntregaConfirmarView.as_view(), name="entrega_confirmar"),
    path("entrega/<int:pk>/fallida/", views.EntregaFallidaView.as_view(), name="entrega_fallida"),
]
