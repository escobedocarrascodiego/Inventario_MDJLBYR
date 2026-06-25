from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML, Div
from organizacion.models import UbicacionFisica, Oficina, Local, Area
from personal.models import Personal
from .models import Bien


# ==============================================================================
# FORMULARIOS PARA BIEN
# ==============================================================================

class BienForm(forms.ModelForm):
    # Campo de búsqueda para denominación (no se guarda, solo para búsqueda)
    buscar_denominacion = forms.CharField(
        required=False,
        label="Escriba el nombre del bien a buscar:",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_buscar_denominacion',
            'placeholder': 'Buscar denominación...',
            'autocomplete': 'off'
        })
    )

    # Cantidad de bienes a registrar (no se guarda en el modelo). Si es > 1 se
    # crean N bienes idénticos, cada uno con su propio código patrimonial
    # correlativo. Se usa en el "Ingreso X Grupo".
    cantidad = forms.IntegerField(
        required=False,
        min_value=1,
        initial=1,
        label="Cantidad",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_cantidad',
            'min': '1',
            'value': '1',
        })
    )

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if not cantidad or cantidad < 1:
            return 1
        return cantidad
    
    class Meta:
        model = Bien
        fields = [
            # Identificación - ahora usamos denominacion
            'denominacion',
            'codigo_interno',
            # Contabilidad - ahora editables
            'tipo_cuenta', 'cuenta_contable', 'tasa_depreciacion', 'vida_util_meses',
            # Adquisición
            'forma_adquisicion', 'fecha_adquisicion', 'resolucion_alta', 'fecha_pecosa',
            # Valores
            'valor_adquisicion', 'valor_neto',
            # Estado
            'estado', 'situacion',
            # Asignación
            'usuario_asignado', 'local', 'area', 'oficina', 'ubicacion_fisica',
            # Detalles técnicos
            'marca', 'modelo', 'color', 'serie', 'dimension',
            # Vehículos
            'placa', 'numero_motor', 'numero_chasis', 'anio_fabricacion',
            # Otros
            'otros_detalles'
        ]
        widgets = {
            'denominacion': forms.HiddenInput(),  # Se oculta, se selecciona desde el buscador
            'codigo_interno': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_cuenta': forms.Select(attrs={'class': 'form-select'}),
            'cuenta_contable': forms.Select(attrs={'class': 'form-select'}),
            'tasa_depreciacion': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'vida_util_meses': forms.NumberInput(attrs={'class': 'form-control'}),
            'forma_adquisicion': forms.Select(attrs={'class': 'form-select'}),
            'fecha_adquisicion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'resolucion_alta': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_pecosa': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'valor_adquisicion': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_neto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'situacion': forms.Select(attrs={'class': 'form-select'}),
            'usuario_asignado': forms.Select(attrs={'class': 'form-select'}),
            'local': forms.Select(attrs={'class': 'form-select'}),
            'area': forms.Select(attrs={'class': 'form-select'}),
            'oficina': forms.Select(attrs={'class': 'form-select'}),
            'ubicacion_fisica': forms.Select(attrs={'class': 'form-select'}),
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control'}),
            'serie': forms.TextInput(attrs={'class': 'form-control'}),
            'dimension': forms.TextInput(attrs={'class': 'form-control'}),
            'placa': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_motor': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_chasis': forms.TextInput(attrs={'class': 'form-control'}),
            'anio_fabricacion': forms.NumberInput(attrs={'class': 'form-control'}),
            'otros_detalles': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si hay una instancia, establecer el valor inicial del buscador
        if self.instance and self.instance.pk and self.instance.denominacion:
            self.fields['buscar_denominacion'].initial = self.instance.denominacion.nombre

        self.fields['ubicacion_fisica'].required = False
        self.fields['ubicacion_fisica'].empty_label = "Seleccione ubicación física (opcional)"

        ubicacion_qs = UbicacionFisica.objects.none()
        oficina_id = (self.data.get('oficina') or '').strip()
        area_id = (self.data.get('area') or '').strip()
        if oficina_id.isdigit():
            ubicacion_qs = UbicacionFisica.objects.filter(oficina_id=int(oficina_id), activo=True).order_by('piso', 'detalle')
        elif area_id.isdigit():
            ubicacion_qs = UbicacionFisica.objects.filter(area_id=int(area_id), activo=True).order_by('piso', 'detalle')
        elif self.instance.pk:
            if self.instance.oficina_id:
                ubicacion_qs = UbicacionFisica.objects.filter(oficina_id=self.instance.oficina_id, activo=True).order_by('piso', 'detalle')
            elif self.instance.area_id:
                ubicacion_qs = UbicacionFisica.objects.filter(area_id=self.instance.area_id, activo=True).order_by('piso', 'detalle')
            elif self.instance.ubicacion_fisica_id:
                ubicacion_qs = UbicacionFisica.objects.filter(pk=self.instance.ubicacion_fisica_id)
        self.fields['ubicacion_fisica'].queryset = ubicacion_qs
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3"><i class="fas fa-search me-2"></i>Selección del Tipo de Bien</h5>'),
            Div(
                HTML('<label class="form-label">ESCRIBA EL NOMBRE DEL BIEN A BUSCAR:</label>'),
                Row(
                    Column('buscar_denominacion', css_class='col-md-10'),
                    Column(
                        HTML('<button type="button" class="btn btn-primary w-100" id="btn-buscar-denominacion"><i class="fas fa-search"></i></button>'),
                        css_class='col-md-2'
                    ),
                ),
                HTML('<div id="lista-denominaciones" class="mt-2" style="max-height: 200px; overflow-y: auto; border: 1px solid #ddd; display: none;"></div>'),
                css_class='mb-4'
            ),
            HTML('<hr class="my-4">'),
            HTML('<h5 class="mb-3">Datos del Bien</h5>'),
            Div(
                HTML('<div class="row mb-3">'),
                HTML('<div class="col-md-8">'),
                HTML('<label class="form-label">Denominación:</label>'),
                HTML('<input type="text" class="form-control" id="id_denominacion_display" readonly>'),
                HTML('</div>'),
                HTML('<div class="col-md-4">'),
                HTML('<label class="form-label">Cód. Patrimonial:</label>'),
                HTML('<input type="text" class="form-control" id="id_codigo_patrimonial_display" readonly>'),
                HTML('</div>'),
                HTML('</div>'),
                HTML('<div class="row mb-3">'),
                HTML('<div class="col-md-6">'),
                HTML('<label class="form-label">Grupo Genérico:</label>'),
                HTML('<input type="text" class="form-control" id="id_grupo_generico_display" readonly>'),
                HTML('</div>'),
                HTML('<div class="col-md-6">'),
                HTML('<label class="form-label">Clase:</label>'),
                HTML('<input type="text" class="form-control" id="id_clase_display" readonly>'),
                HTML('</div>'),
                HTML('</div>'),
                HTML('<div class="row mb-3">'),
                HTML('<div class="col-md-12">'),
                HTML('<label class="form-label">Código Interno:</label>'),
                Column('codigo_interno', css_class='col-md-12'),
                HTML('</div>'),
                HTML('</div>'),
                HTML('<div class="row mb-3">'),
                HTML('<div class="col-md-6">'),
                HTML('<label class="form-label">Tipo de Cuenta:</label>'),
                HTML('<input type="text" class="form-control" id="id_tipo_cuenta_display" readonly>'),
                HTML('</div>'),
                HTML('<div class="col-md-6">'),
                HTML('<label class="form-label">Cuenta Contable:</label>'),
                HTML('<input type="text" class="form-control" id="id_cuenta_contable_display" readonly>'),
                HTML('</div>'),
                HTML('</div>'),
            ),
            'denominacion',  # Campo oculto
            Row(
                Column('tasa_depreciacion', css_class='col-md-6'),
                Column('vida_util_meses', css_class='col-md-6'),
            ),
            HTML('<hr class="my-4">'),
            HTML('<h5 class="mb-3">Adquisición</h5>'),
            Row(
                Column('forma_adquisicion', css_class='col-md-4'),
                Column('fecha_adquisicion', css_class='col-md-4'),
                Column('resolucion_alta', css_class='col-md-4'),
            ),
            Row(
                Column('fecha_pecosa', css_class='col-md-4'),
            ),
            Row(
                Column('valor_adquisicion', css_class='col-md-6'),
                Column('valor_neto', css_class='col-md-6'),
            ),
            Row(
                Column('estado', css_class='col-md-12'),
            ),
            Row(
                Column('situacion', css_class='col-md-6'),
            ),
            HTML('<hr class="my-4">'),
            HTML('<h5 class="mb-3">Asignación y Ubicación</h5>'),
            Row(
                Column('usuario_asignado', css_class='col-md-6'),
                Column('local', css_class='col-md-6'),
            ),
            Row(
                Column('area', css_class='col-md-6'),
                Column('oficina', css_class='col-md-6'),
            ),
            HTML('<hr class="my-4">'),
            HTML('<h5 class="mb-3">Detalle Técnico</h5>'),
            Row(
                Column('marca', css_class='col-md-3'),
                Column('modelo', css_class='col-md-3'),
                Column('color', css_class='col-md-3'),
                Column('serie', css_class='col-md-3'),
            ),
            Row(
                Column('dimension', css_class='col-md-6'),
            ),
            HTML('<hr class="my-4">'),
            HTML('<h5 class="mb-3">Datos de Vehículo (si aplica)</h5>'),
            Row(
                Column('placa', css_class='col-md-3'),
                Column('numero_motor', css_class='col-md-3'),
                Column('numero_chasis', css_class='col-md-3'),
                Column('anio_fabricacion', css_class='col-md-3'),
            ),
            HTML('<hr class="my-4">'),
            HTML('<h5 class="mb-3">Información Adicional</h5>'),
            Row(
                Column('otros_detalles', css_class='col-md-12'),
            ),
            Submit('submit', 'Grabar', css_class='btn btn-primary mt-3')
        )


