from django.urls import path
from . import views

# NOTA: Estas URLs se incluirán desde inventario/urls.py con el namespace 'inventario'

urlpatterns = [
    # URLs para Baja de Bienes
    path('funciones/baja-bienes/', views.baja_bienes_list, name='baja_bienes_list'),
    path('funciones/baja-bienes/nuevo/', views.baja_bien_create, name='baja_bien_create'),
    path('funciones/baja-bienes/<int:pk>/', views.baja_bien_detail, name='baja_bien_detail'),
    path('funciones/baja-bienes/<int:pk>/ficha/', views.generar_ficha_baja, name='ficha_baja'),
]
