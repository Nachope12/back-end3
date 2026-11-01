from django import forms
from django.forms import inlineformset_factory

from core.forms import DateTimeLocalInput
from inventario.models import Producto

from .models import Cotizacion, CotizacionItem, DetallePedido, Pedido


class CotizacionForm(forms.ModelForm):
    class Meta:
        model = Cotizacion
        fields = ["cliente", "diseno", "fecha_entrega"]
        widgets = {"fecha_entrega": DateTimeLocalInput(), "diseno": forms.Textarea(attrs={"rows": 4})}


class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ["cliente", "diseno", "notas", "fecha_entrega", "direccion_entrega"]
        widgets = {
            "fecha_entrega": DateTimeLocalInput(),
            "diseno": forms.Textarea(attrs={"rows": 4}),
            "notas": forms.Textarea(attrs={"rows": 2}),
        }


class _LineaBase(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].queryset = Producto.objects.filter(activo=True)


class CotizacionItemForm(_LineaBase):
    class Meta:
        model = CotizacionItem
        fields = ["producto", "cantidad", "precio_unitario"]


class DetallePedidoForm(_LineaBase):
    class Meta:
        model = DetallePedido
        fields = ["producto", "cantidad", "precio_unitario"]


CotizacionItemFormSet = inlineformset_factory(
    Cotizacion, CotizacionItem, form=CotizacionItemForm, extra=1, min_num=1, validate_min=True, can_delete=True)
DetallePedidoFormSet = inlineformset_factory(
    Pedido, DetallePedido, form=DetallePedidoForm, extra=1, min_num=1, validate_min=True, can_delete=True)
