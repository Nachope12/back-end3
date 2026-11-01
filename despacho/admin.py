from django.contrib import admin
from django.utils.html import format_html

from .models import Entrega, Ruta


class EntregaInline(admin.TabularInline):
    model = Entrega
    extra = 0
    fields = ("orden", "pedido", "estado", "receptor_nombre", "entregada_en")
    readonly_fields = ("estado", "receptor_nombre", "entregada_en")
    autocomplete_fields = ("pedido",)


@admin.register(Ruta)
class RutaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "fecha", "repartidor", "estado", "resumen")
    list_filter = ("estado", "fecha", "repartidor")
    search_fields = ("nombre", "repartidor__username", "repartidor__first_name")
    date_hierarchy = "fecha"
    readonly_fields = ("estado",)
    inlines = [EntregaInline]


@admin.register(Entrega)
class EntregaAdmin(admin.ModelAdmin):
    list_display = ("pedido", "ruta", "orden", "estado", "receptor_nombre", "entregada_en", "tiene_comprobante")
    list_filter = ("estado", "ruta__fecha", "ruta")
    search_fields = ("pedido__cliente__nombre", "receptor_nombre", "ruta__nombre")
    date_hierarchy = "entregada_en"
    readonly_fields = ("estado", "entregada_en", "vista_firma", "vista_foto")
    fields = ("ruta", "pedido", "orden", "estado", "receptor_nombre", "observaciones", "entregada_en",
              "vista_firma", "vista_foto")
    autocomplete_fields = ("pedido",)

    @admin.display(description="Comprobante", boolean=True)
    def tiene_comprobante(self, obj):
        return bool(obj.firma or obj.foto)

    @admin.display(description="Firma")
    def vista_firma(self, obj):
        return format_html('<img src="{}" style="max-height:120px;background:#fff;border:1px solid #ddd">', obj.firma.url) \
            if obj.firma else "—"

    @admin.display(description="Foto del comprobante")
    def vista_foto(self, obj):
        return format_html('<img src="{}" style="max-height:200px">', obj.foto.url) if obj.foto else "—"
