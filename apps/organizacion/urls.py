from django.urls import path
from . import views

# NOTA: Estas URLs se incluirán desde inventario/urls.py con el namespace 'inventario'
# por lo que los nombres de URL (name=) se mantienen idénticos al original.

urlpatterns = [
    # URLs para Entidad
    path('entidades/', views.EntidadListView.as_view(), name='entidad_list'),
    path('entidades/nuevo/', views.EntidadCreateView.as_view(), name='entidad_create'),
    path('entidades/<int:pk>/editar/', views.EntidadUpdateView.as_view(), name='entidad_update'),
    path('entidades/<int:pk>/eliminar/', views.EntidadDeleteView.as_view(), name='entidad_delete'),

    # URLs para Local
    path('locales/', views.LocalListView.as_view(), name='local_list'),
    path('locales/nuevo/', views.LocalCreateView.as_view(), name='local_create'),
    path('locales/<int:pk>/editar/', views.LocalUpdateView.as_view(), name='local_update'),
    path('locales/<int:pk>/eliminar/', views.LocalDeleteView.as_view(), name='local_delete'),

    # URLs para Área
    path('areas/', views.AreaListView.as_view(), name='area_list'),
    path('areas/nuevo/', views.AreaCreateView.as_view(), name='area_create'),
    path('areas/<int:pk>/editar/', views.AreaUpdateView.as_view(), name='area_update'),
    path('areas/<int:pk>/eliminar/', views.AreaDeleteView.as_view(), name='area_delete'),

    # URLs para Oficina
    path('oficinas/', views.OficinaListView.as_view(), name='oficina_list'),
    path('oficinas/nuevo/', views.OficinaCreateView.as_view(), name='oficina_create'),
    path('oficinas/<int:pk>/editar/', views.OficinaUpdateView.as_view(), name='oficina_update'),
    path('oficinas/<int:pk>/eliminar/', views.OficinaDeleteView.as_view(), name='oficina_delete'),

    # URLs para Ubicación Física
    path('ubicaciones-fisicas/', views.UbicacionFisicaListView.as_view(), name='ubicacionfisica_list'),
    path('ubicaciones-fisicas/nuevo/', views.UbicacionFisicaCreateView.as_view(), name='ubicacionfisica_create'),
    path('ubicaciones-fisicas/<int:pk>/editar/', views.UbicacionFisicaUpdateView.as_view(), name='ubicacionfisica_update'),
    path('ubicaciones-fisicas/<int:pk>/eliminar/', views.UbicacionFisicaDeleteView.as_view(), name='ubicacionfisica_delete'),

    # URLs AJAX
    path('ajax/areas-por-local/', views.obtener_areas_por_local, name='obtener_areas_por_local'),
    path('ajax/oficinas-por-area/', views.obtener_oficinas_por_area, name='obtener_oficinas_por_area'),
    path('ajax/ubicaciones-fisicas/', views.obtener_ubicaciones_fisicas, name='obtener_ubicaciones_fisicas'),
]
