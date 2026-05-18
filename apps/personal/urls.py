from django.urls import path
from . import views

# NOTA: Estas URLs se incluirán desde inventario/urls.py con el namespace 'inventario'
# por lo que los nombres de URL (name=) se mantienen idénticos al original.

urlpatterns = [
    # URLs para Personal
    path('personal/', views.PersonalListView.as_view(), name='personal_list'),
    path('personal/datatable/', views.personal_datatable, name='personal_datatable'),
    path('personal/nuevo/', views.PersonalCreateView.as_view(), name='personal_create'),
    path('personal/<int:pk>/editar/', views.PersonalUpdateView.as_view(), name='personal_update'),
    path('personal/<int:pk>/eliminar/', views.PersonalDeleteView.as_view(), name='personal_delete'),

    # URLs AJAX
    path('ajax/buscar-personal/', views.buscar_personal, name='buscar_personal'),
]
