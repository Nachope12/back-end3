from django.contrib import admin, messages
from django.utils.html import format_html

from core.exceptions import ErrorDeNegocio, mensaje_error

from .models import (AVANCE, Cotizacion, CotizacionItem, DetallePedido, Estado, HistorialEstado, Pedido)

COLORES = {
    "RECIBIDO": "#7e6bb5", "EN_PREPARACION": "#b8860b", "HORNEADO_DECORADO": "#b4672a",
    "CONTROL_CALIDAD": "#2a7f8c", "LISTO": "#2f7d4f", "ENTREGADO": "#555", "CANCELADO": "#a33",
    "PENDIENTE": "#b8860b", "APROBADA": "#2f7d4f", "RECHAZADA": "#a33",
}


def insignia(obj):
    return format_html('<b style="color:{}">{}</b>', COLORES.get(obj.estado, "#333"), obj.get_estado_display())


class CotizacionItemInline(admin.TabularInline):
    model = CotizacionItem
    extra = 1


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 1


class HistorialInline(admin.TabularInline):
    model = HistorialEstado
    extra = 0
    can_delete = False
    readonly_fields = ("de", "a", "usuario", "fecha")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "fecha_entrega", "estado_color", "total", "creado_por")
    list_filter = ("estado", "fecha_entrega")
    search_fields = ("cliente__nombre", "diseno")
    date_hierarchy = "fecha_entrega"
    readonly_fields = ("estado", "total", "creado_por")
    inlines = [CotizacionItemInline]
    actions = ["aprobar"]

    @admin.display(description="Estado", ordering="estado")
    def estado_color(self, obj):
        return insignia(obj)

    def save_model(self, request, obj, form, change):
        if not obj.creado_por_id:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recalcular_total()

    @admin.action(description="Aprobar y generar pedido")
    def aprobar(self, request, queryset):
        for cot in queryset:
            try:
                pedido = cot.aprobar(request.user)
                self.message_user(request, f"{cot} aprobada → pedido #{pedido.pk}.", messages.SUCCESS)
            except ErrorDeNegocio as e:
                self.message_user(request, f"{cot}: {mensaje_error(e)}", messages.ERROR)


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "fecha_entrega", "estado_color", "urgente_si", "total", "insumos_descontados")
    list_filter = ("estado", "fecha_entrega", "insumos_descontados")
    search_fields = ("id", "cliente__nombre", "diseno", "direccion_entrega")
    date_hierarchy = "fecha_entrega"
    readonly_fields = ("estado", "total", "insumos_descontados", "creado_por", "creado_en", "actualizado_en")
    inlines = [DetallePedidoInline, HistorialInline]
    actions = ["avanzar"]
    change_form_template = "admin/pedidos/pedido/change_form.html"

    @admin.display(description="Estado", ordering="estado")
    def estado_color(self, obj):
        return insignia(obj)

    @admin.display(description="Urgente", boolean=True)
    def urgente_si(self, obj):
        return obj.urgente

    def save_model(self, request, obj, form, change):
        if not obj.creado_por_id:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recalcular_total()

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        pedido = Pedido.objects.filter(pk=object_id).first()
        if pedido:
            extra_context["requerimiento"] = pedido.requerimiento()
        return super().change_view(request, object_id, form_url, extra_context)

    @admin.action(description="Avanzar al siguiente estado del Kanban")
    def avanzar(self, request, queryset):
        for p in queryset:
            siguiente = AVANCE.get(p.estado)
            if not siguiente:
                self.message_user(request, f"{p}: no tiene un siguiente estado.", messages.WARNING)
                continue
            try:
                p.cambiar_estado(siguiente, request.user)
                self.message_user(request, f"{p}: ahora «{Estado(siguiente).label}».", messages.SUCCESS)
            except ErrorDeNegocio as e:
                self.message_user(request, f"{p}: {mensaje_error(e)}", messages.ERROR)


@admin.register(HistorialEstado)
class HistorialAdmin(admin.ModelAdmin):
    list_display = ("fecha", "pedido", "de", "a", "usuario")
    list_filter = ("a", "fecha")
    search_fields = ("pedido__cliente__nombre",)
    date_hierarchy = "fecha"
