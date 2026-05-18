from django.urls import path, include

app_name = 'inventario'

# ==============================================================================
# URL MAESTRO: Incluye todas las URLs de las sub-apps
# ==============================================================================
# Todas las sub-apps se incluyen SIN prefijo adicional porque cada una ya
# define sus paths completos (ej: 'bienes/', 'personal/', etc.)
# El namespace 'inventario' se mantiene para que todos los reverse() y
# {% url 'inventario:xxx' %} en templates sigan funcionando sin cambios.
# ==============================================================================

urlpatterns = [
    # App: bienes (incluye home, CRUD bien, consulta histórica, cierre, importación, funciones_index, AJAX)
    path('', include('bienes.urls')),

    # App: organizacion (CRUD entidad, local, área, oficina, ubicación física + AJAX)
    path('', include('organizacion.urls')),

    # App: personal (CRUD personal, datatable, buscar_personal AJAX)
    path('', include('personal.urls')),

    # App: catalogos (CRUD grupo genérico, clase, denominación, cuenta contable + AJAX + datatables)
    path('', include('catalogos.urls')),

    # App: bajas (listado, crear, detalle, ficha PDF de baja)
    path('', include('bajas.urls')),

    # App: traslados (traslado manual, escaneo códigos, reporte asignación, AJAX)
    path('', include('traslados.urls')),

    # App: reportes (reportes PDF, Excel, etiquetas, fichas)
    path('', include('reportes.urls')),
]
