from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.db.models import Q, Count
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import csv
import unicodedata
from io import TextIOWrapper
from openpyxl import Workbook
from openpyxl.styles import Font
from organizacion.models import Local, Area, Oficina
from personal.models import Personal
from catalogos.models import CuentaContable, Denominacion
from .models import Bien, ParametroSistema, HistoricoDepreciacion, validar_cierre_anterior
from .forms import BienForm


# ==============================================================================
# VISTA HOME (Dashboard)
# ==============================================================================

def home(request):
    """Vista del dashboard principal con estadísticas"""
    import json
    from traslados.models import TrasladoBien
    from bajas.models import BajaBien
    from catalogos.models import Denominacion, CuentaContable as CuentaContableModel
    from organizacion.models import Oficina as OficinaModel

    total_bienes = Bien.objects.exclude(estado='BAJA').count()
    total_baja = Bien.objects.filter(estado='BAJA').count()
    total_personal = Personal.objects.count()
    total_locales = Local.objects.count()
    total_areas = Area.objects.count()
    total_oficinas = OficinaModel.objects.count()
    total_denominaciones = Denominacion.objects.filter(activo=True).count()
    total_traslados = TrasladoBien.objects.count()

    estados_data = list(
        Bien.objects.values('estado')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    adquisicion_data = list(
        Bien.objects.exclude(estado='BAJA')
        .values('forma_adquisicion')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    locales_data = list(
        Bien.objects.exclude(estado='BAJA')
        .values('local__nombre')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    )

    situacion_data = list(
        Bien.objects.exclude(estado='BAJA')
        .values('situacion')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    context = {
        'total_bienes': total_bienes,
        'total_bienes_baja': total_baja,
        'total_personal': total_personal,
        'total_locales': total_locales,
        'total_areas': total_areas,
        'total_oficinas': total_oficinas,
        'total_denominaciones': total_denominaciones,
        'total_traslados': total_traslados,
        'estados_data': estados_data,
        'estados_json': json.dumps(estados_data),
        'adquisicion_json': json.dumps(adquisicion_data),
        'locales_json': json.dumps(locales_data),
        'situacion_json': json.dumps(situacion_data),
    }
    return render(request, 'index.html', context)


# ==============================================================================
# CONSULTA HISTÓRICA
# ==============================================================================

def consulta_historica(request):
    """Consulta histórica del valor neto en una fecha de corte."""
    fecha_corte = None
    resultados = []
    config = None
    valor_uit = Decimal('5500.00')
    divisor = 4
    config_year_used = None

    locales = Local.objects.order_by('nombre')
    denominaciones = Denominacion.objects.order_by('nombre')
    cuentas_contables = CuentaContable.objects.order_by('codigo')

    local_id = ''
    area_id = ''
    oficina_id = ''
    denominacion_id = ''
    cuenta_contable_id = ''

    if request.method == 'POST':
        fecha_corte_str = request.POST.get('fecha_corte')
        local_id = (request.POST.get('local_id') or '').strip()
        area_id = (request.POST.get('area_id') or '').strip()
        oficina_id = (request.POST.get('oficina_id') or '').strip()
        denominacion_id = (request.POST.get('denominacion_id') or '').strip()
        cuenta_contable_id = (request.POST.get('cuenta_contable_id') or '').strip()
        if fecha_corte_str:
            try:
                fecha_corte = datetime.strptime(fecha_corte_str, '%Y-%m-%d').date()
            except ValueError:
                fecha_corte = None

        if fecha_corte:
            config = ParametroSistema.get_config_for_year(fecha_corte.year)
            if config:
                valor_uit = config.valor_uit
                divisor = config.divisor_umbral_depreciacion or 4
                config_year_used = config.anio_fiscal
                if config.anio_fiscal != fecha_corte.year:
                    messages.warning(
                        request,
                        f"No se encontró configuración para {fecha_corte.year}. "
                        f"Se usó la más antigua registrada ({config.anio_fiscal})."
                    )
            else:
                messages.warning(
                    request,
                    "No hay parámetros registrados. Se usarán valores por defecto."
                )

            bienes = Bien.objects.all()
            if local_id:
                bienes = bienes.filter(local_id=local_id)
            if area_id:
                bienes = bienes.filter(area_id=area_id)
            if oficina_id:
                bienes = bienes.filter(oficina_id=oficina_id)
            if denominacion_id:
                bienes = bienes.filter(denominacion_id=denominacion_id)
            if cuenta_contable_id:
                bienes = bienes.filter(cuenta_contable_id=cuenta_contable_id)

            bienes = bienes.order_by('codigo_patrimonial')
            for bien in bienes:
                valor_historico = bien.valor_neto_en(fecha_corte)
                resultados.append({
                    'bien': bien,
                    'valor_historico': valor_historico,
                })

    context = {
        'fecha_corte': fecha_corte,
        'resultados': resultados,
        'valor_uit': valor_uit,
        'divisor': divisor,
        'config_year_used': config_year_used,
        'locales': locales,
        'denominaciones': denominaciones,
        'cuentas_contables': cuentas_contables,
        'selected_local_id': local_id,
        'selected_area_id': area_id,
        'selected_oficina_id': oficina_id,
        'selected_denominacion_id': denominacion_id,
        'selected_cuenta_contable_id': cuenta_contable_id,
    }
    return render(request, 'inventario/consulta_historica.html', context)


# ==============================================================================
# CIERRE DE AÑO FISCAL
# ==============================================================================

def cierre_anio_fiscal(request):
    """Cierre de año fiscal para congelar historial."""
    parametros = ParametroSistema.objects.order_by('anio_fiscal')
    anios_cerrados = set(
        HistoricoDepreciacion.objects.values_list('anio_fiscal', flat=True).distinct()
    )
    anios = [{
        'anio': p.anio_fiscal,
        'cerrado': p.anio_fiscal in anios_cerrados
    } for p in parametros]

    if request.method == 'POST':
        anio_str = request.POST.get('anio_fiscal')
        if not anio_str or not anio_str.isdigit():
            messages.error(request, "Seleccione un año válido para el cierre.")
        else:
            anio = int(anio_str)
            try:
                validar_cierre_anterior(anio)
                fecha_corte = date(anio, 12, 31)
                bienes = Bien.objects.exclude(
                    baja__fecha_resolucion__lte=fecha_corte
                ).select_related('oficina', 'usuario_asignado')

                for bien in bienes:
                    valor_neto = bien.valor_neto_en(fecha_corte)
                    depreciacion_acumulada = bien.valor_adquisicion - valor_neto
                    depreciacion_acumulada = depreciacion_acumulada.quantize(
                        Decimal('0.00'), rounding=ROUND_HALF_UP
                    )

                    HistoricoDepreciacion.objects.update_or_create(
                        bien=bien,
                        anio_fiscal=anio,
                        defaults={
                            'valor_adquisicion_h': bien.valor_adquisicion,
                            'depreciacion_acumulada_h': depreciacion_acumulada,
                            'valor_neto_h': valor_neto,
                            'estado_h': bien.estado,
                            'oficina_h': bien.oficina.nombre if bien.oficina else None,
                            'usuario_h': (
                                f"{bien.usuario_asignado.apellidos}, {bien.usuario_asignado.nombres}"
                                if bien.usuario_asignado else None
                            ),
                            'fecha_cierre': timezone.now(),
                        }
                    )

                messages.success(request, f"Cierre del año {anio} ejecutado correctamente.")
                return redirect('inventario:cierre_anio_fiscal')
            except ValidationError as exc:
                messages.error(request, str(exc))

    context = {
        'anios': anios
    }
    return render(request, 'inventario/cierre_anio_fiscal.html', context)


# ==============================================================================
# IMPORTACIÓN MASIVA DE INVENTARIO
# ==============================================================================

def importar_inventario_view(request):
    """Importa bienes desde un CSV y retorna resultados."""
    if request.method != 'POST':
        return render(request, 'inventario/importar_inventario.html')

    reporte = {
        'total_procesado': 0,
        'total_exito': 0,
        'errores': [],
        'advertencias': []
    }

    archivo = request.FILES.get('archivo_csv')
    if not archivo:
        reporte['errores'].append({
            'fila': '-',
            'motivo': 'No se adjuntó un archivo CSV.'
        })
        return render(request, 'inventario/resultados_importacion.html', {'reporte': reporte})

    try:
        sample = archivo.file.read(1024)
        archivo.file.seek(0)
        try:
            sniffed = csv.Sniffer().sniff(sample.decode('utf-8'), delimiters=';,')
            delimiter = sniffed.delimiter
        except Exception:
            delimiter = ';'
        reader = csv.DictReader(TextIOWrapper(archivo.file, encoding='utf-8-sig'), delimiter=delimiter)
    except Exception:
        reporte['errores'].append({
            'fila': '-',
            'motivo': 'No se pudo leer el archivo CSV.'
        })
        return render(request, 'inventario/resultados_importacion.html', {'reporte': reporte})

    def _valor(col_name, row):
        return (row.get(col_name) or '').strip()

    def _parse_fecha(valor, fila):
        if not valor:
            return None, 'Fecha de referencia vacía'
        valor = valor.strip()
        if valor == '0/01/1900':
            return None, 'Fecha de referencia inválida (0/01/1900)'
        for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
            try:
                return datetime.strptime(valor, fmt).date(), None
            except ValueError:
                continue
        return None, 'Fecha de referencia inválida'

    def _singularizar(token):
        if token.endswith('ES') and len(token) > 4:
            return token[:-2]
        if token.endswith('S') and len(token) > 3:
            return token[:-1]
        return token

    def _normalizar(texto):
        if texto is None:
            return ''
        texto = unicodedata.normalize('NFD', str(texto))
        texto = ''.join(ch for ch in texto if unicodedata.category(ch) != 'Mn')
        texto = ''.join(ch if ch.isalnum() else ' ' for ch in texto)
        return ' '.join(texto.upper().split())

    def _tokenizar(texto):
        tokens = [_singularizar(t) for t in _normalizar(texto).split(' ') if t]
        return set(tokens)

    def _buscar_coincidencia(qs, texto, field_name):
        if not texto:
            return None
        tokens_busqueda = _tokenizar(texto)
        if not tokens_busqueda:
            return None
        candidatos = list(qs)
        for candidato in candidatos:
            tokens_cand = _tokenizar(getattr(candidato, field_name, ''))
            if tokens_busqueda.issubset(tokens_cand):
                return candidato
        return None

    def _parse_decimal(valor):
        if valor is None:
            return None
        texto = str(valor).strip()
        if not texto:
            return None
        texto = texto.replace(' ', '')
        if ',' in texto and '.' in texto:
            texto = texto.replace(',', '')
        elif ',' in texto and '.' not in texto:
            texto = texto.replace('.', '').replace(',', '.')
        return Decimal(texto)

    pendientes = []
    headers_csv = reader.fieldnames or []
    filas_fallidas = []

    for idx, row in enumerate(reader, start=2):
        reporte['total_procesado'] += 1
        try:
            codigo_raw = _valor('codigo_patrimonial_completo', row)
            codigo_limpio = codigo_raw.replace('-', '').strip()
            if len(codigo_limpio) < 12:
                raise ValidationError(f'Código incompleto: {codigo_raw}')
            if len(codigo_limpio) > 12:
                codigo_limpio = codigo_limpio[:12]
            codigo_base = codigo_limpio[:8]
            correlativo_str = codigo_limpio[-4:]
            if not correlativo_str.isdigit():
                raise ValidationError(f'Correlativo inválido: {codigo_raw}')
            correlativo = int(correlativo_str)

            fecha_ref = _valor('fecha_referencia', row)
            fecha_referencia, warning = _parse_fecha(fecha_ref, idx)
            if warning:
                fecha_referencia = date(1900, 1, 1)
                reporte['advertencias'].append({
                    'fila': idx,
                    'motivo': f"{warning} ('{fecha_ref}'), se usó 1900-01-01"
                })

            denominacion_nombre = _valor('denominacion', row)
            if not denominacion_nombre:
                raise ValidationError('Denominación vacía')
            denominacion = Denominacion.objects.filter(nombre__exact=denominacion_nombre).first()
            if not denominacion:
                raise ValidationError(f"Denominación no encontrada: {denominacion_nombre}")

            responsable_nombre = _valor('responsable', row)
            responsable_dni = _valor('dni_responsable', row)
            responsable = None
            if responsable_dni:
                responsable = Personal.objects.filter(numero_documento=responsable_dni).first()
            if not responsable and responsable_nombre:
                partes = [p for p in responsable_nombre.split() if p]
                query = Personal.objects.all()
                for parte in partes:
                    query = query.filter(
                        Q(nombres__icontains=parte) | Q(apellidos__icontains=parte)
                    )
                responsable = query.first()
            if (responsable_nombre or responsable_dni) and not responsable:
                detalle = responsable_dni or responsable_nombre
                raise ValidationError(f'Responsable no encontrado: {detalle}')

            local_nombre = _valor('local', row)
            area_nombre = _valor('area', row)
            oficina_nombre = _valor('oficina', row)

            local = _buscar_coincidencia(Local.objects.all(), local_nombre, 'nombre')
            if not local:
                raise ValidationError(f'Local no encontrado: {local_nombre}')

            area = None
            if area_nombre:
                area = _buscar_coincidencia(Area.objects.filter(local=local), area_nombre, 'nombre')
                if not area:
                    area = _buscar_coincidencia(Area.objects.all(), area_nombre, 'nombre')
            if area_nombre and not area:
                raise ValidationError(f'Área no encontrada: {area_nombre}')

            oficina = None
            if oficina_nombre and area_nombre and _normalizar(oficina_nombre) == _normalizar(area_nombre):
                oficina = None
            elif oficina_nombre:
                oficina = _buscar_coincidencia(Oficina.objects.filter(area=area), oficina_nombre, 'nombre')
                if not oficina:
                    oficina = _buscar_coincidencia(Oficina.objects.all(), oficina_nombre, 'nombre')
                if not oficina:
                    raise ValidationError(f'Oficina no encontrada: {oficina_nombre}')

            valor_adquisicion_str = _valor('valor_adquisicion', row)
            try:
                valor_adquisicion = _parse_decimal(valor_adquisicion_str)
            except (InvalidOperation, TypeError):
                valor_adquisicion = None
            if valor_adquisicion is None:
                raise ValidationError(f'Valor de adquisición inválido: {valor_adquisicion_str}')

            estado_val = _valor('estado', row) or 'BUENO'
            if estado_val not in dict(Bien.ESTADO_BIEN):
                estado_val = 'BUENO'

            situacion_val = (_valor('situacion', row) or 'USO').upper()
            if 'DESUSO' in situacion_val:
                situacion_val = 'DESUSO'
            elif situacion_val not in dict(Bien.SITUACION_CHOICES):
                situacion_val = 'USO'

            anio_fabricacion_val = _valor('anio_fabricacion', row)
            anio_fabricacion = int(anio_fabricacion_val) if anio_fabricacion_val.isdigit() else None

            forma_adquisicion_val = (_valor('forma_adquisicion', row) or 'COMPRA').upper()
            if forma_adquisicion_val not in dict(Bien.FORMA_ADQUISICION):
                forma_adquisicion_val = 'COMPRA'

            with transaction.atomic():
                bien = Bien.objects.create(
                    denominacion=denominacion,
                    codigo_patrimonial_base=codigo_base,
                    correlativo=correlativo,
                    codigo_patrimonial=codigo_limpio,
                    codigo_interno=_valor('codigo_interno', row) or None,
                    tipo_cuenta='USO_ESTATAL',
                    forma_adquisicion=forma_adquisicion_val,
                    fecha_adquisicion=fecha_referencia,
                    fecha_pecosa=fecha_referencia,
                    resolucion_alta=_valor('resolucion_alta', row) or None,
                    valor_adquisicion=valor_adquisicion,
                    valor_neto=valor_adquisicion,
                    estado=estado_val,
                    situacion=situacion_val,
                    usuario_asignado=responsable,
                    local=local,
                    area=area,
                    oficina=oficina,
                    marca=_valor('marca', row) or None,
                    modelo=_valor('modelo', row) or None,
                    color=_valor('color', row) or None,
                    serie=_valor('serie', row) or None,
                    dimension=_valor('dimension', row) or None,
                    placa=_valor('placa', row) or None,
                    numero_motor=_valor('numero_motor', row) or None,
                    numero_chasis=_valor('numero_chasis', row) or None,
                    anio_fabricacion=anio_fabricacion,
                )
                bien.valor_neto = bien.valor_neto_en()
                bien.save(update_fields=['valor_neto'])

            reporte['total_exito'] += 1
        except ValidationError as exc:
            reporte['errores'].append({
                'fila': idx,
                'motivo': str(exc)
            })
            fila_error = dict(row)
            filas_fallidas.append(fila_error)
        except Exception:
            reporte['errores'].append({
                'fila': idx,
                'motivo': 'Error inesperado al procesar la fila'
            })
            fila_error = dict(row)
            filas_fallidas.append(fila_error)

    if filas_fallidas:
        request.session['import_failed_rows'] = {
            'headers': headers_csv,
            'rows': filas_fallidas,
        }

    context = {'reporte': reporte}
    if filas_fallidas:
        context['descarga_errores_url'] = reverse_lazy('inventario:descargar_errores_importacion')
    return render(request, 'inventario/resultados_importacion.html', context)


def descargar_plantilla_carga(request):
    """Genera una plantilla Excel para carga masiva."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Plantilla"
    headers = [
        'codigo_patrimonial_completo',
        'fecha_referencia',
        'denominacion',
        'responsable',
        'dni_responsable',
        'local',
        'area',
        'oficina',
        'valor_adquisicion',
        'forma_adquisicion',
        'resolucion_alta',
        'codigo_interno',
        'estado',
        'situacion',
        'marca',
        'modelo',
        'color',
        'serie',
        'dimension',
        'placa',
        'numero_motor',
        'numero_chasis',
        'anio_fabricacion',
    ]
    ws.append(headers)

    for col_idx, _ in enumerate(headers, start=1):
        ws.cell(row=1, column=col_idx).font = Font(bold=True)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="plantilla_carga.xlsx"'
    wb.save(response)
    return response


def descargar_errores_importacion(request):
    """Descarga un Excel con filas que fallaron en la importación."""
    data = request.session.get('import_failed_rows')
    if not data:
        messages.warning(request, "No hay errores disponibles para descargar.")
        return redirect('inventario:importar_inventario')

    headers = list(data.get('headers') or [])

    wb = Workbook()
    ws = wb.active
    ws.title = "Errores"
    ws.append(headers)
    for col_idx, _ in enumerate(headers, start=1):
        ws.cell(row=1, column=col_idx).font = Font(bold=True)

    for row in data.get('rows', []):
        ws.append([row.get(h, '') for h in headers])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="errores_carga.xlsx"'
    wb.save(response)
    return response


# ==============================================================================
# VISTAS PARA BIEN (CRUD Completo)
# ==============================================================================

class BienListView(ListView):
    model = Bien
    template_name = 'inventario/bien_list.html'
    context_object_name = 'bienes'
    
    def get_queryset(self):
        return Bien.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['cuentas_contables'] = CuentaContable.objects.order_by('codigo')
        context['estado_choices'] = Bien.ESTADO_BIEN
        context['situacion_choices'] = Bien.SITUACION_CHOICES
        return context


class BienCreateView(SuccessMessageMixin, CreateView):
    model = Bien
    form_class = BienForm
    template_name = 'inventario/bien_form.html'
    success_url = reverse_lazy('inventario:bien_list')
    success_message = "Bien creado exitosamente."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nuevo Bien'
        context['action'] = 'Crear'
        return context


class BienUpdateView(SuccessMessageMixin, UpdateView):
    model = Bien
    form_class = BienForm
    template_name = 'inventario/bien_form.html'
    success_url = reverse_lazy('inventario:bien_list')
    success_message = "Bien actualizado exitosamente."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Bien'
        context['action'] = 'Actualizar'
        return context


class BienDeleteView(SuccessMessageMixin, DeleteView):
    model = Bien
    template_name = 'inventario/bien_confirm_delete.html'
    success_url = reverse_lazy('inventario:bien_list')
    success_message = "Bien eliminado exitosamente."
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


# ==============================================================================
# HISTORIAL DE BIEN
# ==============================================================================

def bien_historial(request, pk):
    """Vista para mostrar el historial de traslados de un bien"""
    from traslados.models import TrasladoBien
    bien = get_object_or_404(
        Bien.objects.select_related(
            'denominacion', 'cuenta_contable', 'usuario_asignado',
            'local', 'area', 'oficina', 'ubicacion_fisica'
        ),
        pk=pk
    )
    
    # Obtener todos los traslados del bien ordenados por fecha (más reciente primero)
    traslados = TrasladoBien.objects.filter(bien=bien).select_related(
        'usuario_origen', 'usuario_origen__area', 'usuario_origen__area__local', 'usuario_origen__oficina',
        'usuario_destino', 'usuario_destino__area', 'usuario_destino__area__local', 'usuario_destino__oficina',
        'local_origen', 'local_destino', 'area_origen', 'area_destino',
        'oficina_origen', 'oficina_destino', 'ubicacion_origen', 'ubicacion_destino'
    ).order_by('-fecha_traslado')
    
    # Construir historial completo incluyendo el estado actual
    historial = []
    
    # Agregar estado actual como último registro
    if bien.usuario_asignado:
        historial.append({
            'fecha': 'Actual',
            'usuario': bien.usuario_asignado,
            'local': bien.local,
            'area': bien.area,
            'oficina': bien.oficina,
            'tipo': 'actual',
            'observaciones': 'Estado actual del bien'
        })
    
    # Agregar traslados históricos
    for traslado in traslados:
        historial.append({
            'id': traslado.id,  # ID del traslado para reimprimir la ficha
            'fecha': traslado.fecha_traslado.strftime('%d/%m/%Y %H:%M'),
            'usuario_origen': traslado.usuario_origen,
            'usuario_destino': traslado.usuario_destino,
            'local_origen': traslado.local_origen,
            'local_destino': traslado.local_destino,
            'area_origen': traslado.area_origen,
            'area_destino': traslado.area_destino,
            'oficina_origen': traslado.oficina_origen,
            'oficina_destino': traslado.oficina_destino,
            'tipo': 'traslado',
            'observaciones': traslado.observaciones or ''
        })
    
    # Si no hay traslados y no hay usuario asignado, mostrar información inicial
    if not historial:
        historial.append({
            'fecha': 'Sin historial',
            'usuario': None,
            'local': bien.local,
            'area': bien.area,
            'oficina': bien.oficina,
            'tipo': 'sin_historial',
            'observaciones': 'No se registran traslados para este bien'
        })
    
    return render(request, 'inventario/bien_historial.html', {
        'bien': bien,
        'historial': historial
    })


# ==============================================================================
# DATATABLE SERVER-SIDE PARA BIENES
# ==============================================================================

@require_http_methods(["GET"])
def bienes_datatable(request):
    from django.utils.html import escape
    from datetime import datetime
    
    def _to_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    draw = _to_int(request.GET.get('draw'), 1)
    start = _to_int(request.GET.get('start'), 0)
    length = _to_int(request.GET.get('length'), 25)
    
    search_value = (request.GET.get('search[value]', '') or '').strip()
    codigo = (request.GET.get('codigo', '') or '').strip()
    denominacion = (request.GET.get('denominacion', '') or '').strip()
    ubicacion = (request.GET.get('ubicacion_fisica', '') or '').strip()
    personal_id = (request.GET.get('personal_id', '') or '').strip()
    cuenta_id = (request.GET.get('cuenta_id', '') or '').strip()
    estado = (request.GET.get('estado', '') or '').strip()
    resolucion_alta = (request.GET.get('resolucion_alta', '') or '').strip()
    fecha_inicio = (request.GET.get('fecha_inicio', '') or '').strip()
    fecha_fin = (request.GET.get('fecha_fin', '') or '').strip()
    situacion = (request.GET.get('situacion', '') or '').strip()

    # 1. BASE LIMPIA (Sin select_related todavía)
    base_qs = Bien.objects.exclude(estado='BAJA')
    records_total = base_qs.count()

    # 2. APLICAR FILTROS
    queryset = base_qs
    has_filters = False

    if search_value:
        has_filters = True
        queryset = queryset.filter(
            Q(descripcion__icontains=search_value) |
            Q(codigo_patrimonial__icontains=search_value) |
            Q(codigo_interno__icontains=search_value) |
            Q(marca__icontains=search_value) |
            Q(modelo__icontains=search_value) |
            Q(placa__icontains=search_value)
        )
    if codigo:
        has_filters = True
        queryset = queryset.filter(codigo_patrimonial__icontains=codigo)
    if denominacion:
        has_filters = True
        queryset = queryset.filter(
            Q(denominacion__nombre__icontains=denominacion) |
            Q(descripcion__icontains=denominacion)
        )
    if ubicacion:
        has_filters = True
        queryset = queryset.filter(
            Q(ubicacion_fisica__detalle__icontains=ubicacion) |
            Q(ubicacion_fisica__area__nombre__icontains=ubicacion) |
            Q(ubicacion_fisica__oficina__nombre__icontains=ubicacion) |
            Q(ubicacion_fisica__local__nombre__icontains=ubicacion)
        )
    if personal_id.isdigit():
        has_filters = True
        queryset = queryset.filter(usuario_asignado_id=int(personal_id))
    if cuenta_id.isdigit():
        has_filters = True
        queryset = queryset.filter(cuenta_contable_id=int(cuenta_id))
    if estado:
        has_filters = True
        queryset = queryset.filter(estado=estado)
    if situacion:
        has_filters = True
        queryset = queryset.filter(situacion=situacion)
    if resolucion_alta:
        has_filters = True
        queryset = queryset.filter(resolucion_alta__icontains=resolucion_alta)
    if fecha_inicio:
        try:
            fecha_i = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            queryset = queryset.filter(fecha_adquisicion__gte=fecha_i)
            has_filters = True
        except ValueError:
            pass
    if fecha_fin:
        try:
            fecha_f = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            queryset = queryset.filter(fecha_adquisicion__lte=fecha_f)
            has_filters = True
        except ValueError:
            pass

    # 3. CONTAR FILTRADOS (Rápido, porque no hay JOINs)
    records_filtered = queryset.count() if has_filters else records_total

    # 4. ORDENAR (Sin el '-id' al final)
    order_column = _to_int(request.GET.get('order[0][column]'), 0)
    order_dir = request.GET.get('order[0][dir]', 'asc')
    order_map = {
        0: 'codigo_patrimonial',
        1: 'descripcion',
        2: 'marca',
        3: 'estado',
        4: 'valor_neto',
        5: 'tasa_depreciacion',
        6: 'vida_util_meses',
        7: 'fecha_pecosa',
        8: 'resolucion_alta',
        9: 'usuario_asignado__apellidos',
        10: 'oficina__nombre',
    }
    order_field = order_map.get(order_column, 'codigo_patrimonial')
    if order_dir == 'desc':
        order_field = f"-{order_field}"
        
    queryset = queryset.order_by(order_field)

    # -------------------------------------------------------------------------
    # EL TRUCO MAESTRO: AISLAR LOS IDs PARA ALIVIAR EL SERVIDOR
    # -------------------------------------------------------------------------
    
    if length <= 0:
        length = 25

    # 5. Extraer SOLO los IDs de la página actual (Paginación súper rápida en BD)
    bienes_ids = list(queryset.values_list('id', flat=True)[start:start + length])

    # 6. Hacer la consulta pesada con JOINs SOLO para los registros que van a la pantalla
    bienes_finales = Bien.objects.filter(id__in=bienes_ids).select_related(
        'denominacion', 'cuenta_contable', 'usuario_asignado',
        'usuario_asignado__area', 'usuario_asignado__oficina',
        'local', 'area', 'oficina', 'ubicacion_fisica'
    )

    # 7. Reordenar en memoria RAM para respetar el orden original de DataTables
    bienes_dict = {bien.id: bien for bien in bienes_finales}
    bienes_ordenados = [bienes_dict[id_] for id_ in bienes_ids if id_ in bienes_dict]

    # -------------------------------------------------------------------------

    # 8. ARMADO DE DATOS
    def truncate_words(text, limit):
        parts = (text or '').split()
        if len(parts) <= limit:
            return text
        return ' '.join(parts[:limit]) + '...'

    def estado_badge(estado, label):
        badge = 'bg-secondary'
        if estado == 'NUEVO':
            badge = 'bg-success'
        elif estado == 'BUENO':
            badge = 'bg-info'
        elif estado == 'REGULAR':
            badge = 'bg-warning'
        elif estado == 'MALO':
            badge = 'bg-danger'
        return f'<span class="badge {badge}">{escape(label)}</span>'

    data = []
        
    # Usamos la lista de objetos ordenados en RAM (bienes_ordenados) en lugar del queryset directo
    for bien in bienes_ordenados:
        codigo = escape(bien.codigo_patrimonial or '')
        descripcion = escape(truncate_words(bien.descripcion or '', 10)) or '-'
        marca_modelo = ''
        if bien.marca or bien.modelo:
            marca_modelo = f"{bien.marca or ''} {bien.modelo or ''}".strip()
            if bien.placa:
                marca_modelo = f"{marca_modelo} / Placa: {bien.placa}"
        else:
            marca_modelo = '-'
        marca_modelo = escape(marca_modelo)
        estado_html = estado_badge(bien.estado, bien.get_estado_display())
        valor_neto = f"S/ {bien.valor_neto:,.2f}" if bien.valor_neto is not None else 'S/ 0.00'
        
        tasa = f"{bien.tasa_depreciacion:,.2f}" if bien.tasa_depreciacion is not None else '-'
        vida_util = f"{bien.vida_util_meses}" if bien.vida_util_meses is not None else '-'
        fecha_pecosa = bien.fecha_pecosa.strftime('%d/%m/%Y') if bien.fecha_pecosa else '-'
        resolucion = escape(bien.resolucion_alta) if bien.resolucion_alta else '-'

        # Validación de usuario para evitar posibles caídas
        usuario = escape(str(bien.usuario_asignado)) if bien.usuario_asignado else 'Sin asignar'
        oficina = escape(truncate_words(bien.oficina.nombre, 3)) if bien.oficina else '-'

        edit_url = reverse('inventario:bien_update', args=[bien.pk])
        historial_url = reverse('inventario:bien_historial', args=[bien.pk])
        traslado_url = reverse('inventario:traslado_bienes_index')
        acciones = (
            '<div class="btn-group btn-group-sm" role="group">'
            f'<a href="{edit_url}" class="btn btn-outline-primary" title="Editar">'
            '<i class="fas fa-edit"></i></a>'
            f'<a href="{historial_url}" class="btn btn-outline-info" title="Ver Historial">'
            '<i class="fas fa-history"></i></a>'
            f'<a href="{traslado_url}?bien_id={bien.pk}" class="btn btn-outline-success" title="Trasladar">'
            '<i class="fas fa-exchange-alt"></i></a>'
            '</div>'
        )

        data.append([
            f'<strong>{codigo}</strong>',
            descripcion,
            marca_modelo,
            estado_html,
            valor_neto,
            tasa,
            vida_util,
            fecha_pecosa,
            resolucion,
            usuario,
            oficina,
            acciones,
        ])

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


# ==============================================================================
# MÓDULO DE FUNCIONES (INDEX)
# ==============================================================================

def funciones_index(request):
    """Vista del menú de funciones"""
    context = {
        'total_bienes': Bien.objects.exclude(estado='BAJA').count(),
        'total_bienes_baja': Bien.objects.filter(estado='BAJA').count(),
        'total_personal': Personal.objects.count(),
        'total_locales': Local.objects.count(),
        'total_areas': Area.objects.count(),
    }
    return render(request, 'inventario/funciones_index.html', context)


# ==============================================================================
# VISTA AJAX PARA CALCULAR VALOR NETO
# ==============================================================================

@require_http_methods(["GET"])
def obtener_valor_neto(request):
    """Vista AJAX para calcular el valor neto actualizado"""
    valor_adquisicion = request.GET.get('valor_adquisicion')
    fecha_pecosa = request.GET.get('fecha_pecosa')
    tasa_depreciacion = request.GET.get('tasa_depreciacion')
    cuenta_contable_id = request.GET.get('cuenta_contable_id')

    if not valor_adquisicion:
        return JsonResponse({'valor_neto': None})

    try:
        valor_adquisicion_decimal = Decimal(valor_adquisicion)
    except (InvalidOperation, TypeError):
        return JsonResponse({'valor_neto': None})

    fecha_pecosa_date = None
    if fecha_pecosa:
        try:
            fecha_pecosa_date = datetime.strptime(fecha_pecosa, '%Y-%m-%d').date()
        except ValueError:
            fecha_pecosa_date = None

    tasa_decimal = None
    if tasa_depreciacion:
        try:
            tasa_decimal = Decimal(tasa_depreciacion)
        except (InvalidOperation, TypeError):
            tasa_decimal = None

    cuenta_contable = None
    if cuenta_contable_id:
        cuenta_contable = CuentaContable.objects.filter(pk=cuenta_contable_id).first()

    bien = Bien(
        valor_adquisicion=valor_adquisicion_decimal,
        fecha_pecosa=fecha_pecosa_date,
        tasa_depreciacion=tasa_decimal,
        cuenta_contable=cuenta_contable,
    )

    valor_neto = bien.valor_neto_actualizado
    if valor_neto is None:
        return JsonResponse({'valor_neto': None})

    valor_neto_decimal = Decimal(valor_neto).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return JsonResponse({'valor_neto': f"{valor_neto_decimal:.2f}"})


# ==============================================================================
# VISTAS AJAX DE BÚSQUEDA DE BIENES
# ==============================================================================

@require_http_methods(["GET"])
def buscar_bien_ajax(request):
    """Vista AJAX para buscar bienes para dar de baja"""
    from bajas.models import BajaBien
    tipo_busqueda = request.GET.get('tipo_busqueda', '')
    valor_busqueda = request.GET.get('valor_busqueda', '').strip()
    
    if not tipo_busqueda or not valor_busqueda or len(valor_busqueda) < 2:
        return JsonResponse({'bienes': [], 'error': 'Ingrese al menos 2 caracteres para buscar.'})
    
    # Buscar bienes según el tipo
    bienes = Bien.objects.exclude(estado='BAJA').select_related(
        'denominacion', 'cuenta_contable', 'usuario_asignado',
        'local', 'area', 'oficina'
    )
    
    if tipo_busqueda == 'codigo_patrimonial':
        bienes = bienes.filter(codigo_patrimonial__icontains=valor_busqueda)
    elif tipo_busqueda == 'codigo_interno':
        bienes = bienes.filter(codigo_interno__icontains=valor_busqueda)
    elif tipo_busqueda == 'denominacion':
        bienes = bienes.filter(
            Q(descripcion__icontains=valor_busqueda) |
            Q(denominacion__nombre__icontains=valor_busqueda)
        )
    
    # Limitar a 20 resultados
    bienes = bienes[:20]
    
    # Verificar cuáles ya tienen baja
    bienes_con_baja = BajaBien.objects.filter(bien_id__in=[b.id for b in bienes]).values_list('bien_id', flat=True)
    
    results = []
    for bien in bienes:
        # Verificar si ya tiene baja
        tiene_baja = bien.id in bienes_con_baja
        
        results.append({
            'id': bien.id,
            'codigo_patrimonial': bien.codigo_patrimonial or 'N/A',
            'codigo_interno': bien.codigo_interno or 'N/A',
            'denominacion': bien.denominacion.nombre if bien.denominacion else bien.descripcion or 'N/A',
            'grupo_generico': bien.grupo_generico or 'N/A',
            'clase': bien.clase or 'N/A',
            'tipo_cuenta': bien.get_tipo_cuenta_display(),
            'cuenta_contable': str(bien.cuenta_contable) if bien.cuenta_contable else 'N/A',
            'forma_adquisicion': bien.get_forma_adquisicion_display(),
            'resolucion_alta': bien.resolucion_alta or 'N/A',
            'fecha_adquisicion': bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else 'N/A',
            'valor_adquisicion': str(bien.valor_adquisicion),
            'valor_neto': str(bien.valor_neto),
            'estado': bien.get_estado_display(),
            'usuario_asignado': f"{bien.usuario_asignado.apellidos}, {bien.usuario_asignado.nombres}" if bien.usuario_asignado else 'N/A',
            'local': bien.local.nombre,
            'area': bien.area.nombre if bien.area else 'N/A',
            'oficina': bien.oficina.nombre if bien.oficina else 'N/A',
            'tiene_baja': tiene_baja
        })
    
    return JsonResponse({'bienes': results})


@require_http_methods(["GET"])
def buscar_bien_etiquetas(request):
    """Vista AJAX para buscar bienes en generación de etiquetas.

    Optimización: cuando la búsqueda parece un código patrimonial (empieza por
    dígito) se usa ``istartswith``, que es "sargable" en SQL Server y aprovecha
    el índice de ``codigo_patrimonial`` en lugar de hacer un LIKE '%...%' con
    comodín inicial (que fuerza un escaneo completo de la tabla). La búsqueda por
    nombre se resuelve contra el catálogo de denominaciones (tabla pequeña).
    """
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'results': []})

    # Mismo patrón que la lista de Bienes Patrimoniales (que carga al instante):
    # - SIN select_related / SIN JOINs durante el filtrado.
    # - Se busca en la columna denormalizada 'descripcion' (que ya está en la
    #   tabla Bien y se auto-rellena desde la denominación), evitando el JOIN a
    #   la tabla de denominaciones.
    # - Se traen solo las columnas necesarias con .values() y se limita a 20.
    codigo_normalizado = query.replace('.', '').replace('-', '').replace(' ', '')
    if codigo_normalizado.isdigit():
        # Búsqueda por código: istartswith es "sargable" y usa el índice.
        filtro = Q(codigo_patrimonial__istartswith=query)
        if codigo_normalizado != query:
            filtro |= Q(codigo_patrimonial__istartswith=codigo_normalizado)
    else:
        # Búsqueda por nombre directamente sobre la tabla Bien (sin JOIN).
        filtro = Q(descripcion__icontains=query)

    bienes = Bien.objects.exclude(estado='BAJA').filter(filtro).values(
        'id', 'codigo_patrimonial', 'descripcion'
    ).order_by('codigo_patrimonial')[:20]

    results = [
        {
            'id': bien['id'],
            'text': f"{bien['codigo_patrimonial'] or 'N/A'} - {bien['descripcion'] or 'N/A'}"
        }
        for bien in bienes
    ]

    return JsonResponse({'results': results})


@require_http_methods(["GET"])
def obtener_bien_ajax(request, pk):
    """Vista AJAX para obtener los datos completos de un bien"""
    bien = get_object_or_404(Bien.objects.select_related(
        'denominacion', 'cuenta_contable', 'usuario_asignado',
        'local', 'area', 'oficina'
    ), pk=pk)
    
    # Verificar si ya tiene baja
    tiene_baja = hasattr(bien, 'baja')
    
    return JsonResponse({
        'id': bien.id,
        'codigo_patrimonial': bien.codigo_patrimonial or 'N/A',
        'codigo_interno': bien.codigo_interno or 'N/A',
        'denominacion': bien.denominacion.nombre if bien.denominacion else bien.descripcion or 'N/A',
        'grupo_generico': bien.grupo_generico or 'N/A',
        'clase': bien.clase or 'N/A',
        'tipo_cuenta': bien.get_tipo_cuenta_display(),
        'cuenta_contable': str(bien.cuenta_contable) if bien.cuenta_contable else 'N/A',
        'forma_adquisicion': bien.get_forma_adquisicion_display(),
        'resolucion_alta': bien.resolucion_alta or 'N/A',
        'fecha_adquisicion': bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else 'N/A',
        'valor_adquisicion': str(bien.valor_adquisicion),
        'valor_neto': str(bien.valor_neto),
        'estado': bien.get_estado_display(),
        'usuario_asignado': f"{bien.usuario_asignado.apellidos}, {bien.usuario_asignado.nombres}" if bien.usuario_asignado else 'N/A',
        'local': bien.local.nombre,
        'area': bien.area.nombre if bien.area else 'N/A',
        'oficina': bien.oficina.nombre if bien.oficina else 'N/A',
        'tiene_baja': tiene_baja
    })
