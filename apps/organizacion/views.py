from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Entidad, Local, Area, Oficina, UbicacionFisica
from .forms import EntidadForm, LocalForm, AreaForm, OficinaForm, UbicacionFisicaForm
from inventario.permisos import PermisoRequeridoMixin


# ==============================================================================
# VISTAS PARA ENTIDAD (CRUD Completo)
# ==============================================================================

class EntidadListView(ListView):
    model = Entidad
    template_name = 'inventario/entidad_list.html'
    context_object_name = 'entidades'
    
    def get_queryset(self):
        queryset = Entidad.objects.all()
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search) |
                Q(ruc__icontains=search)
            )
        return queryset.order_by('nombre')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        return context


class EntidadCreateView(PermisoRequeridoMixin, SuccessMessageMixin, CreateView):
    permission_required = 'organizacion.add_entidad'
    model = Entidad
    form_class = EntidadForm
    template_name = 'inventario/entidad_form.html'
    success_url = reverse_lazy('inventario:entidad_list')
    success_message = "Entidad creada exitosamente."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nueva Entidad'
        context['action'] = 'Crear'
        return context


class EntidadUpdateView(PermisoRequeridoMixin, SuccessMessageMixin, UpdateView):
    permission_required = 'organizacion.change_entidad'
    model = Entidad
    form_class = EntidadForm
    template_name = 'inventario/entidad_form.html'
    success_url = reverse_lazy('inventario:entidad_list')
    success_message = "Entidad actualizada exitosamente."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Entidad'
        context['action'] = 'Actualizar'
        return context


class EntidadDeleteView(PermisoRequeridoMixin, SuccessMessageMixin, DeleteView):
    permission_required = 'organizacion.delete_entidad'
    model = Entidad
    template_name = 'inventario/entidad_confirm_delete.html'
    success_url = reverse_lazy('inventario:entidad_list')
    success_message = "Entidad eliminada exitosamente."
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


# ==============================================================================
# VISTAS PARA LOCAL (CRUD Completo)
# ==============================================================================

class LocalListView(ListView):
    model = Local
    template_name = 'inventario/local_list.html'
    context_object_name = 'locales'
    
    def get_queryset(self):
        queryset = Local.objects.select_related('entidad').all()
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search) |
                Q(direccion__icontains=search) |
                Q(entidad__nombre__icontains=search)
            )
        return queryset.order_by('nombre')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        return context


class LocalCreateView(PermisoRequeridoMixin, SuccessMessageMixin, CreateView):
    permission_required = 'organizacion.add_local'
    model = Local
    form_class = LocalForm
    template_name = 'inventario/local_form.html'
    success_url = reverse_lazy('inventario:local_list')
    success_message = "Local creado exitosamente."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nuevo Local'
        context['action'] = 'Crear'
        return context


class LocalUpdateView(PermisoRequeridoMixin, SuccessMessageMixin, UpdateView):
    permission_required = 'organizacion.change_local'
    model = Local
    form_class = LocalForm
    template_name = 'inventario/local_form.html'
    success_url = reverse_lazy('inventario:local_list')
    success_message = "Local actualizado exitosamente."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Local'
        context['action'] = 'Actualizar'
        return context


class LocalDeleteView(PermisoRequeridoMixin, SuccessMessageMixin, DeleteView):
    permission_required = 'organizacion.delete_local'
    model = Local
    template_name = 'inventario/local_confirm_delete.html'
    success_url = reverse_lazy('inventario:local_list')
    success_message = "Local eliminado exitosamente."
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


# ==============================================================================
# VISTAS PARA ÁREA (CRUD Completo)
# ==============================================================================

class AreaListView(ListView):
    model = Area
    template_name = 'inventario/area_list.html'
    context_object_name = 'areas'
    
    def get_queryset(self):
        queryset = Area.objects.select_related('local', 'local__entidad').all()
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search) |
                Q(siglas__icontains=search) |
                Q(local__nombre__icontains=search)
            )
        return queryset.order_by('local__nombre', 'nombre')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        return context


class AreaCreateView(PermisoRequeridoMixin, SuccessMessageMixin, CreateView):
    permission_required = 'organizacion.add_area'
    model = Area
    form_class = AreaForm
    template_name = 'inventario/area_form.html'
    success_url = reverse_lazy('inventario:area_list')
    success_message = "Área creada exitosamente."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nueva Área'
        context['action'] = 'Crear'
        return context


class AreaUpdateView(PermisoRequeridoMixin, SuccessMessageMixin, UpdateView):
    permission_required = 'organizacion.change_area'
    model = Area
    form_class = AreaForm
    template_name = 'inventario/area_form.html'
    success_url = reverse_lazy('inventario:area_list')
    success_message = "Área actualizada exitosamente."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Área'
        context['action'] = 'Actualizar'
        return context


class AreaDeleteView(PermisoRequeridoMixin, SuccessMessageMixin, DeleteView):
    permission_required = 'organizacion.delete_area'
    model = Area
    template_name = 'inventario/area_confirm_delete.html'
    success_url = reverse_lazy('inventario:area_list')
    success_message = "Área eliminada exitosamente."
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


# ==============================================================================
# VISTAS PARA OFICINA (CRUD Completo)
# ==============================================================================

class OficinaListView(ListView):
    model = Oficina
    template_name = 'inventario/oficina_list.html'
    context_object_name = 'oficinas'
    
    def get_queryset(self):
        queryset = Oficina.objects.select_related('area', 'area__local').all()
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search) |
                Q(codigo_interno__icontains=search) |
                Q(area__nombre__icontains=search)
            )
        return queryset.order_by('area__nombre', 'nombre')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        return context


