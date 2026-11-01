from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, TemplateView

from core import roles as r
from core.crud import RolMixin
from core.exceptions import ErrorDeNegocio, mensaje_error

from .models import AVANCE, COLUMNAS_KANBAN, Cotizacion, Estado, Pedido


class PedidoDetalleView(RolMixin, DetailView):
    roles = (r.VENTAS, r.COCINA, r.REPARTO)
    template_name = "pedidos/pedido_detail.html"

    def get_queryset(self):
        return Pedido.objects.select_related("cliente", "cotizacion").prefetch_related(
            "detalles__producto", "historial__usuario")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["requerimiento"] = self.object.requerimiento()
        ctx["puede_cancelar"] = r.tiene_rol(self.request.user, r.VENTAS) and self.object.estado == Estado.RECIBIDO
        return ctx


class PedidoCancelarView(RolMixin, View):
    roles = (r.VENTAS,)

    def post(self, request, pk):
        pedido = get_object_or_404(Pedido, pk=pk)
        try:
            pedido.cancelar(request.user)
            messages.success(request, f"{pedido} cancelado.")
        except (ErrorDeNegocio, ValidationError) as e:
            messages.error(request, mensaje_error(e))
        return redirect("pedido_detail", pk=pk)


class KanbanView(RolMixin, TemplateView):
    roles = (r.VENTAS, r.COCINA)
    template_name = "pedidos/kanban.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pedidos = (Pedido.objects.filter(estado__in=[c for c, _ in COLUMNAS_KANBAN])
                   .select_related("cliente").prefetch_related("detalles__producto").order_by("fecha_entrega"))
        columnas = []
        for codigo, nombre in COLUMNAS_KANBAN:
            lista = [p for p in pedidos if p.estado == codigo]
            columnas.append({"codigo": codigo, "nombre": nombre, "pedidos": lista, "cantidad": len(lista)})
        ctx["columnas"] = columnas
        ctx["puede_mover"] = r.tiene_rol(self.request.user, r.COCINA)
        ctx["avance"] = {k.value: v.value for k, v in AVANCE.items()}
        return ctx


class CotizacionDetalleView(RolMixin, DetailView):
    roles = (r.VENTAS,)
    template_name = "pedidos/cotizacion_detail.html"

    def get_queryset(self):
        return Cotizacion.objects.select_related("cliente").prefetch_related("items__producto")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["requerimiento"] = self.object.requerimiento()
        return ctx


class CotizacionAccionView(RolMixin, View):
    roles = (r.VENTAS,)
    accion = None

    def post(self, request, pk):
        cot = get_object_or_404(Cotizacion, pk=pk)
        try:
            if self.accion == "aprobar":
                pedido = cot.aprobar(request.user)
                messages.success(request, f"Cotización aprobada. Se creó el pedido #{pedido.pk}.")
                return redirect("pedido_detail", pk=pedido.pk)
            cot.rechazar()
            messages.success(request, "Cotización rechazada.")
        except (ErrorDeNegocio, ValidationError) as e:
            messages.error(request, mensaje_error(e))
        return redirect("cotizacion_detail", pk=pk)
