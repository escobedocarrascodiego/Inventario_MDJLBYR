from django.urls import path
from . import views

# NOTA: Estas URLs se incluirán desde inventario/urls.py con el namespace 'inventario'

urlpatterns = [
    # Home
    path('', views.home, name='home'),

    # URLs para Bien
    path('bienes/', views.BienListView.as_view(), name='bien_list'),
    path('bienes/nuevo/', views.BienCreateView.as_view(), name='bien_create'),
    path('bienes/<int:pk>/editar/', views.BienUpdateView.as_view(), name='bien_update'),
    path('bienes/<int:pk>/eliminar/', views.BienDeleteView.as_view(), name='bien_delete'),
    path('bienes/<int:pk>/historial/', views.bien_historial, name='bien_historial'),
    path('bienes/datatable/', views.bienes_datatable, name='bienes_datatable'),
    path('bienes/consulta-historica/', views.consulta_historica, name='consulta_historica'),
    path('bienes/cierre-anio-fiscal/', views.cierre_anio_fiscal, name='cierre_anio_fiscal'),
    path('bienes/carga-masiva/', views.importar_inventario_view, name='importar_inventario'),
    path('bienes/carga-masiva/plantilla/', views.descargar_plantilla_carga, name='descargar_plantilla_carga'),
    path('bienes/carga-masiva/errores/', views.descargar_errores_importacion, name='descargar_errores_importacion'),

    # Funciones index
    path('funciones/', views.funciones_index, name='funciones_index'),

    # URLs AJAX
    path('ajax/valor-neto/', views.obtener_valor_neto, name='obtener_valor_neto'),
    path('ajax/buscar-bien-baja/', views.buscar_bien_ajax, name='buscar_bien_ajax'),
    path('ajax/buscar-bien-etiquetas/', views.buscar_bien_etiquetas, name='buscar_bien_etiquetas'),
    path('ajax/bien/<int:pk>/', views.obtener_bien_ajax, name='obtener_bien_ajax'),
]
