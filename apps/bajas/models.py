from django.db import models


# ==============================================================================
# 5. MODELO DE BAJA DE BIENES
# ==============================================================================

class BajaBien(models.Model):
    """Modelo para registrar la baja de bienes patrimoniales"""
    
    CAUSAL_BAJA_CHOICES = [
        ('DESTRUCCION_SINIESTRO', 'DESTRUCCIÓN O SINIESTRO'),
        ('ENFERMEDAD_INCURABLE', 'ENFERMEDAD INCURABLE'),
        ('ESTADO_EXCEDENCIA', 'ESTADO DE EXCEDENCIA'),
        ('FALLECIMIENTO_MUERTE', 'FALLECIMIENTO O MUERTE'),
        ('FALTANTE_SANEAMIENTO', 'FALTANTE - SANEAMIENTO'),
        ('LESION_GRAVE', 'LESION GRAVE'),
        ('MANTENIMIENTO_REPARACION', 'MANTENIMIENTO O REPARACIÓN ONEROSA'),
        ('OBSOLENCIA_TECNICA', 'OBSOLENCIA TECNICA'),
        ('PERDIDA_ROBO', 'PERDIDA: ROBO O SUSTRACCION'),
        ('REEMBOLSO_REPOSICION', 'REEMBOLSO O REPOSICIÓN'),
        ('OTRO_CAUSAL', 'OTRO CAUSAL'),
    ]
    
    # Relación con el bien
    bien = models.OneToOneField('bienes.Bien', on_delete=models.PROTECT, related_name='baja', verbose_name="Bien")
    
    # Datos del acto de baja
    resolucion_baja = models.CharField(max_length=100, verbose_name="Resolución de Baja")
    fecha_resolucion = models.DateField(verbose_name="Fecha Resolución")
    causal_baja = models.CharField(max_length=30, choices=CAUSAL_BAJA_CHOICES, verbose_name="Causal de Baja")
    documento_sbn = models.CharField(max_length=50, blank=True, null=True, verbose_name="Doc. SBN N°")
    
    # Auditoría
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    usuario_registro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Usuario que registró")
    
    def __str__(self):
        return f"Baja de {self.bien.codigo_patrimonial} - {self.get_causal_baja_display()}"
    
    class Meta:
        verbose_name = "Baja de Bien"
        verbose_name_plural = "Bajas de Bienes"
        ordering = ['-fecha_registro']
        db_table = 'inventario_bajabien'
