from django.contrib import admin
from django.db.models import F
from django.utils.html import format_html

from .models import Insumo, ItemBOM, MovimientoInventario, Producto


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "unidad", "stock", "stock_minimo", "indicador", "fecha_vencimiento",
                    "proveedor", "activo")
    list_filter = ("unidad", "perecible", "activo", "proveedor")
    search_fields = ("nombre", "proveedor")
    list_editable = ("activo",)
    ordering = ("nombre",)
    change_list_template = "admin/inventario/insumo/change_list.html"

    @admin.display(description="Estado")
    def indicador(self, obj):
        color = {"OK": "#2f7d4f", "POR_VENCER": "#b7791f", "BAJO": "#c0392b", "VENCIDO": "#7b1e3a"}[obj.estado_stock]
        return format_html('<b style="color:{}">{}</b>', color, obj.estado_stock_display)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["bajo_minimo"] = Insumo.objects.filter(activo=True, stock__lte=F("stock_minimo")).count()
        return super().changelist_view(request, extra_context)


class ItemBOMInline(admin.TabularInline):
    model = ItemBOM
    extra = 1
    autocomplete_fields = ("insumo",)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "porciones", "tiempo_preparacion_min", "costo", "precio", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "descripcion")
    inlines = [ItemBOMInline]

    @admin.display(description="Costo de insumos")
    def costo(self, obj):
        return f"${obj.costo_insumos():,.0f}".replace(",", ".")

    @admin.display(description="Precio sugerido")
    def precio(self, obj):
        return f"${obj.precio_sugerido():,.0f}".replace(",", ".")


@admin.register(ItemBOM)
class ItemBOMAdmin(admin.ModelAdmin):
    list_display = ("producto", "insumo", "cantidad")
    list_filter = ("producto",)
    search_fields = ("producto__nombre", "insumo__nombre")
    autocomplete_fields = ("insumo",)


@admin.register(MovimientoInventario)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "insumo", "tipo", "delta", "stock_resultante", "pedido", "usuario")
    list_filter = ("tipo", "fecha")
    search_fields = ("insumo__nombre", "nota")
    date_hierarchy = "fecha"
    readonly_fields = [f.name for f in MovimientoInventario._meta.fields]

    def has_add_permission(self, request):
        return False  # el stock solo cambia mediante operaciones auditadas

    def has_delete_permission(self, request, obj=None):
        return False
