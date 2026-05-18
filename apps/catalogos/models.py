from django.db import models


# ==============================================================================
# 3. CATÁLOGOS CONTABLES
# ==============================================================================

# TipoCuenta eliminado - ahora es un campo simple en Bien

class CuentaContable(models.Model):
    codigo = models.CharField(max_length=50, unique=True) # Ej: 1503.0101
    descripcion = models.CharField(max_length=255) # Ej: VEHICULOS PARA TRANSPORTE
    tasa_depreciacion = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    vida_util_meses = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"

    class Meta:
        ordering = ['codigo']
        verbose_name = "Cuenta Contable"
        verbose_name_plural = "Cuentas Contables"
        db_table = 'inventario_cuentacontable'


# ==============================================================================
# 3.1. CATÁLOGOS DE BIENES (Grupo Genérico, Clase, Denominación)
# ==============================================================================

class GrupoGenerico(models.Model):
    """Catálogo de Grupos Genéricos (ej: OFICINA, VEHICULO, MAQUINARIA)"""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Grupo Genérico"
        verbose_name_plural = "Grupos Genéricos"
        ordering = ['nombre']
        db_table = 'inventario_grupogenerico'


class Clase(models.Model):
    """
    Catálogo de Clases (ej: AERONAVE, VEHÍCULO, CPU).
    Cada clase pertenece a un Grupo Genérico y tiene asociada una Cuenta Contable por defecto.
    """
    nombre = models.CharField(max_length=100)
    grupo_generico = models.ForeignKey(GrupoGenerico, on_delete=models.PROTECT, related_name='clases', null=True, blank=True, help_text="Grupo genérico al que pertenece esta clase")
    cuenta_contable = models.ForeignKey(CuentaContable, on_delete=models.PROTECT, related_name='clases', null=True, blank=True, help_text="Cuenta contable por defecto para esta clase")
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        if self.grupo_generico:
            return f"{self.nombre} ({self.grupo_generico.nombre})"
        return self.nombre

    class Meta:
        verbose_name = "Clase"
        verbose_name_plural = "Clases"
        ordering = ['grupo_generico', 'nombre']
        # unique_together solo si grupo_generico no es null
        # Se manejará a nivel de aplicación o en una migración posterior
        db_table = 'inventario_clase'


class Denominacion(models.Model):
    """
    Catálogo de Denominaciones de Bienes.
    Cada denominación está vinculada a un Grupo Genérico, Clase y Cuenta Contable.
    La cuenta contable puede auto-completarse desde la clase, pero es personalizable.
    """
    nombre = models.CharField(max_length=300, unique=True, verbose_name="Denominación")
    grupo_generico = models.ForeignKey(GrupoGenerico, on_delete=models.PROTECT, related_name='denominaciones')
    clase = models.ForeignKey(Clase, on_delete=models.PROTECT, related_name='denominaciones')
    
    # Código patrimonial base (se usará para generar el código completo con correlativo)
    codigo_patrimonial_base = models.CharField(max_length=50, verbose_name="Código Patrimonial Base")
    
    # Cuenta contable asociada (puede auto-completarse desde clase, pero es personalizable)
    cuenta_contable = models.ForeignKey(CuentaContable, on_delete=models.PROTECT, related_name='denominaciones')
    
    activo = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Denominación"
        verbose_name_plural = "Denominaciones"
        ordering = ['nombre']
        db_table = 'inventario_denominacion'
