from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, FormView

from core import roles as r
from core.crud import RolMixin
from core.exceptions import ErrorDeNegocio, mensaje_error

from .forms import AgregarEntregaForm, ConfirmarEntregaForm
from .models import Entrega, Ruta


def rutas_visibles(qs, user):
    if r.tiene_rol(user, r.VENTAS):
        return qs
    return qs.filter(repartidor=user)


class RutaDetalleView(RolMixin, DetailView):
    roles = (r.VENTAS, r.REPARTO)
    template_name = "despacho/ruta_detail.html"

    def get_queryset(self):
        return rutas_visibles(Ruta.objects.select_related("repartidor"), self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["entregas"] = self.object.entregas.select_related("pedido__cliente")
        ctx["puede_planificar"] = r.tiene_rol(self.request.user, r.VENTAS) and self.object.es_editable
        ctx["puede_entregar"] = r.tiene_rol(self.request.user, r.REPARTO)
        ctx["form_agregar"] = AgregarEntregaForm()
        return ctx


class RutaAccionView(RolMixin, View):
    """Acciones POST sobre una ruta: iniciar, agregar entrega."""
    roles = (r.VENTAS, r.REPARTO)
    accion = None

    def post(self, request, pk):
        ruta = get_object_or_404(rutas_visibles(Ruta.objects.all(), request.user), pk=pk)
        try:
            if self.accion == "iniciar":
                ruta.iniciar()
                messages.success(request, "Ruta iniciada.")
            elif self.accion == "agregar":
                if not r.tiene_rol(request.user, r.VENTAS):
                    raise ErrorDeNegocio("No tienes permiso para planificar rutas.")
                if not ruta.es_editable:
                    raise ErrorDeNegocio("La ruta ya está completada.")
                form = AgregarEntregaForm(request.POST)
                if not form.is_valid():
                    raise ErrorDeNegocio("Selecciona un pedido listo para despachar.")
                orden = ruta.entregas.count() + 1
                entrega = Entrega(ruta=ruta, pedido=form.cleaned_data["pedido"], orden=orden)
                entrega.full_clean()
                entrega.save()
                messages.success(request, "Pedido agregado a la ruta.")
        except (ErrorDeNegocio, ValidationError) as e:
            messages.error(request, mensaje_error(e))
        return redirect("ruta_detail", pk=pk)


class EntregaConfirmarView(RolMixin, FormView):
    roles = (r.REPARTO,)
    form_class = ConfirmarEntregaForm
    template_name = "despacho/entrega_confirmar.html"

    def dispatch(self, request, *args, **kwargs):
        qs = Entrega.objects.select_related("pedido__cliente", "ruta")
        if request.user.is_authenticated and not request.user.is_superuser:
            qs = qs.filter(ruta__repartidor=request.user)
        self.entrega = get_object_or_404(qs, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["entrega"] = self.entrega
        return ctx

    def get_success_url(self):
        from django.urls import reverse
        return reverse("ruta_detail", args=[self.entrega.ruta_id])

    def form_valid(self, form):
        accion = self.request.POST.get("accion")
        d = form.cleaned_data
        try:
            self.entrega.confirmar(d["receptor_nombre"], d["firma"], d["foto"], self.request.user)
        except (ErrorDeNegocio, ValidationError) as e:
            form.add_error(None, mensaje_error(e))
            return self.form_invalid(form)
        messages.success(self.request, "Entrega confirmada.")
        return redirect(self.get_success_url())


class EntregaFallidaView(RolMixin, View):
    roles = (r.REPARTO,)

    def post(self, request, pk):
        qs = Entrega.objects.select_related("ruta")
        if not request.user.is_superuser:
            qs = qs.filter(ruta__repartidor=request.user)
        entrega = get_object_or_404(qs, pk=pk)
        try:
            entrega.marcar_fallida(request.POST.get("motivo", ""))
            messages.success(request, "Entrega marcada como fallida.")
        except ErrorDeNegocio as e:
            messages.error(request, mensaje_error(e))
        return redirect("ruta_detail", pk=entrega.ruta_id)
