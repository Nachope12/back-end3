from django.db import transaction


class EscrituraAnidadaMixin:
    """Permite crear/actualizar un objeto junto a sus líneas hijas (ítems/detalles) en un solo JSON.

    Atributos a definir:  campo_anidado (related_name), modelo_hijo, fk_hijo
    """

    campo_anidado = None
    modelo_hijo = None
    fk_hijo = None

    def _crear_hijos(self, padre, hijos):
        for datos in hijos:
            self.modelo_hijo.objects.create(**{self.fk_hijo: padre}, **datos)

    def _despues(self, obj):
        if hasattr(obj, "recalcular_total"):
            obj.recalcular_total()

    @transaction.atomic
    def create(self, validated_data):
        hijos = validated_data.pop(self.campo_anidado, [])
        obj = super().create(validated_data)
        self._crear_hijos(obj, hijos)
        self._despues(obj)
        return obj

    @transaction.atomic
    def update(self, instance, validated_data):
        hijos = validated_data.pop(self.campo_anidado, None)
        obj = super().update(instance, validated_data)
        if hijos is not None:
            getattr(obj, self.campo_anidado).all().delete()
            self._crear_hijos(obj, hijos)
        self._despues(obj)
        return obj
