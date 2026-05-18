from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML
from organizacion.models import Oficina
from .models import Personal


# ==============================================================================
# FORMULARIOS PARA PERSONAL
# ==============================================================================

class PersonalForm(forms.ModelForm):
    class Meta:
        model = Personal
        fields = [
            'nombres', 'apellidos', 'tipo_documento', 'numero_documento',
            'modalidad', 'area', 'oficina', 'cargo'
        ]
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'numero_documento': forms.TextInput(attrs={'class': 'form-control'}),
            'modalidad': forms.Select(attrs={'class': 'form-select'}),
            'area': forms.Select(attrs={'class': 'form-select', 'id': 'id_area'}),
            'oficina': forms.Select(attrs={'class': 'form-select', 'id': 'id_oficina'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer oficina opcional
        self.fields['oficina'].required = False
        self.fields['oficina'].empty_label = "Seleccione una oficina (opcional)"
        
        # Filtrar oficinas según el área seleccionada
        if 'area' in self.data:
            try:
                area_id = int(self.data.get('area'))
                self.fields['oficina'].queryset = Oficina.objects.filter(area_id=area_id).order_by('nombre')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.area:
            # Si es edición, mostrar solo las oficinas del área de la instancia
            self.fields['oficina'].queryset = Oficina.objects.filter(
                area=self.instance.area
            ).order_by('nombre')
        else:
            # Si es creación nueva, no mostrar oficinas hasta que se seleccione un área
            self.fields['oficina'].queryset = Oficina.objects.none()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3">Datos Personales</h5>'),
            Row(
                Column('nombres', css_class='col-md-6'),
                Column('apellidos', css_class='col-md-6'),
            ),
            Row(
                Column('tipo_documento', css_class='col-md-4'),
                Column('numero_documento', css_class='col-md-8'),
            ),
            HTML('<hr class="my-4">'),
            HTML('<h5 class="mb-3">Datos Laborales</h5>'),
            Row(
                Column('modalidad', css_class='col-md-4'),
                Column('area', css_class='col-md-8'),
            ),
            Row(
                Column('oficina', css_class='col-md-8'),
                HTML('<div class="col-md-4">'),
                HTML('<label class="form-label">&nbsp;</label>'),
                HTML('<div class="form-text">Opcional: Solo para personal con oficina asignada</div>'),
                HTML('</div>'),
            ),
            Row(
                Column('cargo', css_class='col-md-12'),
            ),
            Submit('submit', 'Guardar', css_class='btn btn-primary mt-3')
        )
