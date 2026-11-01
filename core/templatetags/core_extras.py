from decimal import Decimal

from django import template
from django.utils import timezone
from django.utils.html import format_html

register = template.Library()


def _decimal(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


@register.filter
def clp(valor):
    """Formatea pesos chilenos: 12500 -> $12.500"""
    try:
        n = Decimal(valor)
    except Exception:
        return "—"
    return "$" + f"{n:,.0f}".replace(",", ".")


@register.filter
def num(valor):
    try:
        return _decimal(Decimal(valor))
    except Exception:
        return valor


@register.simple_tag
def cell(obj, col):
    """Muestra el valor de una columna (etiqueta, atributo[, tipo])."""
    attr = col[1]
    tipo = col[2] if len(col) > 2 else None
    valor = getattr(obj, attr)
    if callable(valor):
        valor = valor()
    display = getattr(obj, f"get_{attr}_display", None) or getattr(obj, f"{attr}_display", None)
    if callable(display):
        display = display()
    if valor is None or valor == "":
        return "—"
    if tipo == "badge":
        return format_html('<span class="badge badge-{}">{}</span>', valor, display or valor)
    if tipo == "money":
        return clp(valor)
    if tipo == "fechahora":
        return timezone.localtime(valor).strftime("%d/%m/%Y %H:%M")
    if tipo == "fecha":
        return valor.strftime("%d/%m/%Y")
    if display:
        return display
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, Decimal):
        return _decimal(valor)
    return valor


@register.filter
def editable(obj):
    """True si el objeto no define `es_editable` o si lo es."""
    return getattr(obj, "es_editable", True)
