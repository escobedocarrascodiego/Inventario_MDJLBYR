from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime
import json
from organizacion.models import Local, Area, Oficina, UbicacionFisica
from personal.models import Personal
from bienes.models import Bien
from .models import TrasladoBien, EscaneoCodigoBarra


# ==============================================================================
# HELPERS DE ESCANEO
# ==============================================================================

def _get_request_session_key(request):
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key
    return session_key


def _serialize_escaneo(escaneo):
    descripcion = ''
    usuario_actual = ''
    usuario_actual_id = None
    oficina_actual = ''
    if escaneo.bien:
        descripcion = escaneo.bien.denominacion.nombre if escaneo.bien.denominacion else (escaneo.bien.descripcion or '')
        if escaneo.bien.usuario_asignado:
            usuario_actual = str(escaneo.bien.usuario_asignado)
            usuario_actual_id = escaneo.bien.usuario_asignado.id
        if escaneo.bien.oficina:
            oficina_actual = escaneo.bien.oficina.nombre
    return {
        'id': escaneo.id,
        'codigo_patrimonial': escaneo.codigo_patrimonial,
        'descripcion': descripcion or 'N/A',
        'usuario_actual': usuario_actual or 'N/A',
        'usuario_actual_id': usuario_actual_id,
        'oficina_actual': oficina_actual or 'N/A',
        'estado': escaneo.estado,
        'mensaje_error': escaneo.mensaje_error or '',
    }


# ==============================================================================
# MÓDULO DE ESCANEO DE CÓDIGOS DE BARRAS
# ==============================================================================

def escanear_codigos_barras(request):
    """Vista principal para escanear códigos de barras y preparar traslados."""
    session_key = _get_request_session_key(request)
    escaneos = EscaneoCodigoBarra.objects.filter(
        session_key=session_key,
        estado__in=['PENDIENTE', 'ERROR']
    ).select_related('bien', 'bien__denominacion', 'bien__usuario_asignado', 'bien__oficina')
    escaneos_data = [_serialize_escaneo(e) for e in escaneos]
    locales = Local.objects.all().order_by('nombre')
    areas = Area.objects.all().order_by('nombre')

    return render(request, 'inventario/escanear_codigos_barras.html', {
        'escaneos_json': json.dumps(escaneos_data),
        'locales': locales,
        'areas': areas
    })


@require_http_methods(["POST"])
def registrar_escaneo_codigo(request):
    """Registra un código escaneado y lo guarda en la lista temporal."""
    data = {}
    if request.body:
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            data = {}

    codigo = (data.get('codigo') or request.POST.get('codigo') or '').strip()
    if not codigo:
        return JsonResponse({'success': False, 'error': 'Debe ingresar un código.'})

    session_key = _get_request_session_key(request)
    existente = EscaneoCodigoBarra.objects.filter(
        session_key=session_key,
        estado__in=['PENDIENTE', 'ERROR'],
        codigo_patrimonial=codigo
    ).select_related('bien', 'bien__denominacion', 'bien__usuario_asignado', 'bien__oficina').first()
    if existente:
        return JsonResponse({
            'success': True,
            'exists': True,
            'message': 'El código ya está en la lista.',
            'escaneo': _serialize_escaneo(existente)
        })

    bien = Bien.objects.select_related('denominacion', 'usuario_asignado', 'oficina').filter(codigo_patrimonial=codigo).first()
    if not bien or bien.estado == 'BAJA':
        escaneo = EscaneoCodigoBarra.objects.create(
            session_key=session_key,
            codigo_patrimonial=codigo,
            estado='ERROR',
            mensaje_error='Bien no encontrado o dado de baja'
        )
        return JsonResponse({
            'success': True,
            'escaneo': _serialize_escaneo(escaneo),
            'message': 'El código no corresponde a un bien activo.'
        })

    escaneo = EscaneoCodigoBarra.objects.create(
        session_key=session_key,
        codigo_patrimonial=codigo,
        bien=bien
    )
    return JsonResponse({
        'success': True,
        'escaneo': _serialize_escaneo(escaneo),
        'message': 'Código agregado.'
    })


@require_http_methods(["POST"])
def eliminar_escaneo_codigo(request, pk):
    """Elimina un escaneo pendiente de la lista."""
    session_key = _get_request_session_key(request)
    escaneo = get_object_or_404(
        EscaneoCodigoBarra,
        pk=pk,
        session_key=session_key,
        estado__in=['PENDIENTE', 'ERROR']
    )
    escaneo.delete()
    return JsonResponse({'success': True})


