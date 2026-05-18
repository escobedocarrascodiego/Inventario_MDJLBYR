from django.urls import path
from . import views

# NOTA: Estas URLs se incluirán desde inventario/urls.py con el namespace 'inventario'
# por lo que los nombres de URL (name=) se mantienen idénticos al original.

urlpatterns = [
    # URLs para Catálogos de Bienes - Grupo Genérico
    path('catalogos/grupos-genericos/', views.GrupoGenericoListView.as_view(), name='grupogenerico_list'),
    path('catalogos/grupos-genericos/nuevo/', views.GrupoGenericoCreateView.as_view(), name='grupogenerico_create'),
    path('catalogos/grupos-genericos/<int:pk>/editar/', views.GrupoGenericoUpdateView.as_view(), name='grupogenerico_update'),
    path('catalogos/grupos-genericos/<int:pk>/eliminar/', views.GrupoGenericoDeleteView.as_view(), name='grupogenerico_delete'),

    # URLs para Catálogos de Bienes - Clase
    path('catalogos/clases/', views.ClaseListView.as_view(), name='clase_list'),
    path('catalogos/clases/nuevo/', views.ClaseCreateView.as_view(), name='clase_create'),
    path('catalogos/clases/<int:pk>/editar/', views.ClaseUpdateView.as_view(), name='clase_update'),
    path('catalogos/clases/<int:pk>/eliminar/', views.ClaseDeleteView.as_view(), name='clase_delete'),

    # URLs para Catálogos de Bienes - Denominación
    path('catalogos/denominaciones/', views.DenominacionListView.as_view(), name='denominacion_list'),
    path('catalogos/denominaciones/nuevo/', views.DenominacionCreateView.as_view(), name='denominacion_create'),
    path('catalogos/denominaciones/<int:pk>/editar/', views.DenominacionUpdateView.as_view(), name='denominacion_update'),
    path('catalogos/denominaciones/<int:pk>/eliminar/', views.DenominacionDeleteView.as_view(), name='denominacion_delete'),
    path('catalogos/denominaciones/datatable/', views.denominaciones_datatable, name='denominaciones_datatable'),

    # URLs para Cuenta Contable
    path('catalogos/cuentas-contables/', views.CuentaContableListView.as_view(), name='cuentacontable_list'),
    path('catalogos/cuentas-contables/nuevo/', views.CuentaContableCreateView.as_view(), name='cuentacontable_create'),
    path('catalogos/cuentas-contables/<int:pk>/editar/', views.CuentaContableUpdateView.as_view(), name='cuentacontable_update'),
    path('catalogos/cuentas-contables/<int:pk>/eliminar/', views.CuentaContableDeleteView.as_view(), name='cuentacontable_delete'),
    path('catalogos/cuentas-contables/datatable/', views.cuentas_contables_datatable, name='cuentas_contables_datatable'),

    # URLs AJAX
    path('ajax/buscar-denominaciones/', views.buscar_denominaciones, name='buscar_denominaciones'),
    path('ajax/denominacion/<int:pk>/', views.obtener_denominacion, name='obtener_denominacion'),
    path('ajax/cuenta-contable/<int:pk>/', views.obtener_cuenta_contable, name='obtener_cuenta_contable'),
    path('ajax/clase/<int:pk>/info/', views.obtener_clase_info, name='obtener_clase_info'),
    path('ajax/clases-por-grupo/', views.obtener_clases_por_grupo, name='obtener_clases_por_grupo'),
]