class OficinaCreateView(PermisoRequeridoMixin, SuccessMessageMixin, CreateView):
    permission_required = 'organizacion.add_oficina'
    model = Oficina
    form_class = OficinaForm
    template_name = 'inventario/oficina_form.html'
    success_url = reverse_lazy('inventario:oficina_list')
    success_message = "Oficina creada exitosamente."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nueva Oficina'
        context['action'] = 'Crear'
        return context


class OficinaUpdateView(PermisoRequeridoMixin, SuccessMessageMixin, UpdateView):
    permission_required = 'organizacion.change_oficina'
    model = Oficina
    form_class = OficinaForm
    template_name = 'inventario/oficina_form.html'
    success_url = reverse_lazy('inventario:oficina_list')
    success_message = "Oficina actualizada exitosamente."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Oficina'
        context['action'] = 'Actualizar'
        return context


class OficinaDeleteView(PermisoRequeridoMixin, SuccessMessageMixin, DeleteView):
    permission_required = 'organizacion.delete_oficina'
    model = Oficina
    template_name = 'inventario/oficina_confirm_delete.html'
    success_url = reverse_lazy('inventario:oficina_list')
    success_message = "Oficina eliminada exitosamente."
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


# ==============================================================================
# VISTAS PARA UBICACIÓN FÍSICA (CRUD Completo)
# ==============================================================================

class UbicacionFisicaListView(ListView):
    model = UbicacionFisica
    template_name = 'inventario/ubicacionfisica_list.html'
    context_object_name = 'ubicaciones'

    def get_queryset(self):
        queryset = UbicacionFisica.objects.select_related('local', 'area', 'oficina').all()
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(detalle__icontains=search) |
                Q(oficina__nombre__icontains=search) |
                Q(area__nombre__icontains=search) |
                Q(local__nombre__icontains=search)
            )
        return queryset.order_by('local__nombre', 'area__nombre', 'oficina__nombre', 'piso', 'detalle')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        return context


class UbicacionFisicaCreateView(PermisoRequeridoMixin, SuccessMessageMixin, CreateView):
    permission_required = 'organizacion.add_ubicacionfisica'
    model = UbicacionFisica
    form_class = UbicacionFisicaForm
    template_name = 'inventario/ubicacionfisica_form.html'
    success_url = reverse_lazy('inventario:ubicacionfisica_list')
    success_message = "Ubicación física creada exitosamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nueva Ubicación Física'
        context['action'] = 'Crear'
        return context


class UbicacionFisicaUpdateView(PermisoRequeridoMixin, SuccessMessageMixin, UpdateView):
    permission_required = 'organizacion.change_ubicacionfisica'
    model = UbicacionFisica
    form_class = UbicacionFisicaForm
    template_name = 'inventario/ubicacionfisica_form.html'
    success_url = reverse_lazy('inventario:ubicacionfisica_list')
    success_message = "Ubicación física actualizada exitosamente."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Ubicación Física'
        context['action'] = 'Actualizar'
        return context


class UbicacionFisicaDeleteView(PermisoRequeridoMixin, SuccessMessageMixin, DeleteView):
    permission_required = 'organizacion.delete_ubicacionfisica'
    model = UbicacionFisica
    template_name = 'inventario/ubicacionfisica_confirm_delete.html'
    success_url = reverse_lazy('inventario:ubicacionfisica_list')
    success_message = "Ubicación física eliminada exitosamente."

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


# ==============================================================================
# VISTAS AJAX PARA ORGANIZACIÓN
# ==============================================================================

@require_http_methods(["GET"])
def obtener_areas_por_local(request):
    """Vista AJAX para obtener áreas filtradas por local"""
    local_id = request.GET.get('local_id')
    if not local_id:
        return JsonResponse({'areas': []})
    
    areas = Area.objects.filter(local_id=local_id).order_by('nombre')
    results = [{'id': a.id, 'nombre': a.nombre, 'siglas': a.siglas or ''} for a in areas]
    
    return JsonResponse({'areas': results})


@require_http_methods(["GET"])
def obtener_oficinas_por_area(request):
    """Vista AJAX para obtener oficinas filtradas por área"""
    area_id = request.GET.get('area_id')
    if not area_id:
        return JsonResponse({'oficinas': []})
    
    oficinas = Oficina.objects.filter(area_id=area_id).order_by('nombre')
    results = [{'id': o.id, 'nombre': o.nombre, 'codigo_interno': o.codigo_interno or ''} for o in oficinas]
    
    return JsonResponse({'oficinas': results})


@require_http_methods(["GET"])
def obtener_ubicaciones_fisicas(request):
    """Vista AJAX para obtener ubicaciones físicas por área/oficina/local."""
    area_id = request.GET.get('area_id')
    oficina_id = request.GET.get('oficina_id')
    local_id = request.GET.get('local_id')
    queryset = UbicacionFisica.objects.filter(activo=True)

    if oficina_id:
        queryset = queryset.filter(oficina_id=oficina_id)
    elif area_id:
        queryset = queryset.filter(area_id=area_id)
    elif local_id:
        queryset = queryset.filter(local_id=local_id)
    else:
        return JsonResponse({'ubicaciones': []})

    results = [{'id': u.id, 'nombre': str(u)} for u in queryset.order_by('piso', 'detalle')]
    return JsonResponse({'ubicaciones': results})
