from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML
from .models import CuentaContable, GrupoGenerico, Clase, Denominacion


# ==============================================================================
# FORMULARIOS PARA CUENTA CONTABLE
# ==============================================================================

class CuentaContableForm(forms.ModelForm):
    class Meta:
        model = CuentaContable
        fields = ['codigo', 'descripcion', 'tasa_depreciacion', 'vida_util_meses']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'tasa_depreciacion': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'vida_util_meses': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('codigo', css_class='col-md-3'),
                Column('descripcion', css_class='col-md-9'),
            ),
            Row(
                Column('tasa_depreciacion', css_class='col-md-6'),
                Column('vida_util_meses', css_class='col-md-6'),
            ),
            Submit('submit', 'Guardar', css_class='btn btn-primary')
        )


# ==============================================================================
# FORMULARIOS PARA CATÁLOGOS DE BIENES
# ==============================================================================

class GrupoGenericoForm(forms.ModelForm):
    class Meta:
        model = GrupoGenerico
        fields = ['nombre', 'descripcion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('nombre', css_class='col-md-8'),
                Column('activo', css_class='col-md-4'),
            ),
            Row(
                Column('descripcion', css_class='col-md-12'),
            ),
            Submit('submit', 'Guardar', css_class='btn btn-primary')
        )


class ClaseForm(forms.ModelForm):
    class Meta:
        model = Clase
        fields = ['nombre', 'grupo_generico', 'cuenta_contable', 'descripcion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'grupo_generico': forms.Select(attrs={'class': 'form-select'}),
            'cuenta_contable': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3">Datos de la Clase</h5>'),
            Row(
                Column('nombre', css_class='col-md-6'),
                Column('activo', css_class='col-md-6'),
            ),
            Row(
                Column('grupo_generico', css_class='col-md-6'),
                Column('cuenta_contable', css_class='col-md-6'),
            ),
            Row(
                Column('descripcion', css_class='col-md-12'),
            ),
            Submit('submit', 'Guardar', css_class='btn btn-primary')
        )


class DenominacionForm(forms.ModelForm):
    class Meta:
        model = Denominacion
        fields = [
            'nombre', 'grupo_generico', 'clase',
            'codigo_patrimonial_base', 'cuenta_contable',
            'activo', 'observaciones'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'grupo_generico': forms.Select(attrs={'class': 'form-select', 'id': 'id_grupo_generico'}),
            'clase': forms.Select(attrs={'class': 'form-select', 'id': 'id_clase'}),
            'codigo_patrimonial_base': forms.TextInput(attrs={'class': 'form-control'}),
            'cuenta_contable': forms.Select(attrs={'class': 'form-select', 'id': 'id_cuenta_contable'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar clases según el grupo genérico seleccionado
        if 'grupo_generico' in self.data:
            try:
                grupo_id = int(self.data.get('grupo_generico'))
                self.fields['clase'].queryset = Clase.objects.filter(grupo_generico_id=grupo_id, activo=True).order_by('nombre')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            # Si es edición, mostrar solo las clases del grupo genérico de la instancia
            self.fields['clase'].queryset = Clase.objects.filter(
                grupo_generico=self.instance.grupo_generico, activo=True
            ).order_by('nombre')
        else:
            # Si es creación nueva, no mostrar clases hasta que se seleccione un grupo genérico
            self.fields['clase'].queryset = Clase.objects.none()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3">Datos de la Denominación</h5>'),
            Row(
                Column('nombre', css_class='col-md-8'),
                Column('activo', css_class='col-md-4'),
            ),
            Row(
                Column('grupo_generico', css_class='col-md-6'),
                Column('clase', css_class='col-md-6'),
            ),
            HTML('<div id="clase-info" class="alert alert-info" style="display: none;">'
                 '<strong>Cuenta Contable sugerida:</strong> <span id="cuenta-contable-sugerida"></span>'
                 '</div>'),
            HTML('<hr class="my-4">'),
            HTML('<h5 class="mb-3">Código Patrimonial y Contabilidad</h5>'),
            Row(
                Column('codigo_patrimonial_base', css_class='col-md-6'),
                Column('cuenta_contable', css_class='col-md-6'),
            ),
            HTML('<hr class="my-4">'),
            HTML('<h5 class="mb-3">Información Adicional</h5>'),
            Row(
                Column('observaciones', css_class='col-md-12'),
            ),
            Submit('submit', 'Guardar', css_class='btn btn-primary mt-3')
        )
