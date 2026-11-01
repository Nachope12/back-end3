from . import roles as r


def roles(request):
    u = request.user
    return {
        "es_admin": r.tiene_rol(u, r.ADMIN) if u.is_authenticated else False,
        "es_ventas": r.tiene_rol(u, r.VENTAS),
        "es_cocina": r.tiene_rol(u, r.COCINA),
        "es_reparto": r.tiene_rol(u, r.REPARTO),
    }
