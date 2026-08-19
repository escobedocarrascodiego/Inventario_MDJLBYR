from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
from organizacion.models import Local, Area, Oficina, UbicacionFisica
from personal.models import Personal
from catalogos.models import CuentaContable, Denominacion


# ==============================================================================
# 2.1. PARÁMETROS DEL SISTEMA
# ==============================================================================

class ParametroSistema(models.Model):
    anio_fiscal = models.PositiveIntegerField(unique=True)
    valor_uit = models.DecimalField(max_digits=10, decimal_places=2)
    divisor_umbral_depreciacion = models.PositiveIntegerField(default=4)
    es_activo = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.anio_fiscal} {'(Activo)' if self.es_activo else ''}".strip()

    def save(self, *args, **kwargs):
        if self.es_activo:
            ParametroSistema.objects.exclude(pk=self.pk).update(es_activo=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_current_config(cls):
        activo = cls.objects.filter(es_activo=True).first()
        if activo:
            return activo
        return cls.objects.order_by('-anio_fiscal').first()

    @classmethod
    def get_config_for_year(cls, year, disponibles=None):
        # `disponibles` permite pasar la lista de parámetros ya cargada (una sola
        # consulta) cuando se procesa en lote (reportes); sin ella, cada llamada
        # consulta la BD y en un reporte de N bienes son N viajes al servidor.
        if disponibles is None:
            disponibles = list(cls.objects.all())
        if not disponibles:
            return None
        if not year:
            return max(disponibles, key=lambda c: c.anio_fiscal)
        for config in disponibles:
            if config.anio_fiscal == year:
                return config
        # Fallback: si no existe fila para el año exacto, se devuelve la del año
        # MÁS CERCANO disponible (menor |anio_fiscal - year|). En empate de distancia
        # gana el año menor (más antiguo). NO se usa la fila activa (es_activo) ni la
        # más reciente: para el umbral de 1/4 UIT interesa la UIT histórica más próxima
        # al año de adquisición del bien.
        return min(disponibles, key=lambda c: (abs(c.anio_fiscal - year), c.anio_fiscal))

    class Meta:
        ordering = ['-anio_fiscal']
        verbose_name = "Parámetro del Sistema"
        verbose_name_plural = "Parámetros del Sistema"
        db_table = 'inventario_parametrosistema'


# ==============================================================================
# 4. MODELO PRINCIPAL: BIENES (PATRIMONIO)
# ==============================================================================

class Bien(models.Model):
    # Campo ID explícito para SQL Server
    id = models.BigAutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')
    
    # --- Datos de Identificación ---
    # La denominación ahora es una ForeignKey al catálogo (nullable para migración)
    denominacion = models.ForeignKey('catalogos.Denominacion', on_delete=models.PROTECT, related_name='bienes', verbose_name="Denominación", null=True, blank=True)
    
    # Estos campos se mantienen para compatibilidad pero se auto-completan desde denominacion
    # Se pueden hacer readonly o eliminarse después
    descripcion = models.CharField(max_length=300, verbose_name="Nombre o Denominación", editable=False, blank=True, null=True)
    grupo_generico = models.CharField(max_length=100, blank=True, null=True, editable=False)
    clase = models.CharField(max_length=100, blank=True, null=True, editable=False)
    
    # Código patrimonial: base + correlativo (ej: 74089950-0001)
    codigo_patrimonial_base = models.CharField(max_length=50, verbose_name="Cód. Patrimonial Base", editable=False, blank=True, null=True)
    correlativo = models.PositiveIntegerField(default=0, verbose_name="Correlativo")
    codigo_patrimonial = models.CharField(max_length=50, unique=True, verbose_name="Cód. Patrimonial Completo", editable=False, blank=True, null=True)
    codigo_interno = models.CharField(max_length=50, blank=True, null=True, verbose_name="Cód. Interno")
    
    # --- Contabilidad ---
    TIPO_CUENTA_CHOICES = [
        ('USO_ESTATAL', 'DE USO ESTATAL'),
        ('USO_PRIVADO', 'DE USO PRIVADO'),
    ]
    tipo_cuenta = models.CharField(max_length=20, choices=TIPO_CUENTA_CHOICES, default='USO_ESTATAL', verbose_name="Tipo de Cuenta")
    cuenta_contable = models.ForeignKey('catalogos.CuentaContable', on_delete=models.PROTECT, null=True, blank=True)
    tasa_depreciacion = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    vida_util_meses = models.PositiveIntegerField(null=True, blank=True)
    
    # --- Adquisición ---
    FORMA_ADQUISICION = [
        ('COMPRA', 'Compra'),
        ('DONACION', 'Donación'),
        ('FABRICACION', 'Fabricación'),
        ('PERMUTA', 'Permuta'),
        ('REPOSICION', 'Reposición'),
        ('REPRODUCCION', 'Reproducción'),
        ('SANEAMIENTO', 'Saneamiento'),
    ]
    forma_adquisicion = models.CharField(max_length=20, choices=FORMA_ADQUISICION)
    fecha_adquisicion = models.DateField()
    resolucion_alta = models.CharField(max_length=100, blank=True, null=True)
    fecha_pecosa = models.DateField(null=True, blank=True, verbose_name="Fecha de PECOSA / Salida")
    
    # --- Valores (Monetarios) ---
    valor_adquisicion = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    valor_neto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    
    # --- Estado ---
    ESTADO_BIEN = [
        ('NUEVO', 'Nuevo'),
        ('BUENO', 'Bueno'),
        ('REGULAR', 'Regular'),
        ('MALO', 'Malo'),
        ('CHADARRA', 'Chatarra'),
        ('RAEE', 'RAEE'),
        ('BAJA', 'De Baja'),
    ]
    estado = models.CharField(max_length=15, choices=ESTADO_BIEN, default='BUENO')

    # --- Situación (verificación de inventario: Normal / Faltante / Sobrante) ---
    SITUACION_CHOICES = [
        ('N', 'Normal'),
        ('F', 'Faltante'),
        ('S', 'Sobrante'),
    ]
    situacion = models.CharField(
        max_length=10,
        choices=SITUACION_CHOICES,
        default='N',
        verbose_name="Situación"
    )
    
    # --- Asignación / Ubicación ---
    # Aunque Local y Área se pueden deducir de la Oficina, en inventarios a veces
    # los bienes están en tránsito o en almacén sin oficina. Dejo los 3 como pediste.
    usuario_asignado = models.ForeignKey('personal.Personal', on_delete=models.SET_NULL, null=True, blank=True)
    
    local = models.ForeignKey('organizacion.Local', on_delete=models.PROTECT)
    area = models.ForeignKey('organizacion.Area', on_delete=models.PROTECT, null=True, blank=True)
    oficina = models.ForeignKey('organizacion.Oficina', on_delete=models.PROTECT, null=True, blank=True)
    ubicacion_fisica = models.ForeignKey('organizacion.UbicacionFisica', on_delete=models.PROTECT, null=True, blank=True)

    # ==========================================================================
    # DETALLES TÉCNICOS "MALEABLES" (Polimorfismo Simple)
    # ==========================================================================
    
    # Campos comunes a casi todos los bienes tecnológicos/mecánicos
    marca = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    serie = models.CharField(max_length=100, blank=True, null=True) # Común en CPUs, Monitores, Laptops
    dimension = models.CharField(max_length=100, blank=True, null=True, verbose_name="Dimensión")
    
    # Campos Específicos de Vehículos (Se dejan null si es un CPU)
    placa = models.CharField(max_length=20, blank=True, null=True)
    numero_motor = models.CharField(max_length=50, blank=True, null=True)
    numero_chasis = models.CharField(max_length=50, blank=True, null=True)
    anio_fabricacion = models.PositiveIntegerField(blank=True, null=True, verbose_name="Año")
    
    # Campo "Comodín" para especificaciones extrañas
    # Aquí puedes guardar un JSON como texto si SQL Server te da problemas con JSON nativo
    # Ej: {"procesador": "i7", "ram": "16GB"}
    otros_detalles = models.TextField(blank=True, null=True, help_text="Especificaciones adicionales en formato texto")

    @classmethod
    def normalizar_situacion(cls, valor):
        """Convierte un valor libre (Excel/CSV) al código de situación N/F/S.

        Acepta el código ('F') o el nombre completo ('FALTANTE', 'Faltante').
        Cualquier otra cosa -vacío, valores antiguos tipo USO/DESUSO, basura-
        cae en 'N' (Normal), que es el estado por defecto del inventario.
        """
        texto = (valor or '').strip().upper()
        if texto.startswith('F'):
            return 'F'
        if texto.startswith('S'):
            return 'S'
        if texto in dict(cls.SITUACION_CHOICES):
            return texto
        return 'N'

    def _fecha_inicio_depreciacion(self):
        """Fecha desde la que se cuenta la depreciación.
        COALESCE(fecha_pecosa, fecha_adquisicion): la PECOSA (puesta en uso) tiene
        prioridad; si no existe se usa la fecha de adquisición. Si faltan ambas,
        devuelve None y el bien no se deprecia. (CAMBIO 3)"""
        return self.fecha_pecosa or self.fecha_adquisicion

    def _anio_base_umbral(self):
        """Año cuya UIT se usa para el umbral de 1/4 UIT (Directiva 005-2016-EF/51.01):
        el año de ADQUISICIÓN del bien. Si no hay fecha_adquisicion se usa el año de la
        PECOSA. Si faltan ambas devuelve None (no se puede depreciar). (CAMBIO 1)"""
        if self.fecha_adquisicion:
            return self.fecha_adquisicion.year
        if self.fecha_pecosa:
            return self.fecha_pecosa.year
        return None

    def _meses_transcurridos_desde_pecosa(self, fecha_corte=None):
        # La depreciación arranca en COALESCE(fecha_pecosa, fecha_adquisicion). (CAMBIO 3)
        fecha_inicio = self._fecha_inicio_depreciacion()
        if not fecha_inicio:
            return 0
        inicio_mes_siguiente = (fecha_inicio.replace(day=1) + relativedelta(months=1))
        corte = fecha_corte.date() if hasattr(fecha_corte, 'date') else fecha_corte
        if corte is None:
            corte = timezone.now().date()
        if corte < inicio_mes_siguiente:
            return 0
        delta = relativedelta(corte, inicio_mes_siguiente)
        return (delta.years * 12) + delta.months

    def calcular_depreciacion(self, fecha_corte=None, parametros=None):
        """FUENTE ÚNICA del cálculo de depreciación (Directiva N° 005-2016-EF/51.01).

        Devuelve un dict con todos los componentes para que el modelo, el reporte PDF
        y el Excel reutilicen la misma lógica sin duplicar fórmulas. Claves:
          depreciable (bool), motivo_no_depreciable (str|None), fecha_inicio (date|None),
          anio_base_uit (int|None), umbral (Decimal|None), tasa (Decimal|None),
          meses (int), cuota_mensual (Decimal), depreciacion_acumulada (Decimal),
          valor_neto (Decimal).
        """
        corte = fecha_corte.date() if hasattr(fecha_corte, 'date') else fecha_corte
        if corte is None:
            corte = timezone.now().date()

        fecha_inicio = self._fecha_inicio_depreciacion()
        anio_base = self._anio_base_umbral()
        resultado = {
            'depreciable': False,
            'motivo_no_depreciable': None,
            'fecha_inicio': fecha_inicio,
            'anio_base_uit': anio_base,
            'umbral': None,
            'tasa': None,
            'meses': 0,
            'cuota_mensual': Decimal('0.00'),
            'depreciacion_acumulada': Decimal('0.00'),
            'valor_neto': self.valor_adquisicion,
        }

        # Sin fecha de inicio (ni PECOSA ni adquisición) no se puede depreciar. (CAMBIO 3)
        if fecha_inicio is None or anio_base is None:
            resultado['motivo_no_depreciable'] = 'Sin fecha de adquisición ni PECOSA'
            return resultado

        # --- Umbral de 1/4 UIT con la UIT del AÑO DE ADQUISICIÓN (CAMBIO 1) ---
        # `parametros`: lista de ParametroSistema precargada por el llamador para
        # evitar una consulta a la BD por cada bien en procesos por lote (reportes).
        config = ParametroSistema.get_config_for_year(anio_base, disponibles=parametros)
        valor_uit = config.valor_uit if config else Decimal('5500.00')
        divisor_umbral = (config.divisor_umbral_depreciacion if config else 4) or 4
        umbral = valor_uit / Decimal(str(divisor_umbral))
        resultado['umbral'] = umbral
        if self.valor_adquisicion <= umbral:
            resultado['motivo_no_depreciable'] = f'≤ 1/4 UIT del año {anio_base}'
            return resultado

        # --- Tasa (NO usa UIT; idéntico a antes) ---
        tasa = self.tasa_depreciacion
        if tasa is None and self.cuenta_contable:
            tasa = self.cuenta_contable.tasa_depreciacion
        if not tasa:
            resultado['motivo_no_depreciable'] = 'Sin tasa de depreciación'
            return resultado
        resultado['tasa'] = tasa

        # --- Depreciación lineal con piso de S/ 1.00 (idéntico a antes) ---
        meses = self._meses_transcurridos_desde_pecosa(corte)
        cuota_mensual = (self.valor_adquisicion * (tasa / 100)) / 12
        cuota_mensual = cuota_mensual.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
        valor_neto = max(self.valor_adquisicion - cuota_mensual * meses, Decimal('1.00'))
        # La acumulada se acota al piso para que (acumulada + valor_neto) = adquisición.
        depreciacion_acumulada = self.valor_adquisicion - valor_neto
        resultado.update({
            'depreciable': True,
            'meses': meses,
            'cuota_mensual': cuota_mensual,
            'depreciacion_acumulada': depreciacion_acumulada,
            'valor_neto': valor_neto,
        })
        return resultado

    def valor_neto_en(self, fecha_corte=None):
        return self.calcular_depreciacion(fecha_corte)['valor_neto']

    @property
    def valor_neto_actualizado(self):
        return self.valor_neto_en()

    def save(self, *args, **kwargs):
        """Auto-completa campos desde la denominación seleccionada"""
        if self.denominacion:
            # Auto-completar desde denominación
            self.descripcion = self.denominacion.nombre
            self.grupo_generico = self.denominacion.grupo_generico.nombre
            self.clase = self.denominacion.clase.nombre
            self.codigo_patrimonial_base = self.denominacion.codigo_patrimonial_base
            # tipo_cuenta NO se auto-completa desde denominación, se selecciona manualmente en el formulario
            # La cuenta contable solo se toma de la denominación cuando el bien
            # aún no tiene una asignada; si el usuario la cambió manualmente
            # (p. ej. a cuentas de orden por ser <= 1/4 UIT) se respeta su elección.
            if not self.cuenta_contable_id:
                self.cuenta_contable = self.denominacion.cuenta_contable
            
            # Generar código patrimonial completo si no existe
            if not self.codigo_patrimonial or self.correlativo == 0:
                # Obtener el último correlativo para esta denominación
                ultimo_bien = Bien.objects.filter(
                    denominacion=self.denominacion
                ).exclude(pk=self.pk).order_by('-correlativo').first()
                
                if ultimo_bien:
                    self.correlativo = ultimo_bien.correlativo + 1
                else:
                    self.correlativo = 1
                
                # Formato: BASE-CORRELATIVO (ej: 74089950-0001)
                if self.codigo_patrimonial_base:
                    self.codigo_patrimonial = f"{self.codigo_patrimonial_base}{self.correlativo:04d}"
        else:
            # Si no hay denominación, mantener valores existentes o usar valores por defecto
            # Esto es para compatibilidad con registros antiguos
            if not self.descripcion:
                self.descripcion = "Sin denominación asignada"
            if not self.codigo_patrimonial and self.codigo_patrimonial_base:
                if self.correlativo == 0:
                    self.correlativo = 1
                self.codigo_patrimonial = f"{self.codigo_patrimonial_base}{self.correlativo:04d}"

        if self.cuenta_contable:
            if self.tasa_depreciacion is None and self.cuenta_contable.tasa_depreciacion is not None:
                self.tasa_depreciacion = self.cuenta_contable.tasa_depreciacion
            if self.vida_util_meses is None and self.cuenta_contable.vida_util_meses is not None:
                self.vida_util_meses = self.cuenta_contable.vida_util_meses

        self.valor_neto = self.valor_neto_actualizado
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo_patrimonial} - {self.descripcion}"

    class Meta:
        verbose_name_plural = "Bienes"
        db_table = 'inventario_bien'
        indexes = [
            models.Index(fields=['codigo_patrimonial']),
            models.Index(fields=['estado']),
            # Índices compuestos útiles para listados y filtros frecuentes
            models.Index(fields=['codigo_patrimonial', 'estado']),
            models.Index(fields=['estado', 'situacion']),
            models.Index(fields=['fecha_adquisicion']),
            models.Index(fields=['cuenta_contable']),
            models.Index(fields=['usuario_asignado']),
            # Índice de COBERTURA para el reporte por cuentas contables.
            # El GROUP BY por cuenta_contable con SUM(valor_adquisicion/valor_neto)
            # se resuelve leyendo solo este índice (estrecho) en vez de escanear
            # toda la tabla de bienes (que tiene 30+ columnas). 'estado' permite
            # excluir las bajas y el id (PK) ya viene incluido para el COUNT.
            models.Index(
                fields=['cuenta_contable', 'estado'],
                include=['valor_adquisicion', 'valor_neto'],
                name='bien_cuenta_cob_idx',
            ),
        ]


