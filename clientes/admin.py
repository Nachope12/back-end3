from django.contrib import admin

from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "telefono", "email", "direccion", "creado_en")
    search_fields = ("nombre", "email", "telefono", "direccion")
    list_filter = ("creado_en",)
    date_hierarchy = "creado_en"
