from django.contrib import admin
from .models import UbicacionFisica


@admin.register(UbicacionFisica)
class UbicacionFisicaAdmin(admin.ModelAdmin):
    list_display = ('detalle', 'piso', 'oficina', 'area', 'local', 'activo')
    list_filter = ('local', 'area', 'oficina', 'activo')
    search_fields = ('detalle', 'oficina__nombre', 'area__nombre', 'local__nombre')
