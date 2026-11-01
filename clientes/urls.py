from core import roles as r
from core.crud import crud_urls

from .forms import ClienteForm
from .models import Cliente

urlpatterns = crud_urls(
    "cliente", Cliente,
    columns=[("Nombre", "nombre"), ("Teléfono", "telefono"), ("Correo", "email"), ("Dirección", "direccion")],
    titulo="cliente", plural="Clientes",
    roles_ver=(r.VENTAS,), roles_editar=(r.VENTAS,),
    form_class=ClienteForm, search_fields=("nombre", "email", "telefono"),
)
