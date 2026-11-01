"""Roles del sistema (grupos de Django)."""
ADMIN = "Administrador"
VENTAS = "Ventas"
COCINA = "Cocina"
REPARTO = "Repartidor"
TODOS = (ADMIN, VENTAS, COCINA, REPARTO)


def tiene_rol(usuario, *roles):
    """True si el usuario es superusuario, Administrador o pertenece a alguno de los roles."""
    if not usuario or not usuario.is_authenticated:
        return False
    if usuario.is_superuser:
        return True
    return usuario.groups.filter(name__in=set(roles) | {ADMIN}).exists()
