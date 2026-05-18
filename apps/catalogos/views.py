from django.shortcuts import get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import CuentaContable, GrupoGenerico, Clase, Denominacion
from .forms import CuentaContableForm, GrupoGenericoForm, ClaseForm, DenominacionForm


# ==============================================================================
# VISTAS PARA CATÁLOGOS DE BIENES
# ==============================================================================

# Grupo Genérico

class GrupoGenericoListView(ListView):
    model = GrupoGenerico
    template_name = 'inventario/grupogenerico_list.html'
    context_object_name = 'grupos'

class GrupoGenericoCreateView(SuccessMessageMixin, CreateView):
    model = GrupoGenerico
    form_class = GrupoGenericoForm
    template_name = 'inventario/grupogenerico_form.html'
    success_url = reverse_lazy('inventario:grupogenerico_list')
    success_message = "Grupo Genérico creado exitosamente."

class GrupoGenericoUpdateView(SuccessMessageMixin, UpdateView):
    model = GrupoGenerico
    form_class = GrupoGenericoForm
    template_name = 'inventario/grupogenerico_form.html'
    success_url = reverse_lazy('inventario:grupogenerico_list')
    success_message = "Grupo Genérico actualizado exitosamente."

class GrupoGenericoDeleteView(SuccessMessageMixin, DeleteView):
    model = GrupoGenerico
    template_name = 'inventario/grupogenerico_confirm_delete.html'
    success_url = reverse_lazy('inventario:grupogenerico_list')
    success_message = "Grupo Genérico eliminado exitosamente."


# Clase

class ClaseListView(ListView):
    model = Clase
    template_name = 'inventario/clase_list.html'
    context_object_name = 'clases'
    
    def get_queryset(self):
        return Clase.objects.select_related('grupo_generico', 'cuenta_contable').filter(activo=True).order_by('grupo_generico', 'nombre')

class ClaseCreateView(SuccessMessageMixin, CreateView):
    model = Clase
    form_class = ClaseForm
    template_name = 'inventario/clase_form.html'
    success_url = reverse_lazy('inventario:clase_list')
    success_message = "Clase creada exitosamente."

class ClaseUpdateView(SuccessMessageMixin, UpdateView):
    model = Clase
    form_class = ClaseForm
    template_name = 'inventario/clase_form.html'
    success_url = reverse_lazy('inventario:clase_list')
    success_message = "Clase actualizada exitosamente."

class ClaseDeleteView(SuccessMessageMixin, DeleteView):
    model = Clase
    template_name = 'inventario/clase_confirm_delete.html'
    success_url = reverse_lazy('inventario:clase_list')
    success_message = "Clase eliminada exitosamente."


# Denominación

class DenominacionListView(ListView):
    model = Denominacion
    template_name = 'inventario/denominacion_list.html'
    context_object_name = 'denominaciones'
    
    def get_queryset(self):
        # El listado se carga vía DataTables (server-side); aquí no traemos registros.
        return Denominacion.objects.none()

class DenominacionCreateView(SuccessMessageMixin, CreateView):
    model = Denominacion
    form_class = DenominacionForm
    template_name = 'inventario/denominacion_form.html'
    success_url = reverse_lazy('inventario:denominacion_list')
    success_message = "Denominación creada exitosamente."

class DenominacionUpdateView(SuccessMessageMixin, UpdateView):
    model = Denominacion
    form_class = DenominacionForm
    template_name = 'inventario/denominacion_form.html'
    success_url = reverse_lazy('inventario:denominacion_list')
    success_message = "Denominación actualizada exitosamente. Los bienes vinculados se han actualizado."

    def form_valid(self, form):
        from bienes.models import Bien
        response = super().form_valid(form)
        # Propagar cambios de la denominación a todos los bienes que la usan
        den = self.object
        bienes_actualizados = Bien.objects.filter(denominacion=den).update(
            descripcion=den.nombre,
            grupo_generico=den.grupo_generico.nombre,
            clase=den.clase.nombre,
            codigo_patrimonial_base=den.codigo_patrimonial_base,
            cuenta_contable=den.cuenta_contable,
        )
        return response

