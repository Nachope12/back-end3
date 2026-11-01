from django.contrib import admin
from django.urls import include, path, re_path

from core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("config.api_urls")),
    path("api-auth/", include("rest_framework.urls")),
    path("", include("core.urls")),
    path("", include("clientes.urls")),
    path("", include("inventario.urls")),
    path("", include("pedidos.urls")),
    path("", include("despacho.urls")),
    # Cualquier ruta inexistente (que termine en "/") muestra la página 404 propia, también con DEBUG=True
    re_path(r"^.*/$", core_views.pagina_no_encontrada),
]

handler404 = "core.views.pagina_no_encontrada"
