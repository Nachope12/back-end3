from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView

from core import roles as r
from core.crud import RolMixin
from core.exceptions import ErrorDeNegocio, mensaje_error

from .forms import MovimientoForm
from .models import Producto
from .services import registrar_movimiento


class ProductoDetalleView(RolMixin, DetailView):
    roles = (r.VENTAS, r.COCINA)
    model = Producto
    template_name = "inventario/producto_detail.html"

    def get_queryset(self):
        return Producto.objects.prefetch_related("bom__insumo")


class MovimientoCrearView(RolMixin, FormView):
    roles = (r.COCINA,)
    form_class = MovimientoForm
    template_name = "crud/form.html"
    success_url = reverse_lazy("movimiento_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(titulo="Registrar movimiento de inventario", url_lista=self.success_url)
        return ctx

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            registrar_movimiento(d["insumo"], d["tipo"], d["cantidad"], self.request.user, nota=d["nota"])
        except ErrorDeNegocio as e:
            form.add_error(None, mensaje_error(e))
            return self.form_invalid(form)
        messages.success(self.request, "Movimiento registrado.")
        return redirect(self.success_url)
