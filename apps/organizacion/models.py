from django.db import models
from django.core.exceptions import ValidationError


# ==============================================================================
# 1. MODELOS JERÁRQUICOS (Estructura Orgánica)
# ==============================================================================

class Entidad(models.Model):
    nombre = models.CharField(max_length=200, default="Municipalidad Distrital de José Luis Bustamante y Rivero")
    ruc = models.CharField(max_length=11, blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name_plural = "Entidades"
        db_table = 'inventario_entidad'


class Local(models.Model):
    TIPO_PROPIEDAD = [
        ('ESTATAL', 'Estatal'),
        ('PRIVADA', 'Privada'),
        ('ALQUILADO', 'Alquilado'),
    ]

    entidad = models.ForeignKey(Entidad, on_delete=models.CASCADE, related_name='locales')
    nombre = models.CharField(max_length=200)  # Ej: Palacio Municipal, Sede Adulto Mayor
    tipo_propiedad = models.CharField(max_length=20, choices=TIPO_PROPIEDAD, default='ESTATAL')
    
    # Ubicación
    direccion = models.CharField(max_length=255)
    area_m2 = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Área (m2)")
    numero = models.CharField(max_length=20, blank=True, null=True, verbose_name="N°")
    manzana = models.CharField(max_length=10, blank=True, null=True, verbose_name="Mz")
    lote = models.CharField(max_length=10, blank=True, null=True, verbose_name="Lte")
    
    # Ubicación Geográfica (Ubigeo simple)
    departamento = models.CharField(max_length=100, default="Arequipa")
    provincia = models.CharField(max_length=100, default="Arequipa")
    distrito = models.CharField(max_length=100, default="José Luis Bustamante y Rivero")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name_plural = "Locales"
        db_table = 'inventario_local'


class Area(models.Model):
    local = models.ForeignKey(Local, on_delete=models.PROTECT, related_name='areas')
    nombre = models.CharField(max_length=200)  # Ej: Administración Financiera
    siglas = models.CharField(max_length=20, blank=True, null=True)  # Ej: AF

    def __str__(self):
        return f"{self.nombre} ({self.siglas})" if self.siglas else self.nombre

    class Meta:
        db_table = 'inventario_area'


class Oficina(models.Model):
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name='oficinas')
    nombre = models.CharField(max_length=200)  # Ej: Oficina de Tecnologías de la Info.
    codigo_interno = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} - {self.area.siglas}"

    class Meta:
        db_table = 'inventario_oficina'


# ==============================================================================
# 1.1. UBICACIONES FÍSICAS
# ==============================================================================

class UbicacionFisica(models.Model):
    """Ubicaciones físicas reales (piso, archivo, ambiente, etc.)."""
    local = models.ForeignKey(Local, on_delete=models.PROTECT, related_name='ubicaciones_fisicas')
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name='ubicaciones_fisicas')
    oficina = models.ForeignKey(Oficina, on_delete=models.PROTECT, related_name='ubicaciones_fisicas', null=True, blank=True)
    piso = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Piso")
    detalle = models.CharField(max_length=200, blank=True, null=True, verbose_name="Detalle")
    activo = models.BooleanField(default=True)

    def clean(self):
        if self.oficina and self.oficina.area_id != self.area_id:
            raise ValidationError("La oficina seleccionada no pertenece al área indicada.")

    def __str__(self):
        partes = []
        if self.area:
            partes.append(self.area.nombre)
        if self.oficina:
            partes.append(self.oficina.nombre)
        if self.piso is not None:
            partes.append(f"Piso {self.piso}")
        if self.detalle:
            partes.append(self.detalle)
        base = " - ".join(p for p in partes if p)
        local_nombre = self.local.nombre if self.local else "Sin local"
        return f"{base} ({local_nombre})" if base else f"Ubicación física ({local_nombre})"

    class Meta:
        verbose_name = "Ubicación Física"
        verbose_name_plural = "Ubicaciones Físicas"
        ordering = ['local__nombre', 'area__nombre', 'oficina__nombre', 'piso', 'detalle']
        db_table = 'inventario_ubicacionfisica'
