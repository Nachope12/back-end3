from rest_framework.permissions import SAFE_METHODS, BasePermission

from .roles import tiene_rol


class RolPermission(BasePermission):
    """Permisos por rol.

    Cada ViewSet define:
      roles_lectura   -> roles que pueden consultar (None = cualquier usuario autenticado)
      roles_escritura -> roles que pueden crear/editar/borrar
      roles_acciones  -> {nombre_accion: roles} para acciones personalizadas
    El rol Administrador (y superusuarios) siempre tiene acceso.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        accion = getattr(view, "action", None)
        especiales = getattr(view, "roles_acciones", {})
        if accion in especiales:
            roles = especiales[accion]
        elif request.method in SAFE_METHODS:
            roles = getattr(view, "roles_lectura", None)
        else:
            roles = getattr(view, "roles_escritura", None)
        if roles is None:
            return True
        return tiene_rol(request.user, *roles)
