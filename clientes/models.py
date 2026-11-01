from django.db import models


class Cliente(models.Model):
    nombre = models.CharField("nombre", max_length=150)
    email = models.EmailField("correo", blank=True)
    telefono = models.CharField("teléfono", max_length=30, blank=True)
    direccion = models.CharField("dirección", max_length=255, blank=True)
    creado_en = models.DateTimeField("creado el", auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self):
        return self.nombre
