from django.contrib import admin
from .models import BajaBien


@admin.register(BajaBien)
class BajaBienAdmin(admin.ModelAdmin):
    list_display = ('bien', 'resolucion_baja', 'fecha_resolucion', 'causal_baja', 'fecha_registro')
    list_filter = ('causal_baja', 'fecha_resolucion', 'fecha_registro')
    search_fields = ('bien__codigo_patrimonial', 'bien__descripcion', 'resolucion_baja')
    readonly_fields = ('fecha_registro',)
    date_hierarchy = 'fecha_registro'
