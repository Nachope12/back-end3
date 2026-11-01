from django import forms
from django.forms import inlineformset_factory

from core.forms import DateInput

from .models import Insumo, ItemBOM, MovimientoInventario, Producto


class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = ["nombre", "unidad", "stock", "stock_minimo", "costo_unitario", "perecible",
                  "fecha_vencimiento", "proveedor", "activo"]
        widgets = {"fecha_vencimiento": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:  # el stock solo cambia mediante movimientos auditados
            self.fields["stock"].disabled = True
            self.fields["stock"].help_text = "Para cambiar el stock registra un movimiento de inventario."


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ["nombre", "descripcion", "porciones", "tiempo_preparacion_min", "mano_obra",
                  "margen_pct", "activo"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}


ItemBOMFormSet = inlineformset_factory(
    Producto, ItemBOM, fields=("insumo", "cantidad"), extra=1, min_num=1, validate_min=True, can_delete=True,
)


class MovimientoForm(forms.Form):
    insumo = forms.ModelChoiceField(Insumo.objects.filter(activo=True), label="Insumo")
    tipo = forms.ChoiceField(
        label="Tipo de movimiento",
        choices=[(MovimientoInventario.Tipo.ENTRADA, "Entrada (compra)"),
                 (MovimientoInventario.Tipo.MERMA, "Merma / pérdida"),
                 (MovimientoInventario.Tipo.AJUSTE, "Ajuste (usa negativo para restar)")],
    )
    cantidad = forms.DecimalField(label="Cantidad", max_digits=12, decimal_places=2)
    nota = forms.CharField(label="Nota", max_length=255, required=False)