class DenominacionDeleteView(SuccessMessageMixin, DeleteView):
    model = Denominacion
    template_name = 'inventario/denominacion_confirm_delete.html'
    success_url = reverse_lazy('inventario:denominacion_list')
    success_message = "Denominación eliminada exitosamente."


# ==============================================================================
# VISTA AJAX PARA BUSCAR DENOMINACIONES
# ==============================================================================

@require_http_methods(["GET"])
def buscar_denominaciones(request):
    """Vista AJAX para buscar denominaciones"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'denominaciones': []})
    
    denominaciones = Denominacion.objects.filter(
        activo=True,
        nombre__icontains=query
    ).select_related('grupo_generico', 'clase', 'cuenta_contable')[:20]
    
    results = []
    for den in denominaciones:
        results.append({
            'id': den.id,
            'nombre': den.nombre,
            'grupo_generico': den.grupo_generico.nombre,
            'clase': den.clase.nombre,
            'codigo_patrimonial_base': den.codigo_patrimonial_base,
            'cuenta_contable_codigo': den.cuenta_contable.codigo,
            'cuenta_contable_descripcion': den.cuenta_contable.descripcion,
        })
    
    return JsonResponse({'denominaciones': results})


@require_http_methods(["GET"])
def obtener_denominacion(request, pk):
    """Vista AJAX para obtener datos completos de una denominación"""
    from bienes.models import Bien
    denominacion = get_object_or_404(Denominacion.objects.select_related('grupo_generico', 'clase', 'cuenta_contable'), pk=pk, activo=True)
    
    # Obtener el siguiente correlativo
    ultimo_bien = Bien.objects.filter(denominacion=denominacion).order_by('-correlativo').first()
    siguiente_correlativo = (ultimo_bien.correlativo + 1) if ultimo_bien else 1
    codigo_patrimonial_completo = f"{denominacion.codigo_patrimonial_base}-{siguiente_correlativo:04d}"
    
    return JsonResponse({
        'id': denominacion.id,
        'nombre': denominacion.nombre,
        'grupo_generico': denominacion.grupo_generico.nombre,
        'clase': denominacion.clase.nombre,
        'codigo_patrimonial_base': denominacion.codigo_patrimonial_base,
        'codigo_patrimonial_completo': codigo_patrimonial_completo,
        'correlativo': siguiente_correlativo,
        'cuenta_contable_id': denominacion.cuenta_contable.id,
        'cuenta_contable_codigo': denominacion.cuenta_contable.codigo,
        'cuenta_contable_descripcion': denominacion.cuenta_contable.descripcion,
        'tasa_depreciacion': denominacion.cuenta_contable.tasa_depreciacion,
        'vida_util_meses': denominacion.cuenta_contable.vida_util_meses,
    })


@require_http_methods(["GET"])
def obtener_cuenta_contable(request, pk):
    """Vista AJAX para obtener datos de una cuenta contable"""
    cuenta = get_object_or_404(CuentaContable, pk=pk)
    return JsonResponse({
        'id': cuenta.id,
        'codigo': cuenta.codigo,
        'descripcion': cuenta.descripcion,
        'tasa_depreciacion': cuenta.tasa_depreciacion,
        'vida_util_meses': cuenta.vida_util_meses,
    })


# ==============================================================================
# DATATABLE SERVER-SIDE PARA DENOMINACIONES
# ==============================================================================

@require_http_methods(["GET"])
def denominaciones_datatable(request):
    """Endpoint para DataTables (server-side) en listado de denominaciones."""
    from django.utils.html import escape

    def _to_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    draw = _to_int(request.GET.get('draw'), 1)
    start = _to_int(request.GET.get('start'), 0)
    length = _to_int(request.GET.get('length'), 25)
    search_value = (request.GET.get('search[value]', '') or '').strip()

    # Base queryset sin JOINs adicionales para el conteo inicial
    base_qs = Denominacion.objects.filter(activo=True)
    records_total = base_qs.count()

    # Agregar select_related solo cuando se van a usar los registros
    queryset = base_qs.select_related('grupo_generico', 'clase', 'cuenta_contable')

    # Solo contar de nuevo si realmente hay filtros aplicados
    has_filters = False
    if search_value:
        has_filters = True
        queryset = queryset.filter(
            Q(nombre__icontains=search_value)
            | Q(grupo_generico__nombre__icontains=search_value)
            | Q(clase__nombre__icontains=search_value)
            | Q(cuenta_contable__codigo__icontains=search_value)
        )

    records_filtered = queryset.count() if has_filters else records_total

    order_column = _to_int(request.GET.get('order[0][column]'), 1)
    order_dir = request.GET.get('order[0][dir]', 'asc')
    order_map = {
        0: 'nombre',
        1: 'nombre',
        2: 'grupo_generico__nombre',
        3: 'clase__nombre',
        4: 'codigo_patrimonial_base',
        5: 'cuenta_contable__codigo',
        6: 'activo',
    }
    order_field = order_map.get(order_column, 'nombre')
    if order_dir == 'desc':
        order_field = f"-{order_field}"
    queryset = queryset.order_by(order_field, 'id')

    data = []
    if length <= 0:
        length = 25

    for index, den in enumerate(queryset[start:start + length], start=start + 1):
        nombre = f"<strong>{escape(den.nombre)}</strong>"
        grupo = escape(str(den.grupo_generico))
        clase = escape(str(den.clase))
        codigo_base = escape(den.codigo_patrimonial_base or '')
        cuenta_codigo = escape(den.cuenta_contable.codigo if den.cuenta_contable else '')
        if den.activo:
            estado = '<span class="badge bg-success">Activo</span>'
        else:
            estado = '<span class="badge bg-secondary">Inactivo</span>'

        edit_url = reverse('inventario:denominacion_update', args=[den.pk])
        delete_url = reverse('inventario:denominacion_delete', args=[den.pk])
        acciones = (
            '<div class="btn-group btn-group-sm" role="group">'
            f'<a href="{edit_url}" class="btn btn-outline-primary" title="Editar">'
            '<i class="fas fa-edit"></i></a>'
            f'<a href="{delete_url}" class="btn btn-outline-danger" title="Eliminar" '
            "onclick=\"return confirm('¿Está seguro de eliminar esta denominación?');\">"
            '<i class="fas fa-trash"></i></a>'
            '</div>'
        )

        data.append([
            index,
            nombre,
            grupo,
            clase,
            codigo_base,
            cuenta_codigo,
            estado,
            acciones,
        ])

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


# ==============================================================================
# AJAX PARA CLASE INFO Y CLASES POR GRUPO
# ==============================================================================

@require_http_methods(["GET"])
def obtener_clase_info(request, pk):
    """Vista AJAX para obtener información de una clase (cuenta contable sugerida)"""
    clase = get_object_or_404(Clase.objects.select_related('grupo_generico', 'cuenta_contable'), pk=pk, activo=True)
    
    response_data = {
        'id': clase.id,
        'nombre': clase.nombre,
        'grupo_generico': clase.grupo_generico.nombre,
    }
    
    # Si la clase tiene cuenta contable, incluirla como sugerencia
    if clase.cuenta_contable:
        response_data['cuenta_contable_id'] = clase.cuenta_contable.id
        response_data['cuenta_contable_codigo'] = clase.cuenta_contable.codigo
        response_data['cuenta_contable_descripcion'] = clase.cuenta_contable.descripcion
    
    return JsonResponse(response_data)


@require_http_methods(["GET"])
def obtener_clases_por_grupo(request):
    """Vista AJAX para obtener clases filtradas por grupo genérico"""
    grupo_id = request.GET.get('grupo_id')
    if not grupo_id:
        return JsonResponse({'clases': []})
    
    clases = Clase.objects.filter(grupo_generico_id=grupo_id, activo=True).order_by('nombre')
    results = [{'id': c.id, 'nombre': c.nombre} for c in clases]
    
    return JsonResponse({'clases': results})


# ==============================================================================
# VISTAS PARA CUENTA CONTABLE
# ==============================================================================

class CuentaContableListView(ListView):
    model = CuentaContable
    template_name = 'inventario/cuentacontable_list.html'
    context_object_name = 'cuentas'
    
    def get_queryset(self):
        # El listado se carga vía DataTables (server-side); aquí no traemos registros.
        return CuentaContable.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        return context

class CuentaContableCreateView(SuccessMessageMixin, CreateView):
    model = CuentaContable
    form_class = CuentaContableForm
    template_name = 'inventario/cuentacontable_form.html'
    success_url = reverse_lazy('inventario:cuentacontable_list')
    success_message = "Cuenta Contable creada exitosamente."

class CuentaContableUpdateView(SuccessMessageMixin, UpdateView):
    model = CuentaContable
    form_class = CuentaContableForm
    template_name = 'inventario/cuentacontable_form.html'
    success_url = reverse_lazy('inventario:cuentacontable_list')
    success_message = "Cuenta Contable actualizada exitosamente."

class CuentaContableDeleteView(SuccessMessageMixin, DeleteView):
    model = CuentaContable
    template_name = 'inventario/cuentacontable_confirm_delete.html'
    success_url = reverse_lazy('inventario:cuentacontable_list')
    success_message = "Cuenta Contable eliminada exitosamente."


# ==============================================================================
# DATATABLE SERVER-SIDE PARA CUENTAS CONTABLES
# ==============================================================================

@require_http_methods(["GET"])
def cuentas_contables_datatable(request):
    """Endpoint para DataTables (server-side) en listado de cuentas contables."""
    from django.utils.html import escape

    def _to_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    draw = _to_int(request.GET.get('draw'), 1)
    start = _to_int(request.GET.get('start'), 0)
    length = _to_int(request.GET.get('length'), 25)
    search_value = (request.GET.get('search[value]', '') or '').strip()

    # Base queryset sencillo para conteo total rápido
    base_qs = CuentaContable.objects.all()
    records_total = base_qs.count()

    queryset = base_qs

    # Solo repetir COUNT si hay filtros activos
    has_filters = False
    if search_value:
        has_filters = True
        queryset = queryset.filter(
            Q(codigo__icontains=search_value)
            | Q(descripcion__icontains=search_value)
        )

    records_filtered = queryset.count() if has_filters else records_total

    order_column = _to_int(request.GET.get('order[0][column]'), 1)
    order_dir = request.GET.get('order[0][dir]', 'asc')
    order_map = {
        0: 'codigo',
        1: 'codigo',
        2: 'descripcion',
        3: 'tasa_depreciacion',
        4: 'vida_util_meses',
    }
    order_field = order_map.get(order_column, 'codigo')
    if order_dir == 'desc':
        order_field = f"-{order_field}"
    queryset = queryset.order_by(order_field, 'id')

    data = []
    if length <= 0:
        length = 25

    for index, cuenta in enumerate(queryset[start:start + length], start=start + 1):
        codigo = f"<strong>{escape(cuenta.codigo)}</strong>"
        descripcion = escape(cuenta.descripcion or '')
        if cuenta.tasa_depreciacion is not None:
            tasa = f"{cuenta.tasa_depreciacion:,.2f}%"
        else:
            tasa = '<span class="text-muted">-</span>'
        if cuenta.vida_util_meses is not None:
            vida = str(cuenta.vida_util_meses)
        else:
            vida = '<span class="text-muted">-</span>'

        edit_url = reverse('inventario:cuentacontable_update', args=[cuenta.pk])
        delete_url = reverse('inventario:cuentacontable_delete', args=[cuenta.pk])
        acciones = (
            '<div class="btn-group btn-group-sm" role="group">'
            f'<a href="{edit_url}" class="btn btn-outline-primary" title="Editar">'
            '<i class="fas fa-edit"></i></a>'
            f'<a href="{delete_url}" class="btn btn-outline-danger" title="Eliminar" '
            "onclick=\"return confirm('¿Está seguro de eliminar esta cuenta contable?');\">"
            '<i class="fas fa-trash"></i></a>'
            '</div>'
        )

        data.append([
            index,
            codigo,
            descripcion,
            tasa,
            vida,
            acciones,
        ])

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
