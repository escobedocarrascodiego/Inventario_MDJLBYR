from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML
from .models import BajaBien


# ==============================================================================
# FORMULARIOS PARA BAJA DE BIENES
# ==============================================================================

class BajaBienForm(forms.ModelForm):
    """Formulario para registrar la baja de un bien"""
    
    class Meta:
        model = BajaBien
        fields = ['resolucion_baja', 'fecha_resolucion', 'causal_baja', 'documento_sbn']
        widgets = {
            'resolucion_baja': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_resolucion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'causal_baja': forms.Select(attrs={'class': 'form-select'}),
            'documento_sbn': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3">ACTO DE BAJA</h5>'),
            Row(
                Column('resolucion_baja', css_class='col-md-6'),
                Column('fecha_resolucion', css_class='col-md-6'),
            ),
            Row(
                Column('causal_baja', css_class='col-md-6'),
                Column('documento_sbn', css_class='col-md-6'),
            ),
            Submit('submit', 'Grabar', css_class='btn btn-primary mt-3')
        )
