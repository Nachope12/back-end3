from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


def validar_anticipacion(fecha):
    """Regla de negocio: los pedidos personalizados requieren anticipación mínima."""
    horas = settings.MIN_HORAS_ANTICIPACION
    if fecha and fecha < timezone.now() + timedelta(hours=horas):
        raise ValidationError(
            f"La entrega debe programarse con al menos {horas} horas de anticipación."
        )
