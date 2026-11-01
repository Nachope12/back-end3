from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import F
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils._os import safe_join

from despacho.models import Entrega
from inventario.models import Insumo
from pedidos.models import COLUMNAS_KANBAN, Estado, Pedido

from . import roles as r


@login_required
def dashboard(request):
    ahora = timezone.now()
    hoy = timezone.localdate()
    conteo = {codigo: 0 for codigo, _ in COLUMNAS_KANBAN}
    for p in Pedido.objects.filter(estado__in=conteo.keys()).values_list("estado", flat=True):
        conteo[p] += 1
    activos = Pedido.objects.exclude(estado__in=[Estado.ENTREGADO, Estado.CANCELADO]).select_related("cliente")
    ctx = {
        "conteo_estados": [(nombre, conteo[codigo], codigo) for codigo, nombre in COLUMNAS_KANBAN],
        "entregas_hoy": activos.filter(fecha_entrega__date=hoy).order_by("fecha_entrega"),
        "urgentes": activos.filter(fecha_entrega__lte=ahora + timedelta(hours=6)).exclude(estado=Estado.LISTO)
                           .order_by("fecha_entrega")[:8],
        "insumos_bajos": Insumo.objects.filter(activo=True, stock__lte=F("stock_minimo")).order_by("nombre")[:10],
        "por_vencer": Insumo.objects.filter(
            activo=True, fecha_vencimiento__isnull=False,
            fecha_vencimiento__lte=hoy + timedelta(days=settings.DIAS_ALERTA_VENCIMIENTO),
        ).order_by("fecha_vencimiento")[:10],
        "entregas_pendientes": Entrega.objects.filter(estado=Entrega.Estado.PENDIENTE).count(),
    }
    return render(request, "dashboard.html", ctx)


@login_required
def media_protegida(request, ruta):
    """Los comprobantes de entrega solo los ve personal autorizado (no son públicos)."""
    if not r.tiene_rol(request.user, r.VENTAS, r.REPARTO):
        raise PermissionDenied
    try:
        archivo = safe_join(settings.MEDIA_ROOT, ruta)
        return FileResponse(open(archivo, "rb"))
    except (FileNotFoundError, IsADirectoryError, PermissionError, ValueError):
        raise Http404


def pagina_no_encontrada(request, exception=None):
    """Error 404 propio: avisa y redirige automáticamente a la aplicación."""
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": "No encontrado."}, status=404)
    autenticado = getattr(getattr(request, "user", None), "is_authenticated", False)
    destino = reverse("dashboard") if autenticado else reverse("login")
    return render(request, "404.html", {"destino": destino, "segundos": 5}, status=404)
