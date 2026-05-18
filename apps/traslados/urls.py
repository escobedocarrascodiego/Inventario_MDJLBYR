from django.urls import path
from . import views

# NOTA: Estas URLs se incluirán desde inventario/urls.py con el namespace 'inventario'

urlpatterns = [
    # URLs para Traslado de Bienes
    path('funciones/traslado-bienes/', views.traslado_bienes_index, name='traslado_bienes_index'),

    # URLs AJAX para Traslado de Bienes
    path('ajax/bienes-por-usuario-ubicacion/', views.obtener_bienes_por_usuario_ubicacion, name='obtener_bienes_por_usuario_ubicacion'),
    path('ajax/usuario/<int:pk>/ubicacion/', views.obtener_ubicacion_usuario, name='obtener_ubicacion_usuario'),
    path('ajax/ejecutar-traslado/', views.ejecutar_traslado, name='ejecutar_traslado'),
    path('ajax/buscar-traslados-por-fecha/', views.buscar_traslados_por_fecha, name='buscar_traslados_por_fecha'),

    # URLs para Escaneo de Códigos de Barras
    path('funciones/escanear-codigos-barras/', views.escanear_codigos_barras, name='escanear_codigos_barras'),

    # URLs AJAX para Escaneo de Códigos de Barras
    path('ajax/escaneo-codigo/', views.registrar_escaneo_codigo, name='registrar_escaneo_codigo'),
    path('ajax/escaneo-codigo/<int:pk>/eliminar/', views.eliminar_escaneo_codigo, name='eliminar_escaneo_codigo'),
    path('ajax/escaneo-codigo/limpiar/', views.limpiar_escaneos_codigo, name='limpiar_escaneos_codigo'),
    path('ajax/escaneo-codigo/trasladar/', views.ejecutar_traslado_escaneados, name='ejecutar_traslado_escaneados'),

    # URLs para Reportes de Traslado
    path('funciones/traslado-bienes/reporte/<int:traslado_id>/', views.generar_reporte_asignacion_traslado, name='reporte_asignacion_traslado'),
]
