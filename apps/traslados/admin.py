from django.contrib import admin
from .models import TrasladoBien


@admin.register(TrasladoBien)
class TrasladoBienAdmin(admin.ModelAdmin):
    list_display = ('bien', 'usuario_origen', 'usuario_destino', 'documento_autoriza', 'fecha_traslado')
    list_filter = ('fecha_traslado', 'local_origen', 'local_destino')
    search_fields = ('bien__codigo_patrimonial', 'usuario_origen__apellidos', 'usuario_destino__apellidos', 'documento_autoriza')
    readonly_fields = ('fecha_traslado',)
    date_hierarchy = 'fecha_traslado'