# ==============================================================================
# 4.1. HISTÓRICO DE DEPRECIACIÓN
# ==============================================================================

def validar_cierre_anterior(anio):
    """Valida la correlatividad de cierre fiscal."""
    primer_anio = ParametroSistema.objects.order_by('anio_fiscal').values_list('anio_fiscal', flat=True).first()
    if primer_anio is None:
        return
    if anio == primer_anio:
        return
    existe_cierre_anterior = HistoricoDepreciacion.objects.filter(anio_fiscal=anio - 1).exists()
    if not existe_cierre_anterior:
        raise ValidationError(f"No se puede cerrar el año {anio} sin antes haber cerrado el año {anio - 1}")


class HistoricoDepreciacion(models.Model):
    bien = models.ForeignKey(Bien, on_delete=models.PROTECT, related_name='historicos')
    anio_fiscal = models.PositiveIntegerField()
    valor_adquisicion_h = models.DecimalField(max_digits=12, decimal_places=2)
    depreciacion_acumulada_h = models.DecimalField(max_digits=12, decimal_places=2)
    valor_neto_h = models.DecimalField(max_digits=12, decimal_places=2)
    estado_h = models.CharField(max_length=15, choices=Bien.ESTADO_BIEN)
    oficina_h = models.CharField(max_length=200, blank=True, null=True)
    usuario_h = models.CharField(max_length=200, blank=True, null=True)
    fecha_cierre = models.DateTimeField()

    def __str__(self):
        return f"{self.bien.codigo_patrimonial} - {self.anio_fiscal}"

    class Meta:
        verbose_name = "Histórico de Depreciación"
        verbose_name_plural = "Históricos de Depreciación"
        ordering = ['-anio_fiscal', 'bien']
        unique_together = ('bien', 'anio_fiscal')
        db_table = 'inventario_historicodepreciacion'