# ==============================================================================
# FORMULARIOS PARA GENERACIÓN DE ETIQUETAS
# ==============================================================================

class EtiquetaFiltroForm(forms.Form):
    """Formulario para filtrar bienes para generar etiquetas"""
    TIPO_GENERACION = [
        ('todos', 'Todos los Bienes Activos'),
        ('bien_especifico', 'Bien Específico'),
        ('por_usuario', 'Por Usuario Asignado'),
        ('por_local', 'Por Local'),
        ('por_area', 'Por Área'),
        ('por_oficina', 'Por Oficina'),
        ('por_resolucion', 'Por Orden de Compra / Resolución de Alta'),
        ('por_año', 'Por Año de Adquisición'),
    ]
    
    FORMATO_SALIDA = [
        ('zebra_zpl', 'Impresora Zebra ZT411 (ZPL)'),
        ('pdf', 'PDF'),
    ]

    tipo_generacion = forms.ChoiceField(
        choices=TIPO_GENERACION,
        label="Tipo de Generación",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_tipo_generacion'})
    )

    formato = forms.ChoiceField(
        choices=FORMATO_SALIDA,
        initial='zebra_zpl',
        label="Formato de salida",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_formato'}),
        help_text="ZPL imprime directo en la Zebra; PDF para vista/impresión común."
    )
    
    año = forms.IntegerField(
        required=False,
        label="Año",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_año',
            'min': '2000',
            'max': '2100',
            'placeholder': 'Ej: 2025'
        }),
        help_text="Año que aparecerá en la etiqueta (para búsqueda e impresión)"
    )
    
    bien = forms.ChoiceField(
        required=False,
        label="Bien Específico",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_bien',
            'data-ajax-url': '/ajax/buscar-bien-etiquetas/'
        })
    )

    usuario = forms.ChoiceField(
        required=False,
        label="Usuario Asignado",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_usuario',
            'data-ajax-url': '/ajax/anexo03/buscar-personal/'
        })
    )

    local = forms.ModelChoiceField(
        queryset=Local.objects.all(),
        required=False,
        label="Local",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_local'})
    )
    
    area = forms.ModelChoiceField(
        queryset=Area.objects.all(),
        required=False,
        label="Área",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_area'})
    )
    
    oficina = forms.ModelChoiceField(
        queryset=Oficina.objects.all(),
        required=False,
        label="Oficina",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_oficina'})
    )

    resolucion_alta = forms.ChoiceField(
        required=False,
        label="Orden de Compra / Resolución de Alta",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_resolucion_alta',
            'data-ajax-url': '/ajax/buscar-resolucion-etiquetas/'
        })
    )
    
    año_adquisicion = forms.IntegerField(
        required=False,
        label="Año de Adquisición",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_año_adquisicion',
            'min': '2000',
            'max': '2100',
            'placeholder': 'Filtrar por año de adquisición'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        bien_id = (self.data.get('bien') or self.initial.get('bien') or '').strip()
        choices = [('', 'Seleccione un bien')]
        if bien_id.isdigit():
            bien = Bien.objects.exclude(estado='BAJA').filter(id=int(bien_id)).first()
            if bien:
                codigo = bien.codigo_patrimonial or 'N/A'
                nombre = bien.denominacion.nombre if bien.denominacion else bien.descripcion or 'N/A'
                choices.append((str(bien.id), f"{codigo} - {nombre}"))
        self.fields['bien'].choices = choices

        # Precargar la opción del usuario seleccionado para que el ChoiceField
        # valide correctamente el valor enviado vía AJAX (Select dinámico).
        usuario_id = (self.data.get('usuario') or self.initial.get('usuario') or '').strip()
        usuario_choices = [('', 'Seleccione un usuario')]
        if usuario_id.isdigit():
            persona = Personal.objects.filter(id=int(usuario_id)).first()
            if persona:
                etiqueta = f"{persona.apellidos}, {persona.nombres} — DNI: {persona.numero_documento}"
                usuario_choices.append((str(persona.id), etiqueta))
        self.fields['usuario'].choices = usuario_choices

        # Precargar la opción de resolución/orden de compra elegida (es texto libre
        # del propio bien, así que el value de la opción es la misma cadena).
        resolucion_val = (self.data.get('resolucion_alta') or self.initial.get('resolucion_alta') or '').strip()
        resolucion_choices = [('', 'Seleccione una orden de compra / resolución')]
        if resolucion_val:
            resolucion_choices.append((resolucion_val, resolucion_val))
        self.fields['resolucion_alta'].choices = resolucion_choices

        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<h5 class="mb-3">Configuración de Generación de Etiquetas</h5>'),
            Row(
                Column('tipo_generacion', css_class='col-md-6'),
                Column('formato', css_class='col-md-6'),
            ),
            HTML('<div id="campo-año" class="mt-3">'),
            Row(
                Column('año', css_class='col-md-6'),
            ),
            HTML('</div>'),
            HTML('<div id="campo-bien" class="mt-3" style="display: none;">'),
            Row(
                Column(
                    HTML(
                        '<label class="form-label" for="bien-search">Buscar bien</label>'
                        '<div class="input-group">'
                        '<input type="text" id="bien-search" class="form-control" '
                        'placeholder="Buscar por código o nombre" autocomplete="off">'
                        '<button type="button" id="bien-search-btn" class="btn btn-primary">'
                        '<i class="fas fa-search me-1"></i>Buscar</button>'
                        '</div>'
                    ),
                    css_class='col-md-12'
                ),
            ),
            Row(
                Column('bien', css_class='col-md-12 mt-2'),
            ),
            HTML('</div>'),
            HTML('<div id="campo-usuario" class="mt-3" style="display: none;">'),
            Row(
                Column(
                    HTML(
                        '<label class="form-label" for="usuario-search">Buscar usuario</label>'
                        '<div class="input-group">'
                        '<input type="text" id="usuario-search" class="form-control" '
                        'placeholder="Buscar por apellidos, nombres o DNI" autocomplete="off">'
                        '<button type="button" id="usuario-search-btn" class="btn btn-primary">'
                        '<i class="fas fa-search me-1"></i>Buscar</button>'
                        '</div>'
                    ),
                    css_class='col-md-12'
                ),
            ),
            Row(
                Column('usuario', css_class='col-md-12 mt-2'),
            ),
            HTML('</div>'),
            HTML('<div id="campo-local" class="mt-3" style="display: none;">'),
            Row(
                Column('local', css_class='col-md-12'),
            ),
            HTML('</div>'),
            HTML('<div id="campo-area" class="mt-3" style="display: none;">'),
            Row(
                Column('area', css_class='col-md-12'),
            ),
            HTML('</div>'),
            HTML('<div id="campo-oficina" class="mt-3" style="display: none;">'),
            Row(
                Column('oficina', css_class='col-md-12'),
            ),
            HTML('</div>'),
            HTML('<div id="campo-resolucion" class="mt-3" style="display: none;">'),
            Row(
                Column(
                    HTML(
                        '<label class="form-label" for="resolucion-search">Buscar orden de compra / resolución de alta</label>'
                        '<div class="input-group">'
                        '<input type="text" id="resolucion-search" class="form-control" '
                        'placeholder="Escriba parte de la orden de compra o resolución" autocomplete="off">'
                        '<button type="button" id="resolucion-search-btn" class="btn btn-primary">'
                        '<i class="fas fa-search me-1"></i>Buscar</button>'
                        '</div>'
                    ),
                    css_class='col-md-12'
                ),
            ),
            Row(
                Column('resolucion_alta', css_class='col-md-12 mt-2'),
            ),
            HTML('</div>'),
            HTML('<div id="campo-año-adquisicion" class="mt-3" style="display: none;">'),
            Row(
                Column('año_adquisicion', css_class='col-md-6'),
            ),
            HTML('</div>'),
            HTML('<div class="alert alert-info mt-3">'),
            HTML('<i class="fas fa-info-circle me-2"></i>'),
            HTML('<strong>Nota:</strong> El campo "Año" es obligatorio y aparecerá en todas las etiquetas. '
                 'Al continuar verá la lista de bienes para marcar exactamente cuáles imprimir.'),
            HTML('</div>'),
            Submit('submit', 'Buscar y seleccionar bienes', css_class='btn btn-primary mt-3')
        )

    def clean_bien(self):
        bien_id = (self.cleaned_data.get('bien') or '').strip()
        if not bien_id:
            return None
        if not bien_id.isdigit():
            raise forms.ValidationError("Seleccione un bien válido.")
        bien = Bien.objects.exclude(estado='BAJA').filter(id=int(bien_id)).first()
        if not bien:
            raise forms.ValidationError("Seleccione un bien válido.")
        return bien

    def clean_usuario(self):
        usuario_id = (self.cleaned_data.get('usuario') or '').strip()
        if not usuario_id:
            return None
        if not usuario_id.isdigit():
            raise forms.ValidationError("Seleccione un usuario válido.")
        persona = Personal.objects.filter(id=int(usuario_id)).first()
        if not persona:
            raise forms.ValidationError("Seleccione un usuario válido.")
        return persona

    def clean_resolucion_alta(self):
        valor = (self.cleaned_data.get('resolucion_alta') or '').strip()
        return valor or None


# ==============================================================================
# FORMULARIOS PARA BAJA DE BIENES (búsqueda)
# ==============================================================================

class BuscarBienForm(forms.Form):
    """Formulario para buscar un bien antes de registrar su baja"""
    TIPO_BUSQUEDA = [
        ('codigo_patrimonial', 'Código Patrimonial'),
        ('codigo_interno', 'Código Interno'),
        ('denominacion', 'Denominación'),
    ]
    
    tipo_busqueda = forms.ChoiceField(
        choices=TIPO_BUSQUEDA,
        label="Búsqueda Por:",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_tipo_busqueda'})
    )
    
    valor_busqueda = forms.CharField(
        max_length=200,
        label="Valor de Búsqueda",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_valor_busqueda',
            'placeholder': 'Ingrese el valor a buscar...'
        })
    )
