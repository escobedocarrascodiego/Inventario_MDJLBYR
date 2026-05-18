from django.urls import path
from . import views

# NOTA: Estas URLs se incluirán desde inventario/urls.py con el namespace 'inventario'

urlpatterns = [
    # URLs para Reportes (index + filtros)
    path('funciones/reportes/', views.reportes_index, name='reportes_index'),
    path('funciones/reportes/depreciacion/', views.reporte_depreciacion_filtros, name='reporte_depreciacion_filtros'),

    # URLs para Reportes PDF
    path('funciones/reportes/depreciacion/pdf/', views.generar_reporte_depreciacion, name='reporte_depreciacion'),
    path('funciones/reportes/bienes-activos/', views.generar_reporte_bienes_activos, name='reporte_bienes_activos'),
    path('funciones/reportes/bienes-por-local/', views.generar_reporte_bienes_por_local, name='reporte_bienes_por_local'),
    path('funciones/reportes/bienes-baja/', views.generar_reporte_bienes_baja, name='reporte_bienes_baja'),
    path('funciones/reportes/por-cuentas-contables/', views.generar_reporte_por_cuentas_contables, name='reporte_por_cuentas_contables'),

    # URLs para Reportes en Excel
    path('funciones/reportes/excel/bienes-detallados/', views.generar_reporte_excel_bienes_detallados, name='reporte_excel_bienes_detallados'),
    path('funciones/reportes/excel/bienes-por-local/', views.generar_reporte_excel_bienes_por_local, name='reporte_excel_bienes_por_local'),
    path('funciones/reportes/excel/bienes-baja/', views.generar_reporte_excel_bienes_baja, name='reporte_excel_bienes_baja'),

    # URLs para Etiquetas
    path('funciones/etiquetas/', views.etiquetas_index, name='etiquetas_index'),

    # URLs para Fichas
    path('funciones/fichas/', views.fichas_index, name='fichas_index'),
    path('ajax/buscar-bienes-para-ficha/', views.buscar_bienes_para_ficha, name='buscar_bienes_para_ficha'),
    path('funciones/fichas/computo/<int:bien_id>/', views.generar_ficha_computo, name='ficha_computo'),
    path('funciones/fichas/vehiculo/<int:bien_id>/', views.generar_ficha_vehiculo, name='ficha_vehiculo'),
]
