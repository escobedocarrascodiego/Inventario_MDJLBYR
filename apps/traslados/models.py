from django.db import models


# ==============================================================================
# 6. MODELO DE TRASLADO DE BIENES
# ==============================================================================

class TrasladoBien(models.Model):
    """Modelo para registrar el traslado de bienes entre usuarios y ubicaciones"""
    
    # Bien trasladado
    bien = models.ForeignKey('bienes.Bien', on_delete=models.PROTECT, related_name='traslados', verbose_name="Bien")
    
    # Ubicación Origen
    usuario_origen = models.ForeignKey('personal.Personal', on_delete=models.PROTECT, related_name='traslados_origen', verbose_name="Usuario Origen")
    local_origen = models.ForeignKey('organizacion.Local', on_delete=models.PROTECT, related_name='traslados_origen', verbose_name="Local Origen")
    area_origen = models.ForeignKey('organizacion.Area', on_delete=models.PROTECT, related_name='traslados_origen', null=True, blank=True, verbose_name="Área Origen")
    oficina_origen = models.ForeignKey('organizacion.Oficina', on_delete=models.PROTECT, related_name='traslados_origen', null=True, blank=True, verbose_name="Oficina Origen")
    ubicacion_origen = models.ForeignKey('organizacion.UbicacionFisica', on_delete=models.PROTECT, related_name='traslados_origen_ubicacion', null=True, blank=True, verbose_name="Ubicación Física Origen")
    
    # Ubicación Destino
    usuario_destino = models.ForeignKey('personal.Personal', on_delete=models.PROTECT, related_name='traslados_destino', verbose_name="Usuario Destino")
    local_destino = models.ForeignKey('organizacion.Local', on_delete=models.PROTECT, related_name='traslados_destino', verbose_name="Local Destino")
    area_destino = models.ForeignKey('organizacion.Area', on_delete=models.PROTECT, related_name='traslados_destino', null=True, blank=True, verbose_name="Área Destino")
    oficina_destino = models.ForeignKey('organizacion.Oficina', on_delete=models.PROTECT, related_name='traslados_destino', null=True, blank=True, verbose_name="Oficina Destino")
    ubicacion_destino = models.ForeignKey('organizacion.UbicacionFisica', on_delete=models.PROTECT, related_name='traslados_destino_ubicacion', null=True, blank=True, verbose_name="Ubicación Física Destino")
    
    # Auditoría
    fecha_traslado = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Traslado")
    usuario_registro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Usuario que registró")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Observaciones")
    
    def __str__(self):
        return f"Traslado de {self.bien.codigo_patrimonial} de {self.usuario_origen} a {self.usuario_destino}"
    
    class Meta:
        verbose_name = "Traslado de Bien"
        verbose_name_plural = "Traslados de Bienes"
        ordering = ['-fecha_traslado']
        db_table = 'inventario_trasladobien'


# ==============================================================================
# 7. ESCANEO DE CÓDIGOS DE BARRAS
# ==============================================================================

class EscaneoCodigoBarra(models.Model):
    """Registro temporal de códigos escaneados para traslados masivos."""

    ESTADO_ESCANEO = [
        ('PENDIENTE', 'Pendiente'),
        ('PROCESADO', 'Procesado'),
        ('ERROR', 'Error'),
    ]

    session_key = models.CharField(max_length=40, db_index=True)
    codigo_patrimonial = models.CharField(max_length=50)
    bien = models.ForeignKey(
        'bienes.Bien',
        on_delete=models.PROTECT,
        related_name='escaneos_codigo_barra',
        null=True,
        blank=True
    )
    traslado = models.ForeignKey(
        TrasladoBien,
        on_delete=models.SET_NULL,
        related_name='escaneos',
        null=True,
        blank=True
    )
    estado = models.CharField(max_length=15, choices=ESTADO_ESCANEO, default='PENDIENTE')
    mensaje_error = models.CharField(max_length=255, blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    usuario_registro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Usuario que registró")

    def __str__(self):
        return f"{self.codigo_patrimonial} ({self.get_estado_display()})"

    class Meta:
        verbose_name = "Escaneo de Código de Barra"
        verbose_name_plural = "Escaneos de Códigos de Barras"
        ordering = ['-fecha_registro']
        db_table = 'inventario_escaneocodigobarra'
