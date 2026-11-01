from django.core.exceptions import ValidationError


class ErrorDeNegocio(Exception):
    """Error de regla de negocio (se informa al usuario con un mensaje claro)."""


class StockInsuficiente(ErrorDeNegocio):
    def __init__(self, faltantes):
        self.faltantes = faltantes  # lista de textos: "Harina: faltan 300 g"
        super().__init__("Stock insuficiente: " + "; ".join(faltantes))


class TransicionInvalida(ErrorDeNegocio):
    pass


def mensaje_error(exc):
    """Convierte cualquier excepción de negocio/validación en un texto legible."""
    if isinstance(exc, ValidationError):
        return " ".join(exc.messages)
    return str(exc)
