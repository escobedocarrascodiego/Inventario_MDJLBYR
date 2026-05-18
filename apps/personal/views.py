from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Personal
from .forms import PersonalForm


# ==============================================================================
# DATATABLE SERVER-SIDE PARA PERSONAL
# ==============================================================================

@require_http_methods(["GET"])
def personal_datatable(request):
    """Endpoint para DataTables (server-side) en listado de personal."""
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

    # Base queryset sin JOINs pesados para el conteo total
    base_qs = Personal.objects.all()
    records_total = base_qs.count()

    # Aplicar joins solo cuando se van a usar los datos
    queryset = base_qs.select_related('area', 'area__local', 'oficina')

    # Solo forzar un segundo COUNT si realmente hay filtros
    has_filters = False
    if search_value:
        has_filters = True
        queryset = queryset.filter(
            Q(nombres__icontains=search_value)
            | Q(apellidos__icontains=search_value)
            | Q(numero_documento__icontains=search_value)
            | Q(cargo__icontains=search_value)
        )

    records_filtered = queryset.count() if has_filters else records_total

    order_column = _to_int(request.GET.get('order[0][column]'), 1)
    order_dir = request.GET.get('order[0][dir]', 'asc')
    order_map = {
        0: 'apellidos',
        1: 'apellidos',
        2: 'numero_documento',
        3: 'modalidad',
        4: 'cargo',
        5: 'oficina__nombre',
        6: 'area__nombre',
    }
    order_field = order_map.get(order_column, 'apellidos')
    if order_dir == 'desc':
        order_field = f"-{order_field}"
    queryset = queryset.order_by(order_field, 'nombres', 'id')

    data = []
    if length <= 0:
        length = 25

    for index, persona in enumerate(queryset[start:start + length], start=start + 1):
        nombre_completo = escape(f"{persona.apellidos}, {persona.nombres}")
        documento = f"{escape(persona.get_tipo_documento_display())}: <strong>{escape(persona.numero_documento or '')}</strong>"
        modalidad = f'<span class="badge bg-info">{escape(persona.get_modalidad_display())}</span>'
        cargo = escape(persona.cargo or '-') if getattr(persona, 'cargo', None) else '-'
        oficina = (
            escape(persona.oficina.nombre)
            if getattr(persona, 'oficina', None)
            else '<span class="text-muted">-</span>'
        )
        area = (
            escape(persona.area.nombre)
            if getattr(persona, 'area', None)
            else '<span class="text-muted">-</span>'
        )

        edit_url = reverse('inventario:personal_update', args=[persona.pk])
        delete_url = reverse('inventario:personal_delete', args=[persona.pk])
        acciones = (
            '<div class="btn-group btn-group-sm" role="group">'
            f'<a href="{edit_url}" class="btn btn-outline-primary" title="Editar">'
            '<i class="fas fa-edit"></i></a>'
            f'<a href="{delete_url}" class="btn btn-outline-danger" title="Eliminar" '
            "onclick=\"return confirm('¿Está seguro de eliminar este personal?');\">"
            '<i class="fas fa-trash"></i></a>'
            '</div>'
        )

        data.append([
            index,
            f"<strong>{nombre_completo}</strong>",
            documento,
            modalidad,
            cargo,
            oficina,
            area,
            acciones,
        ])

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


# ==============================================================================
# VISTAS PARA PERSONAL (CRUD Completo)
# ==============================================================================

class PersonalListView(ListView):
    model = Personal
    template_name = 'inventario/personal_list.html'
    context_object_name = 'personal_list'
    
    def get_queryset(self):
        # El listado se carga vía DataTables (server-side); aquí no traemos registros.
        return Personal.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        return context


class PersonalCreateView(SuccessMessageMixin, CreateView):
    model = Personal
    form_class = PersonalForm
    template_name = 'inventario/personal_form.html'
    success_url = reverse_lazy('inventario:personal_list')
    success_message = "Personal creado exitosamente."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nuevo Personal'
        context['action'] = 'Crear'
        return context


class PersonalUpdateView(SuccessMessageMixin, UpdateView):
    model = Personal
    form_class = PersonalForm
    template_name = 'inventario/personal_form.html'
    success_url = reverse_lazy('inventario:personal_list')
    success_message = "Personal actualizado exitosamente."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Personal'
        context['action'] = 'Actualizar'
        return context


class PersonalDeleteView(SuccessMessageMixin, DeleteView):
    model = Personal
    template_name = 'inventario/personal_confirm_delete.html'
    success_url = reverse_lazy('inventario:personal_list')
    success_message = "Personal eliminado exitosamente."
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


# ==============================================================================
# VISTA AJAX PARA BUSCAR PERSONAL
# ==============================================================================

@require_http_methods(["GET"])
def buscar_personal(request):
    """Vista AJAX para buscar personal por apellidos (y nombres) para el formulario de bienes"""
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'personal': [], 'results': []})
    
    # Buscar por apellidos o nombres (icontains)
    personal_list = Personal.objects.filter(
        Q(apellidos__icontains=q) | Q(nombres__icontains=q) | Q(numero_documento__icontains=q)
    ).select_related('area', 'area__local', 'oficina').order_by('apellidos', 'nombres')[:25]
    
    results = []
    select2_results = []
    for p in personal_list:
        display = f"{p.apellidos}, {p.nombres}"
        if p.numero_documento:
            display = f"{display} ({p.numero_documento})"
        results.append({
            'id': p.id,
            'apellidos': p.apellidos,
            'nombres': p.nombres,
            'display': display,
        })
        select2_results.append({
            'id': p.id,
            'text': display,
        })
    
    return JsonResponse({'personal': results, 'results': select2_results})
