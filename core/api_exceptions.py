from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .exceptions import ErrorDeNegocio, StockInsuficiente, mensaje_error


def manejador_errores(exc, context):
    """Convierte errores de negocio en respuestas 400 con un mensaje claro."""
    if isinstance(exc, StockInsuficiente):
        return Response({"detail": str(exc), "faltantes": exc.faltantes}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, (ErrorDeNegocio, DjangoValidationError)):
        return Response({"detail": mensaje_error(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return exception_handler(exc, context)
