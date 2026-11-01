from django import forms
from django.contrib.auth import get_user_model

from core import roles as r
from core.forms import DateInput
from pedidos.models import Estado, Pedido

from .models import Entrega, Ruta


class RutaForm(forms.ModelForm):
    class Meta:
        model = Ruta
        fields = ["nombre", "fecha", "repartidor"]
        widgets = {"fecha": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["repartidor"].queryset = get_user_model().objects.filter(groups__name=r.REPARTO, is_active=True)


class AgregarEntregaForm(forms.Form):
    pedido = forms.ModelChoiceField(Pedido.objects.none(), label="Pedido listo para despachar")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ocupados = Entrega.objects.exclude(estado=Entrega.Estado.FALLIDA).values("pedido")
        self.fields["pedido"].queryset = (Pedido.objects.filter(estado=Estado.LISTO).exclude(pk__in=ocupados)
                                          .select_related("cliente").order_by("fecha_entrega"))


class ConfirmarEntregaForm(forms.Form):
    receptor_nombre = forms.CharField(label="Nombre de quien recibe", max_length=150)
    firma = forms.CharField(widget=forms.HiddenInput, required=False)
    foto = forms.ImageField(label="Foto del comprobante (opcional si hay firma)", required=False)

    def clean(self):
        datos = super().clean()
        if not datos.get("firma") and not datos.get("foto"):
            raise forms.ValidationError("Debes firmar en el recuadro o adjuntar una foto del comprobante.")
        return datos
