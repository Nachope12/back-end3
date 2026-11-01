from django.apps import AppConfig
from django.db.models.signals import post_migrate


def crear_grupos(sender, **kwargs):
    from django.contrib.auth.models import Group

    from .roles import TODOS

    for nombre in TODOS:
        Group.objects.get_or_create(name=nombre)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Dulce Arte"

    def ready(self):
        post_migrate.connect(crear_grupos, sender=self)
