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
    def get_config_for_year(cls, year):
        if not year:
            return cls.objects.order_by('-anio_fiscal').first()
        config = cls.objects.filter(anio_fiscal=year).first()
        if config:
            return config
        return cls.objects.order_by('anio_fiscal').first()

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

    # --- Situación Administrativa ---
    SITUACION_CHOICES = [
        ('NORMAL', 'Normal'),
        ('SOBRANTE', 'Sobrante'),
        ('FALTANTE', 'Faltante'),
    ]
    situacion = models.CharField(
        max_length=10,
        choices=SITUACION_CHOICES,
        default='NORMAL',
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

    def _meses_transcurridos_desde_pecosa(self, fecha_corte=None):
        if not self.fecha_pecosa:
            return 0
        inicio_mes_siguiente = (self.fecha_pecosa.replace(day=1) + relativedelta(months=1))
        corte = fecha_corte.date() if hasattr(fecha_corte, 'date') else fecha_corte
        if corte is None:
            corte = timezone.now().date()
        if corte < inicio_mes_siguiente:
            return 0
        delta = relativedelta(corte, inicio_mes_siguiente)
        return (delta.years * 12) + delta.months

    def valor_neto_en(self, fecha_corte=None):
        if not self.fecha_pecosa:
            return self.valor_adquisicion

        corte = fecha_corte.date() if hasattr(fecha_corte, 'date') else fecha_corte
        if corte is None:
            corte = timezone.now().date()

        config = ParametroSistema.get_config_for_year(corte.year)
        valor_uit = config.valor_uit if config else Decimal('5500.00')
        divisor_umbral = config.divisor_umbral_depreciacion if config else 4
        if not divisor_umbral:
            divisor_umbral = 4
        umbral_depreciacion = valor_uit / Decimal(str(divisor_umbral))

        if self.valor_adquisicion <= umbral_depreciacion:
            return self.valor_adquisicion

        tasa = self.tasa_depreciacion
        if tasa is None and self.cuenta_contable:
            tasa = self.cuenta_contable.tasa_depreciacion

        if not tasa:
            return self.valor_adquisicion

        meses_transcurridos = self._meses_transcurridos_desde_pecosa(corte)
        depreciacion_mensual = (self.valor_adquisicion * (tasa / 100)) / 12
        depreciacion_mensual = depreciacion_mensual.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
        depreciacion_acumulada = depreciacion_mensual * meses_transcurridos
        valor_neto = self.valor_adquisicion - depreciacion_acumulada
        return max(valor_neto, Decimal('1.00'))

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
