"""Vistas CRUD genéricas con control de roles, búsqueda, filtros y formsets en línea.

`crud_urls(...)` genera las rutas  <prefix>_list / _create / _update / _delete
(y opcionalmente <prefix>_detail la define cada app)."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.shortcuts import redirect
from django.urls import path, reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .roles import tiene_rol


class RolMixin(LoginRequiredMixin):
    """Exige sesión iniciada y, si se define `roles`, pertenecer a alguno (Administrador siempre puede)."""

    roles = None

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self.roles is not None:
            if not tiene_rol(request.user, *self.roles):
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class ListaView(RolMixin, ListView):
    template_name = "crud/list.html"
    paginate_by = 15
    columns = ()
    search_fields = ()
    clave = ""
    titulo = ""
    roles_editar = ()
    permitir = ()
    detalle = False
    filtro = None          # (campo, [(valor, etiqueta), ...])
    filtro_usuario = None  # callable(queryset, usuario) -> queryset
    url_nuevo = None       # nombre de URL para el botón "Nuevo" cuando es una vista propia

    def get_queryset(self):
        qs = super().get_queryset()
        if self.filtro_usuario:
            qs = self.filtro_usuario(qs, self.request.user)
        q = self.request.GET.get("q", "").strip()
        if q and self.search_fields:
            cond = Q()
            for campo in self.search_fields:
                cond |= Q(**{f"{campo}__icontains": q})
            qs = qs.filter(cond)
        if self.filtro:
            valor = self.request.GET.get("f", "")
            if valor:
                qs = qs.filter(**{self.filtro[0]: valor})
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            titulo=self.titulo,
            columns=self.columns,
            q=self.request.GET.get("q", ""),
            f=self.request.GET.get("f", ""),
            filtro_opciones=self.filtro[1] if self.filtro else None,
            buscar=bool(self.search_fields),
            puede_editar=tiene_rol(self.request.user, *self.roles_editar),
            url_create=f"{self.clave}_create" if "create" in self.permitir else self.url_nuevo,
            url_update=f"{self.clave}_update" if "update" in self.permitir else None,
            url_delete=f"{self.clave}_delete" if "delete" in self.permitir else None,
            url_detail=f"{self.clave}_detail" if self.detalle else None,
        )
        return ctx


class GuardarMixin(RolMixin):
    template_name = "crud/form.html"
    formset_class = None
    clave = ""
    titulo = ""
    detalle = False
    es_edicion = False

    def _formset(self):
        datos = self.request.POST or None
        return self.formset_class(datos, self.request.FILES or None, instance=self.object, prefix="items")

    def _bloqueado(self):
        messages.error(self.request, "Este registro ya no se puede modificar en su estado actual.")
        return redirect(self.url_destino(self.object))

    def url_destino(self, obj):
        if self.detalle and obj is not None and obj.pk:
            return reverse(f"{self.clave}_detail", args=[obj.pk])
        return reverse(f"{self.clave}_list")

    def get(self, request, *args, **kwargs):
        if self.es_edicion:
            self.object = self.get_object()
            if not getattr(self.object, "es_editable", True):
                return self._bloqueado()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() if self.es_edicion else None
        if self.es_edicion and not getattr(self.object, "es_editable", True):
            return self._bloqueado()
        form = self.get_form()
        formset = self._formset() if self.formset_class else None
        if form.is_valid() and (formset is None or formset.is_valid()):
            return self.guardar(form, formset)
        return self.render_to_response(self.get_context_data(form=form, formset=formset))

    def guardar(self, form, formset):
        with transaction.atomic():
            obj = form.save(commit=False)
            if hasattr(obj, "creado_por_id") and not obj.creado_por_id:
                obj.creado_por = self.request.user
            obj.save()
            form.save_m2m()
            if formset is not None:
                formset.instance = obj
                formset.save()
            if hasattr(obj, "recalcular_total"):
                obj.recalcular_total()
        messages.success(self.request, "Cambios guardados correctamente.")
        return redirect(self.url_destino(obj))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titulo"] = ("Editar " if self.es_edicion else "Nuevo/a ") + self.titulo
        ctx["url_lista"] = reverse(f"{self.clave}_list")
        if self.formset_class and ctx.get("formset") is None:
            ctx["formset"] = self._formset()
        return ctx


class CrearView(GuardarMixin, CreateView):
    pass


class EditarView(GuardarMixin, UpdateView):
    es_edicion = True


class BorrarView(RolMixin, DeleteView):
    template_name = "crud/confirm_delete.html"
    clave = ""
    titulo = ""

    def get_success_url(self):
        return reverse(f"{self.clave}_list")

    def _bloquear_si_corresponde(self):
        self.object = self.get_object()
        if not getattr(self.object, "es_editable", True):
            messages.error(self.request, "Este registro ya no se puede eliminar en su estado actual.")
            return redirect(self.get_success_url())
        return None

    def get(self, request, *args, **kwargs):
        return self._bloquear_si_corresponde() or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self._bloquear_si_corresponde() or super().post(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            respuesta = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, "No se puede eliminar: tiene registros asociados.")
            return redirect(self.get_success_url())
        messages.success(self.request, "Registro eliminado.")
        return respuesta

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(titulo=f"Eliminar {self.titulo}", url_lista=self.get_success_url())
        return ctx


def crud_urls(prefix, model, columns, titulo, plural, roles_ver, roles_editar, form_class=None,
              formset_class=None, search_fields=(), detalle=False, filtro=None, queryset=None,
              permitir=("create", "update", "delete"), filtro_usuario=None, url_nuevo=None):
    """Devuelve las rutas CRUD de un modelo."""
    base = prefix
    urls = [
        path(f"{base}/", ListaView.as_view(
            model=model, queryset=queryset, columns=columns, search_fields=search_fields,
            roles=roles_ver, roles_editar=roles_editar, permitir=permitir, detalle=detalle,
            filtro=filtro, filtro_usuario=filtro_usuario, clave=prefix, titulo=plural,
            url_nuevo=url_nuevo),
            name=f"{prefix}_list"),
    ]
    comunes = dict(model=model, clave=prefix, titulo=titulo, roles=roles_editar)
    if "create" in permitir:
        urls.append(path(f"{base}/nuevo/", CrearView.as_view(
            form_class=form_class, formset_class=formset_class, detalle=detalle, **comunes),
            name=f"{prefix}_create"))
    if "update" in permitir:
        urls.append(path(f"{base}/<int:pk>/editar/", EditarView.as_view(
            form_class=form_class, formset_class=formset_class, detalle=detalle, **comunes),
            name=f"{prefix}_update"))
    if "delete" in permitir:
        urls.append(path(f"{base}/<int:pk>/eliminar/", BorrarView.as_view(**comunes),
                         name=f"{prefix}_delete"))
    return urls