@require_http_methods(["POST"])
def limpiar_escaneos_codigo(request):
    """Limpia todos los escaneos pendientes de la sesión."""
    session_key = _get_request_session_key(request)
    EscaneoCodigoBarra.objects.filter(
        session_key=session_key,
        estado__in=['PENDIENTE', 'ERROR']
    ).delete()
    return JsonResponse({'success': True})


@require_http_methods(["POST"])
def ejecutar_traslado_escaneados(request):
    """Ejecuta el traslado de todos los bienes escaneados pendientes."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}

    usuario_destino_id = data.get('usuario_destino_id')
    local_destino_id = data.get('local_destino_id')
    area_destino_id = data.get('area_destino_id')
    oficina_destino_id = data.get('oficina_destino_id')
    ubicacion_destino_id = data.get('ubicacion_destino_id')
    observaciones = data.get('observaciones', '')

    if not usuario_destino_id:
        return JsonResponse({'success': False, 'error': 'Debe seleccionar usuario destino.'})

    session_key = _get_request_session_key(request)
    escaneos = EscaneoCodigoBarra.objects.filter(
        session_key=session_key,
        estado='PENDIENTE',
        bien__isnull=False
    ).select_related(
        'bien', 'bien__denominacion', 'bien__usuario_asignado',
        'bien__local', 'bien__area', 'bien__oficina'
    )

    if not escaneos.exists():
        return JsonResponse({'success': False, 'error': 'No hay bienes escaneados pendientes.'})

    try:
        usuario_destino = Personal.objects.get(id=usuario_destino_id)
    except Personal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuario destino no encontrado.'})

    duplicados_usuario = [
        escaneo.codigo_patrimonial
        for escaneo in escaneos
        if escaneo.bien and escaneo.bien.usuario_asignado_id == usuario_destino.id
    ]
    if duplicados_usuario:
        codigos_texto = ", ".join(duplicados_usuario[:8])
        if len(duplicados_usuario) > 8:
            codigos_texto += "..."
        return JsonResponse({
            'success': False,
            'error': (
                'El usuario destino no puede ser el mismo usuario actual de los bienes. '
                f'Códigos: {codigos_texto}'
            )
        })

    local_destino = Local.objects.filter(id=local_destino_id).first() if local_destino_id else None
    area_destino = Area.objects.filter(id=area_destino_id).first() if area_destino_id else None
    oficina_destino = Oficina.objects.filter(id=oficina_destino_id).first() if oficina_destino_id else None
    ubicacion_destino = UbicacionFisica.objects.filter(id=ubicacion_destino_id).first() if ubicacion_destino_id else None

    if not local_destino and usuario_destino.area and usuario_destino.area.local:
        local_destino = usuario_destino.area.local
    if not area_destino and usuario_destino.area:
        area_destino = usuario_destino.area
    if not oficina_destino and usuario_destino.oficina:
        oficina_destino = usuario_destino.oficina

    if not local_destino:
        return JsonResponse({'success': False, 'error': 'Debe especificar local destino.'})

    batch_time = timezone.now()
    trasladados = 0
    errores = []
    traslados_ids = []

    for escaneo in escaneos:
        bien = escaneo.bien
        if not bien or bien.estado == 'BAJA':
            escaneo.estado = 'ERROR'
            escaneo.mensaje_error = 'Bien no encontrado o dado de baja'
            escaneo.save(update_fields=['estado', 'mensaje_error'])
            errores.append({'codigo': escaneo.codigo_patrimonial, 'error': escaneo.mensaje_error})
            continue

        if not bien.usuario_asignado or not bien.local:
            escaneo.estado = 'ERROR'
            escaneo.mensaje_error = 'Bien sin usuario o local de origen'
            escaneo.save(update_fields=['estado', 'mensaje_error'])
            errores.append({'codigo': escaneo.codigo_patrimonial, 'error': escaneo.mensaje_error})
            continue

        traslado = TrasladoBien.objects.create(
            bien=bien,
            usuario_origen=bien.usuario_asignado,
            local_origen=bien.local,
            area_origen=bien.area,
            oficina_origen=bien.oficina,
            ubicacion_origen=bien.ubicacion_fisica,
            usuario_destino=usuario_destino,
            local_destino=local_destino,
            area_destino=area_destino,
            oficina_destino=oficina_destino,
            ubicacion_destino=ubicacion_destino,
            observaciones=observaciones
        )
        traslado.fecha_traslado = batch_time
        traslado.save(update_fields=['fecha_traslado'])

        bien.usuario_asignado = usuario_destino
        bien.local = local_destino
        bien.area = area_destino
        bien.oficina = oficina_destino
        bien.ubicacion_fisica = ubicacion_destino
        bien.save()

        escaneo.estado = 'PROCESADO'
        escaneo.traslado = traslado
        escaneo.mensaje_error = ''
        escaneo.save(update_fields=['estado', 'traslado', 'mensaje_error'])

        trasladados += 1
        traslados_ids.append(traslado.id)

    if trasladados == 0:
        return JsonResponse({
            'success': False,
            'error': 'No se pudo trasladar ningún bien.',
            'errores': errores
        })

    return JsonResponse({
        'success': True,
        'message': f'Se trasladaron {trasladados} bien(es) exitosamente.',
        'traslados_ids': traslados_ids,
        'errores': errores
    })


# ==============================================================================
# MÓDULO DE TRASLADO DE BIENES (MANUAL)
# ==============================================================================

def traslado_bienes_index(request):
    """Vista principal para el formulario de traslado de bienes"""
    locales = Local.objects.all().order_by('nombre')
    areas = Area.objects.all().order_by('nombre')
    personal_list = Personal.objects.select_related('area', 'area__local', 'oficina').all().order_by('apellidos', 'nombres')

    preload = None
    bien_id = request.GET.get('bien_id')
    if bien_id:
        try:
            bien = Bien.objects.select_related(
                'usuario_asignado', 'usuario_asignado__area',
                'usuario_asignado__area__local', 'usuario_asignado__oficina',
                'local', 'area', 'oficina', 'ubicacion_fisica', 'denominacion'
            ).get(pk=bien_id)
            preload = {
                'bien_id': bien.pk,
                'codigo_patrimonial': bien.codigo_patrimonial or '',
                'descripcion': bien.denominacion.nombre if bien.denominacion else (bien.descripcion or ''),
                'usuario_id': bien.usuario_asignado_id,
                'usuario_nombre': str(bien.usuario_asignado) if bien.usuario_asignado else '',
                'local_id': bien.local_id,
                'area_id': bien.area_id,
                'oficina_id': bien.oficina_id,
                'ubicacion_id': bien.ubicacion_fisica_id,
            }
        except Bien.DoesNotExist:
            pass

    return render(request, 'inventario/traslado_bienes_form.html', {
        'locales': locales,
        'areas': areas,
        'personal_list': personal_list,
        'preload_json': json.dumps(preload) if preload else 'null',
    })


@require_http_methods(["GET"])
def obtener_bienes_por_usuario_ubicacion(request):
    """Vista AJAX para obtener bienes según usuario y ubicación"""
    usuario_id = request.GET.get('usuario_id')
    local_id = request.GET.get('local_id')
    area_id = request.GET.get('area_id')
    oficina_id = request.GET.get('oficina_id')
    ubicacion_id = request.GET.get('ubicacion_id')
    
    if not usuario_id:
        return JsonResponse({'bienes': [], 'error': 'Debe seleccionar un usuario.'})
    
    try:
        usuario = Personal.objects.get(id=usuario_id)
    except Personal.DoesNotExist:
        return JsonResponse({'bienes': [], 'error': 'Usuario no encontrado.'})
    
    # Filtrar bienes según usuario y ubicación
    bienes = Bien.objects.exclude(estado='BAJA').filter(
        usuario_asignado=usuario
    ).select_related(
        'denominacion', 'local', 'area', 'oficina', 'ubicacion_fisica'
    )
    
    # Filtrar por ubicación si se proporciona
    if local_id:
        bienes = bienes.filter(local_id=local_id)
    if area_id:
        bienes = bienes.filter(area_id=area_id)
    if oficina_id:
        bienes = bienes.filter(oficina_id=oficina_id)
    if ubicacion_id:
        bienes = bienes.filter(ubicacion_fisica_id=ubicacion_id)
    
    bienes = bienes.order_by('codigo_patrimonial')
    
    results = []
    for bien in bienes:
        results.append({
            'id': bien.id,
            'codigo_patrimonial': bien.codigo_patrimonial or 'N/A',
            'descripcion': bien.denominacion.nombre if bien.denominacion else bien.descripcion or 'N/A',
            'local': bien.local.nombre if bien.local else 'N/A',
            'area': bien.area.nombre if bien.area else 'N/A',
            'oficina': bien.oficina.nombre if bien.oficina else 'N/A',
            'ubicacion_fisica': str(bien.ubicacion_fisica) if bien.ubicacion_fisica else 'N/A',
        })
    
    return JsonResponse({'bienes': results})


@require_http_methods(["GET"])
def obtener_ubicacion_usuario(request, pk):
    """Vista AJAX para obtener la ubicación (local, área, oficina) de un usuario"""
    try:
        usuario = Personal.objects.select_related('area', 'area__local', 'oficina').get(id=pk)
        
        return JsonResponse({
            'id': usuario.id,
            'nombres': usuario.nombres,
            'apellidos': usuario.apellidos,
            'local_id': usuario.area.local.id if usuario.area and usuario.area.local else None,
            'local_nombre': usuario.area.local.nombre if usuario.area and usuario.area.local else None,
            'area_id': usuario.area.id if usuario.area else None,
            'area_nombre': usuario.area.nombre if usuario.area else None,
            'oficina_id': usuario.oficina.id if usuario.oficina else None,
            'oficina_nombre': usuario.oficina.nombre if usuario.oficina else None,
        })
    except Personal.DoesNotExist:
        return JsonResponse({'error': 'Usuario no encontrado.'}, status=404)


@require_http_methods(["POST"])
def ejecutar_traslado(request):
    """Vista para ejecutar el traslado de bienes"""
    try:
        data = json.loads(request.body)
        bienes_ids = data.get('bienes_ids', [])
        usuario_origen_id = data.get('usuario_origen_id')
        local_origen_id = data.get('local_origen_id')
        area_origen_id = data.get('area_origen_id')
        oficina_origen_id = data.get('oficina_origen_id')
        ubicacion_origen_id = data.get('ubicacion_origen_id')
        usuario_destino_id = data.get('usuario_destino_id')
        local_destino_id = data.get('local_destino_id')
        area_destino_id = data.get('area_destino_id')
        oficina_destino_id = data.get('oficina_destino_id')
        ubicacion_destino_id = data.get('ubicacion_destino_id')
        documento_autoriza = (data.get('documento_autoriza') or '').strip()
        observaciones = data.get('observaciones', '')

        if not bienes_ids:
            return JsonResponse({'success': False, 'error': 'Debe seleccionar al menos un bien para trasladar.'})
        
        if not usuario_origen_id or not usuario_destino_id:
            return JsonResponse({'success': False, 'error': 'Debe seleccionar usuario origen y destino.'})
        
        # Obtener objetos
        usuario_origen = Personal.objects.get(id=usuario_origen_id)
        usuario_destino = Personal.objects.get(id=usuario_destino_id)
        local_origen = Local.objects.get(id=local_origen_id) if local_origen_id else None
        local_destino = Local.objects.get(id=local_destino_id) if local_destino_id else None
        area_origen = Area.objects.get(id=area_origen_id) if area_origen_id else None
        area_destino = Area.objects.get(id=area_destino_id) if area_destino_id else None
        oficina_origen = Oficina.objects.get(id=oficina_origen_id) if oficina_origen_id else None
        oficina_destino = Oficina.objects.get(id=oficina_destino_id) if oficina_destino_id else None
        ubicacion_origen = UbicacionFisica.objects.get(id=ubicacion_origen_id) if ubicacion_origen_id else None
        ubicacion_destino = UbicacionFisica.objects.get(id=ubicacion_destino_id) if ubicacion_destino_id else None
        
        # Validar que se proporcionen los datos mínimos
        if not local_origen or not local_destino:
            return JsonResponse({'success': False, 'error': 'Debe especificar local origen y destino.'})
        
        # Procesar cada bien (misma fecha_traslado para el lote)
        batch_time = timezone.now()
        bienes_trasladados = []
        traslados_ids = []
        for bien_id in bienes_ids:
            try:
                bien = Bien.objects.get(id=bien_id)
                
                # Crear registro de traslado
                traslado = TrasladoBien.objects.create(
                    bien=bien,
                    usuario_origen=usuario_origen,
                    local_origen=local_origen,
                    area_origen=area_origen,
                    oficina_origen=oficina_origen,
                    ubicacion_origen=ubicacion_origen,
                    usuario_destino=usuario_destino,
                    local_destino=local_destino,
                    area_destino=area_destino,
                    oficina_destino=oficina_destino,
                    ubicacion_destino=ubicacion_destino,
                    documento_autoriza=documento_autoriza,
                    observaciones=observaciones
                )
                # Forzar el mismo timestamp para todo el lote
                traslado.fecha_traslado = batch_time
                traslado.save(update_fields=['fecha_traslado'])

                # Actualizar el bien
                bien.usuario_asignado = usuario_destino
                bien.local = local_destino
                bien.area = area_destino
                bien.oficina = oficina_destino
                bien.ubicacion_fisica = ubicacion_destino
                bien.save()
                
                bienes_trasladados.append(bien.codigo_patrimonial)
                traslados_ids.append(traslado.id)
            except Bien.DoesNotExist:
                continue
        
        if bienes_trasladados:
            return JsonResponse({
                'success': True,
                'message': f'Se trasladaron {len(bienes_trasladados)} bien(es) exitosamente.',
                'bienes': bienes_trasladados,
                'traslados_ids': traslados_ids
            })
        else:
            return JsonResponse({'success': False, 'error': 'No se pudo trasladar ningún bien.'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error al procesar el traslado: {str(e)}'})


# ==============================================================================
# REPORTE DE ASIGNACIÓN DE TRASLADO (PDF)
# ==============================================================================

def generar_reporte_asignacion_traslado(request, traslado_id):
    """Genera la Ficha de Asignación en PDF desde la plantilla HTML (xhtml2pdf)."""
    from io import BytesIO
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa

    traslado = get_object_or_404(
        TrasladoBien.objects.select_related(
            'usuario_origen', 'usuario_origen__area', 'usuario_origen__oficina',
            'local_origen', 'local_origen__entidad', 'area_origen', 'oficina_origen',
            'usuario_destino', 'usuario_destino__area', 'usuario_destino__oficina',
            'local_destino', 'local_destino__entidad', 'area_destino', 'oficina_destino',
            'bien', 'bien__denominacion'
        ),
        id=traslado_id
    )

    # Traslados del mismo usuario destino en la misma fecha (mismo lote)
    traslados_mismo_lote = TrasladoBien.objects.filter(
        usuario_destino=traslado.usuario_destino,
        local_destino=traslado.local_destino,
        fecha_traslado=traslado.fecha_traslado
    ).select_related(
        'bien', 'bien__denominacion'
    ).order_by('bien__codigo_patrimonial')

    traslados_unicos = []
    vistos = set()
    for t in traslados_mismo_lote:
        if t.bien_id in vistos:
            continue
        vistos.add(t.bien_id)
        traslados_unicos.append(t)

    entidad_nombre = (
        traslado.local_destino.entidad.nombre
        if traslado.local_destino and getattr(traslado.local_destino, 'entidad', None)
        else "MUNICIPALIDAD DISTRITAL DE JOSÉ LUIS BUSTAMANTE Y RIVERO"
    )
    fecha_traslado_str = traslado.fecha_traslado.strftime('%d/%m/%Y')

    # Usuario y ubicación de ORIGEN (donde pertenecía el bien antes)
    usuario_origen = traslado.usuario_origen
    nombres_completos_origen = f"{usuario_origen.nombres} {usuario_origen.apellidos}".strip()
    dni_origen = usuario_origen.numero_documento or ''
    correo_origen = getattr(usuario_origen, 'correo', None) or getattr(usuario_origen, 'email', None) or '-'
    oficina_origen = (
        (traslado.oficina_origen.nombre if traslado.oficina_origen else None)
        or (traslado.area_origen.nombre if traslado.area_origen else None)
        or '-'
    )
    local_origen = traslado.local_origen.nombre if traslado.local_origen else '-'
    direccion_origen = traslado.local_origen.direccion if traslado.local_origen else '-'

    # Usuario y ubicación de DESTINO (a quien va el bien)
    usuario_destino = traslado.usuario_destino
    nombres_completos_destino = f"{usuario_destino.nombres} {usuario_destino.apellidos}".strip()
    dni_destino = usuario_destino.numero_documento or ''
    correo_destino = getattr(usuario_destino, 'correo', None) or getattr(usuario_destino, 'email', None) or '-'
    oficina_destino = (
        (traslado.oficina_destino.nombre if traslado.oficina_destino else None)
        or (traslado.area_destino.nombre if traslado.area_destino else None)
        or '-'
    )
    local_destino = traslado.local_destino.nombre if traslado.local_destino else '-'
    direccion_destino = traslado.local_destino.direccion if traslado.local_destino else '-'

    context = {
        'entidad_nombre': entidad_nombre,
        'documento_autoriza': traslado.documento_autoriza or '',
        'fecha': fecha_traslado_str,
        'nombres_completos_origen': nombres_completos_origen,
        'dni_origen': dni_origen,
        'correo_origen': correo_origen,
        'oficina_origen': oficina_origen,
        'local_origen': local_origen,
        'direccion_origen': direccion_origen,
        'nombres_completos_destino': nombres_completos_destino,
        'dni_destino': dni_destino,
        'correo_destino': correo_destino,
        'oficina_destino': oficina_destino,
        'local_destino': local_destino,
        'direccion_destino': direccion_destino,
        'traslados_unicos': traslados_unicos,
    }

    html = render_to_string('ficha-limpia.html', context)
    buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html.encode('utf-8'), dest=buffer, encoding='utf-8')
    if pisa_status.err:
        return HttpResponse(
            "Error al generar el PDF. Verifique que la plantilla sea HTML válido.",
            status=500
        )
    buffer.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ficha_asignacion_traslado_{timestamp}.pdf"'
    return response


# ==============================================================================
# BÚSQUEDA DE TRASLADOS POR FECHA
# ==============================================================================

@require_http_methods(["GET"])
def buscar_traslados_por_fecha(request):
    """Vista AJAX para buscar traslados por rango de fechas"""
    from django.utils.dateparse import parse_date
    from datetime import datetime as dt
    
    fecha_desde_str = request.GET.get('fecha_desde', '')
    fecha_hasta_str = request.GET.get('fecha_hasta', '')
    
    if not fecha_desde_str or not fecha_hasta_str:
        return JsonResponse({
            'error': 'Debe proporcionar ambas fechas',
            'traslados': []
        }, status=400)
    
    try:
        fecha_desde = parse_date(fecha_desde_str)
        fecha_hasta = parse_date(fecha_hasta_str)
        
        if fecha_desde > fecha_hasta:
            return JsonResponse({
                'error': 'La fecha "Desde" debe ser anterior o igual a la fecha "Hasta"',
                'traslados': []
            }, status=400)
        
        # Ajustar fecha_hasta para incluir todo el día
        fecha_hasta_fin_dia = timezone.make_aware(
            dt.combine(fecha_hasta, dt.max.time())
        )
        fecha_desde_inicio_dia = timezone.make_aware(
            dt.combine(fecha_desde, dt.min.time())
        )
        
        # Obtener todos los traslados en el rango de fechas
        traslados = TrasladoBien.objects.filter(
            fecha_traslado__gte=fecha_desde_inicio_dia,
            fecha_traslado__lte=fecha_hasta_fin_dia
        ).select_related(
            'usuario_destino',
            'local_destino',
            'area_destino',
            'oficina_destino'
        ).order_by('-fecha_traslado')
        
        # Agrupar traslados por usuario destino, local destino y fecha (mismo lote)
        # Un lote es un conjunto de traslados al mismo usuario en el mismo local en la misma fecha
        traslados_agrupados = {}
        
        for traslado in traslados:
            # Crear clave única para agrupar: usuario_destino + local_destino + fecha (solo día)
            fecha_dia = traslado.fecha_traslado.date()
            clave = f"{traslado.usuario_destino_id}_{traslado.local_destino_id}_{fecha_dia}"
            
            if clave not in traslados_agrupados:
                traslados_agrupados[clave] = {
                    'traslado_id': traslado.id,  # ID del primer traslado del lote (para generar reporte)
                    'fecha_traslado': traslado.fecha_traslado.isoformat(),
                    'usuario_destino_nombre': f"{traslado.usuario_destino.apellidos}, {traslado.usuario_destino.nombres}",
                    'local_destino_nombre': traslado.local_destino.nombre if traslado.local_destino else '-',
                    'area_destino_nombre': traslado.area_destino.nombre if traslado.area_destino else '-',
                    'oficina_destino_nombre': traslado.oficina_destino.nombre if traslado.oficina_destino else '-',
                    'cantidad_bienes': 0
                }
            
            traslados_agrupados[clave]['cantidad_bienes'] += 1
        
        # Convertir a lista y ordenar por fecha descendente
        resultado = list(traslados_agrupados.values())
        resultado.sort(key=lambda x: x['fecha_traslado'], reverse=True)
        
        return JsonResponse({
            'traslados': resultado,
            'total': len(resultado)
        })
        
    except ValueError as e:
        return JsonResponse({
            'error': f'Formato de fecha inválido: {str(e)}',
            'traslados': []
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': f'Error al buscar traslados: {str(e)}',
            'traslados': []
        }, status=500)
