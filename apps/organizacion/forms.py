from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML, Div
from .models import Entidad, Local, Area, Oficina, UbicacionFisica


# ==============================================================================
# FORMULARIOS PARA ENTIDAD
# ==============================================================================

class EntidadForm(forms.ModelForm):
    class Meta:
        model = Entidad
        fields = ['nombre', 'ruc']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'ruc': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('nombre', css_class='col-md-8'),
                Column('ruc', css_class='col-md-4'),
            ),
            Submit('submit', 'Guardar', css_class='btn btn-primary')
        )


# ==============================================================================
# FORMULARIOS PARA LOCAL
# ==============================================================================

class LocalForm(forms.ModelForm):
    class Meta:
        model = Local
        fields = [
            'entidad', 'nombre', 'tipo_propiedad', 'direccion', 
            'area_m2', 'numero', 'manzana', 'lote',
            'departamento', 'provincia', 'distrito'
        ]
        widgets = {
            'entidad': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_propiedad': forms.Select(attrs={'class': 'form-select'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'area_m2': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'numero': forms.TextInput(attrs={'class': 'form-control'}),
            'manzana': forms.TextInput(attrs={'class': 'form-control'}),
            'lote': forms.TextInput(attrs={'class': 'form-control'}),
            'departamento': forms.TextInput(attrs={'class': 'form-control'}),
            'provincia': forms.TextInput(attrs={'class': 'form-control'}),
            'distrito': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('entidad', css_class='col-md-6'),
                Column('nombre', css_class='col-md-6'),
            ),
            Row(
                Column('tipo_propiedad', css_class='col-md-4'),
                Column('direccion', css_class='col-md-8'),
            ),
            Row(
                Column('area_m2', css_class='col-md-3'),
                Column('numero', css_class='col-md-3'),
                Column('manzana', css_class='col-md-3'),
                Column('lote', css_class='col-md-3'),
            ),
            Row(
                Column('departamento', css_class='col-md-4'),
                Column('provincia', css_class='col-md-4'),
                Column('distrito', css_class='col-md-4'),
            ),
            Submit('submit', 'Guardar', css_class='btn btn-primary')
        )


# ==============================================================================
# FORMULARIOS PARA ÁREA
# ==============================================================================

class AreaForm(forms.ModelForm):
    class Meta:
        model = Area
        fields = ['local', 'nombre', 'siglas']
        widgets = {
            'local': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'siglas': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('local', css_class='col-md-6'),
                Column('nombre', css_class='col-md-4'),
                Column('siglas', css_class='col-md-2'),
            ),
            Submit('submit', 'Guardar', css_class='btn btn-primary')
        )


# ==============================================================================
# FORMULARIOS PARA OFICINA
# ==============================================================================

class OficinaForm(forms.ModelForm):
    class Meta:
        model = Oficina
        fields = ['area', 'nombre', 'codigo_interno']
        widgets = {
            'area': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_interno': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('area', css_class='col-md-6'),
                Column('nombre', css_class='col-md-4'),
                Column('codigo_interno', css_class='col-md-2'),
            ),
            Submit('submit', 'Guardar', css_class='btn btn-primary')
        )


# ==============================================================================
# FORMULARIOS PARA UBICACIÓN FÍSICA
# ==============================================================================

class UbicacionFisicaForm(forms.ModelForm):
    class Meta:
        model = UbicacionFisica
        fields = ['local', 'area', 'oficina', 'piso', 'detalle', 'activo']
        widgets = {
            'local': forms.Select(attrs={'class': 'form-select', 'id': 'id_local'}),
            'area': forms.Select(attrs={'class': 'form-select', 'id': 'id_area'}),
            'oficina': forms.Select(attrs={'class': 'form-select', 'id': 'id_oficina'}),
            'piso': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'detalle': forms.TextInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['oficina'].required = False
        self.fields['oficina'].empty_label = "Seleccione una oficina (opcional)"
        self.fields['piso'].required = False
        self.fields['area'].queryset = Area.objects.all().order_by('nombre')

        if 'area' in self.data:
            try:
                area_id = int(self.data.get('area'))
                self.fields['oficina'].queryset = Oficina.objects.filter(area_id=area_id).order_by('nombre')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.area:
            self.fields['oficina'].queryset = Oficina.objects.filter(area=self.instance.area).order_by('nombre')
        else:
            self.fields['oficina'].queryset = Oficina.objects.none()

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('local', css_class='col-md-4'),
                Column('area', css_class='col-md-4'),
                Column('oficina', css_class='col-md-4'),
            ),
            Row(
                Column('piso', css_class='col-md-3'),
                Column('detalle', css_class='col-md-7'),
                Column('activo', css_class='col-md-2'),
            ),
            Submit('submit', 'Guardar', css_class='btn btn-primary')
        )
