"""
Helpers de control de acceso por rol.

Reglas del sistema:
- El **Administrador** es superusuario (is_superuser=True): pasa TODOS los
  chequeos automáticamente, sin necesidad de asignarle permisos uno por uno.
- El **Trabajador** es un usuario normal que pertenece al grupo "Trabajador".
  Puede ver todo en solo lectura y, además, registrar traslados de bienes
  (permiso ``traslados.add_trasladobien``).

Cómo usar estos helpers:

    # --- Vistas basadas en CLASES (CreateView/UpdateView/DeleteView) ---
    from inventario.permisos import PermisoRequeridoMixin

    class BienCreateView(PermisoRequeridoMixin, CreateView):
        permission_required = 'bienes.add_bien'
        ...

    # --- Vistas basadas en FUNCIONES ---
    from inventario.permisos import permiso_requerido, solo_superusuario

    @permiso_requerido('traslados.add_trasladobien')
    def ejecutar_traslado(request):
        ...

    @solo_superusuario   # operaciones de sistema (cierre anual, carga masiva)
    def cierre_anio_fiscal(request):
        ...

Si un usuario con sesión iniciada intenta entrar a algo para lo que no tiene
permiso, NO se le muestra un 403 técnico: se le regresa al inicio con un
mensaje claro. En peticiones AJAX se responde con un JSON 403.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import redirect

# A dónde se manda al usuario logueado pero sin permiso.
_INICIO = 'inventario:home'
_MENSAJE_SIN_PERMISO = 'No tienes permisos para realizar esa acción.'


def _es_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _denegar(request):
    """Respuesta estándar cuando falta permiso (usuario ya autenticado)."""
    if _es_ajax(request):
        return JsonResponse(
            {'success': False, 'error': _MENSAJE_SIN_PERMISO}, status=403
        )
    messages.error(request, _MENSAJE_SIN_PERMISO)
    return redirect(_INICIO)


class PermisoRequeridoMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Mixin para vistas de clase. Definir el atributo ``permission_required``
    con el código del permiso (ej: 'bienes.change_bien')."""

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return _denegar(self.request)
        return redirect_to_login(
            self.request.get_full_path(), self.get_login_url(), self.get_redirect_field_name()
        )


def permiso_requerido(perm):
    """Decorador para vistas de función. Permite el acceso solo si el usuario
    tiene el permiso ``perm`` (los superusuarios siempre lo tienen)."""

    def decorador(vista):
        @wraps(vista)
        def _envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not request.user.has_perm(perm):
                return _denegar(request)
            return vista(request, *args, **kwargs)

        return _envoltura

    return decorador


def solo_superusuario(vista):
    """Decorador para vistas de función reservadas al Administrador
    (operaciones de sistema: cierre de año fiscal, carga masiva, etc.)."""

    @wraps(vista)
    def _envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_superuser:
            return _denegar(request)
        return vista(request, *args, **kwargs)

    return _envoltura
