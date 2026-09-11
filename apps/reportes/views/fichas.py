from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
from io import BytesIO
import qrcode
import os
from PIL import Image as PILImage
from organizacion.models import Local, Area, Oficina, Entidad
from personal.models import Personal
from bienes.models import Bien


def fichas_index(request):
    """Vista para la página de selección de fichas"""
    return render(request, 'inventario/fichas_index.html')




@require_http_methods(["GET"])
def buscar_bienes_para_ficha(request):
    """Vista AJAX para buscar bienes para generar fichas"""
    query = request.GET.get('q', '').strip()
    tipo_ficha = request.GET.get('tipo', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'bienes': []})
    
    if tipo_ficha not in ['computo', 'vehiculo']:
        return JsonResponse({'error': 'Tipo de ficha inválido', 'bienes': []}, status=400)
    
    # Buscar bienes activos
    bienes = Bien.objects.exclude(estado='BAJA').select_related('denominacion')
    
    # Filtrar según el tipo de ficha (búsqueda general, sin restricciones estrictas)
    if tipo_ficha == 'computo':
        # Para computo, buscar bienes que puedan ser equipos de cómputo
        # Priorizar los que tienen serie pero no excluir los demás
        bienes = bienes.filter(
            Q(codigo_patrimonial__icontains=query) |
            Q(codigo_interno__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(denominacion__nombre__icontains=query) |
            Q(serie__icontains=query) |
            Q(marca__icontains=query) |
            Q(modelo__icontains=query)
        ).order_by('-serie')  # Priorizar los que tienen serie
    elif tipo_ficha == 'vehiculo':
        # Para vehículos, buscar bienes que puedan ser vehículos
        # Priorizar los que tienen placa pero no excluir los demás
        bienes = bienes.filter(
            Q(codigo_patrimonial__icontains=query) |
            Q(codigo_interno__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(denominacion__nombre__icontains=query) |
            Q(placa__icontains=query) |
            Q(numero_motor__icontains=query) |
            Q(numero_chasis__icontains=query)
        ).order_by('-placa')  # Priorizar los que tienen placa
    
    # Limitar a 20 resultados
    bienes = bienes[:20]
    
    results = []
    for bien in bienes:
        results.append({
            'id': bien.id,
            'codigo_patrimonial': bien.codigo_patrimonial or 'N/A',
            'codigo_interno': bien.codigo_interno or 'N/A',
            'descripcion': bien.descripcion or 'N/A',
            'denominacion': bien.denominacion.nombre if bien.denominacion else 'N/A',
            'marca': bien.marca or '',
            'modelo': bien.modelo or '',
            'serie': bien.serie or '',
            'placa': bien.placa or ''
        })
    
    return JsonResponse({'bienes': results})


@require_http_methods(["GET"])


def generar_ficha_computo(request, bien_id):
    """Genera una ficha detallada PDF de un equipo de cómputo"""
    bien = get_object_or_404(
        Bien.objects.select_related(
            'denominacion', 'denominacion__grupo_generico', 'denominacion__clase',
            'cuenta_contable', 'usuario_asignado', 'usuario_asignado__area', 
            'usuario_asignado__area__local', 'usuario_asignado__oficina',
            'local', 'local__entidad', 'area', 'oficina', 'ubicacion_fisica'
        ),
        pk=bien_id
    )
    
    # Validar que el bien tenga serie (característico de equipos de cómputo)
    if not bien.serie:
        return HttpResponse(
            "Este bien no tiene número de serie. Solo se pueden generar fichas de equipos de cómputo con serie.",
            status=400
        )
    
    # Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ficha_computo_{bien.codigo_patrimonial}_{datetime.now().strftime("%Y%m%d")}.pdf"'
    
    # Crear documento PDF
    doc = SimpleDocTemplate(
        response, 
        pagesize=A4,
        leftMargin=1.5*cm,
        rightMargin=1.5*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Estilo para título
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#0066CC'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para subtítulos
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#333333'),
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para etiquetas
    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )
    
    # Estilo para valores
    value_style = ParagraphStyle(
        'ValueStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica',
        alignment=TA_LEFT
    )
    
    # Título
    elements.append(Paragraph("FICHA TÉCNICA DE EQUIPO DE CÓMPUTO", title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # Datos del Bien
    denominacion_texto = bien.descripcion or (bien.denominacion.nombre if bien.denominacion else 'N/A')
    data_bien = [
        [Paragraph('Código Patrimonial:', label_style), Paragraph(bien.codigo_patrimonial or 'N/A', value_style)],
        [Paragraph('Código Interno:', label_style), Paragraph(bien.codigo_interno or 'N/A', value_style)],
        [Paragraph('Denominación:', label_style), Paragraph(denominacion_texto, value_style)],
        [Paragraph('Grupo Genérico:', label_style), Paragraph(bien.grupo_generico or 'N/A', value_style)],
        [Paragraph('Clase:', label_style), Paragraph(bien.clase or 'N/A', value_style)],
    ]
    
    table_bien = Table(data_bien, colWidths=[5*cm, 10*cm])
    table_bien.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
    ]))
    elements.append(table_bien)
    elements.append(Spacer(1, 0.5*cm))
    
    # Especificaciones Técnicas
    elements.append(Paragraph("ESPECIFICACIONES TÉCNICAS", subtitle_style))
    
    data_especificaciones = [
        [Paragraph('Marca:', label_style), Paragraph(bien.marca or 'N/A', value_style)],
        [Paragraph('Modelo:', label_style), Paragraph(bien.modelo or 'N/A', value_style)],
        [Paragraph('Número de Serie:', label_style), Paragraph(bien.serie or 'N/A', value_style)],
        [Paragraph('Color:', label_style), Paragraph(bien.color or 'N/A', value_style)],
        [Paragraph('Dimensión:', label_style), Paragraph(bien.dimension or 'N/A', value_style)],
    ]
    
    if bien.otros_detalles:
        data_especificaciones.append([Paragraph('Otros Detalles:', label_style), Paragraph(bien.otros_detalles, value_style)])
    
    table_especificaciones = Table(data_especificaciones, colWidths=[5*cm, 10*cm])
    table_especificaciones.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
    ]))
    elements.append(table_especificaciones)
    elements.append(Spacer(1, 0.5*cm))
    
    # Datos de Adquisición
    elements.append(Paragraph("DATOS DE ADQUISICIÓN", subtitle_style))
    
    fecha_adq_str = bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else 'N/A'
    fecha_pecosa_str = bien.fecha_pecosa.strftime('%d/%m/%Y') if bien.fecha_pecosa else 'N/A'
    
    data_adquisicion = [
        [Paragraph('Forma de Adquisición:', label_style), Paragraph(bien.get_forma_adquisicion_display(), value_style)],
        [Paragraph('Fecha de Adquisición:', label_style), Paragraph(fecha_adq_str, value_style)],
        [Paragraph('Resolución de Alta:', label_style), Paragraph(bien.resolucion_alta or 'N/A', value_style)],
        [Paragraph('Fecha PECOSA:', label_style), Paragraph(fecha_pecosa_str, value_style)],
        [Paragraph('Valor de Adquisición:', label_style), Paragraph(f"S/ {bien.valor_adquisicion:,.2f}", value_style)],
        [Paragraph('Valor Neto:', label_style), Paragraph(f"S/ {bien.valor_neto:,.2f}", value_style)],
    ]
    
    table_adquisicion = Table(data_adquisicion, colWidths=[5*cm, 10*cm])
    table_adquisicion.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
    ]))
    elements.append(table_adquisicion)
    elements.append(Spacer(1, 0.5*cm))
    
    # Ubicación y Asignación
    elements.append(Paragraph("UBICACIÓN Y ASIGNACIÓN", subtitle_style))
    
    usuario_nombre = f"{bien.usuario_asignado.apellidos}, {bien.usuario_asignado.nombres}" if bien.usuario_asignado else 'N/A'
    ubicacion_fisica_texto = str(bien.ubicacion_fisica) if bien.ubicacion_fisica else 'N/A'
    
    data_ubicacion = [
        [Paragraph('Usuario Asignado:', label_style), Paragraph(usuario_nombre, value_style)],
        [Paragraph('Entidad:', label_style), Paragraph(bien.local.entidad.nombre if bien.local and bien.local.entidad else 'N/A', value_style)],
        [Paragraph('Local:', label_style), Paragraph(bien.local.nombre if bien.local else 'N/A', value_style)],
        [Paragraph('Área:', label_style), Paragraph(bien.area.nombre if bien.area else 'N/A', value_style)],
        [Paragraph('Oficina:', label_style), Paragraph(bien.oficina.nombre if bien.oficina else 'N/A', value_style)],
        [Paragraph('Ubicación Física:', label_style), Paragraph(ubicacion_fisica_texto, value_style)],
    ]
    
    table_ubicacion = Table(data_ubicacion, colWidths=[5*cm, 10*cm])
    table_ubicacion.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
    ]))
    elements.append(table_ubicacion)
    elements.append(Spacer(1, 0.5*cm))
    
    # Estado
    elements.append(Paragraph("ESTADO", subtitle_style))
    
    data_estado = [
        [Paragraph('Estado:', label_style), Paragraph(bien.get_estado_display(), value_style)],
        [Paragraph('Situación:', label_style), Paragraph(bien.get_situacion_display(), value_style)],
    ]
    
    table_estado = Table(data_estado, colWidths=[5*cm, 10*cm])
    table_estado.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
    ]))
    elements.append(table_estado)
    
    # Construir PDF
    doc.build(elements)
    return response




def generar_ficha_vehiculo(request, bien_id):
    """Genera una ficha detallada PDF de un vehículo con formato similar a las imágenes proporcionadas"""
    bien = get_object_or_404(
        Bien.objects.select_related(
            'denominacion', 'denominacion__grupo_generico', 'denominacion__clase',
            'cuenta_contable', 'usuario_asignado', 'usuario_asignado__area', 
            'usuario_asignado__area__local', 'usuario_asignado__oficina',
            'local', 'local__entidad', 'area', 'oficina', 'ubicacion_fisica'
        ),
        pk=bien_id
    )
    
    # Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ficha_vehiculo_{bien.codigo_patrimonial}_{datetime.now().strftime("%Y%m%d")}.pdf"'
    
    # Crear documento PDF
    doc = SimpleDocTemplate(
        response, 
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Estilo para título principal
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#000000'),
        spaceAfter=15,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para etiquetas (negrita)
    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )
    
    # Estilo para valores
    value_style = ParagraphStyle(
        'ValueStyle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica',
        alignment=TA_LEFT
    )
    
    # Encabezado con información institucional
    entidad_nombre = bien.local.entidad.nombre if bien.local and bien.local.entidad else "MUNICIPALIDAD DISTRITAL DE JOSÉ LUIS BUSTAMANTE Y RIVERO"
    elements.append(Paragraph("Institucional", ParagraphStyle('Institucional', parent=styles['Normal'], fontSize=9, fontName='Helvetica', alignment=TA_LEFT)))
    elements.append(Paragraph(f"DEPENDENCIA: {entidad_nombre}", ParagraphStyle('Dependencia', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', alignment=TA_LEFT)))
    elements.append(Spacer(1, 0.4*cm))
    
    # Título principal
    elements.append(Paragraph("FICHA DE VEHÍCULO", title_style))
    elements.append(Spacer(1, 0.3*cm))
    
    # DENOMINACION (en caja destacada)
    denominacion_text = bien.descripcion or (bien.denominacion.nombre if bien.denominacion else 'N/A')
    denominacion_data = [[Paragraph("DENOMINACION", label_style), Paragraph(denominacion_text.upper(), value_style)]]
    denominacion_table = Table(denominacion_data, colWidths=[4*cm, 11*cm])
    denominacion_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#e0e0e0')),
        ('BACKGROUND', (1, 0), (1, 0), colors.white),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(denominacion_table)
    elements.append(Spacer(1, 0.4*cm))
    
    # UBICACION
    ubicacion_data = [
        [Paragraph('LOCAL:', label_style), Paragraph(bien.local.nombre if bien.local else 'N/A', value_style)],
        [Paragraph('AREA:', label_style), Paragraph(bien.area.nombre if bien.area else 'N/A', value_style)],
        [Paragraph('OFICINA:', label_style), Paragraph(bien.oficina.nombre if bien.oficina else 'N/A', value_style)],
    ]
    ubicacion_table = Table(ubicacion_data, colWidths=[4*cm, 11*cm])
    ubicacion_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
    ]))
    elements.append(ubicacion_table)
    elements.append(Spacer(1, 0.3*cm))
    
    # USUARIO
    usuario_nombre = ''
    if bien.usuario_asignado:
        apellidos = bien.usuario_asignado.apellidos or ''
        nombres = bien.usuario_asignado.nombres or ''
        usuario_nombre = f"{apellidos}, {nombres}".strip(', ')
    else:
        usuario_nombre = 'N/A'
    
    usuario_data = [[Paragraph('APELLIDOS Y NOMBRES:', label_style), Paragraph(usuario_nombre, value_style)]]
    usuario_table = Table(usuario_data, colWidths=[4*cm, 11*cm])
    usuario_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
    ]))
    elements.append(usuario_table)
    elements.append(Spacer(1, 0.3*cm))
    
    # DATOS SOBRE EL BIEN
    elements.append(Paragraph("<b>DATOS SOBRE EL BIEN</b>", label_style))
    elements.append(Spacer(1, 0.2*cm))
    
    cuenta_codigo = bien.cuenta_contable.codigo if bien.cuenta_contable else 'N/A'
    doc_adq = bien.resolucion_alta or 'N/A'
    estado_display = bien.get_estado_display() or 'N/A'
    
    fecha_adq_str = bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else 'N/A'
    
    datos_bien = [
        [Paragraph('CODIGO INTERNO:', label_style), Paragraph(bien.codigo_interno or '', value_style)],
        [Paragraph('FORMA ADQUISICION:', label_style), Paragraph(bien.get_forma_adquisicion_display(), value_style)],
        [Paragraph('CUENTA:', label_style), Paragraph(cuenta_codigo, value_style)],
        [Paragraph('DOC. ADQ.:', label_style), Paragraph(doc_adq, value_style)],
        [Paragraph('V. LIBRO (S/.):', label_style), Paragraph(f"{bien.valor_adquisicion:,.2f}", value_style)],
        [Paragraph('FEC. ADQUIS.:', label_style), Paragraph(fecha_adq_str, value_style)],
        [Paragraph('ESTADO:', label_style), Paragraph(estado_display, value_style)],
        [Paragraph('ASEGURADO:', label_style), Paragraph('NO', value_style)],  # Campo no disponible en el modelo, se deja como NO
    ]
    
    datos_bien_table = Table(datos_bien, colWidths=[4*cm, 11*cm])
    datos_bien_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
    ]))
    elements.append(datos_bien_table)
    elements.append(Spacer(1, 0.3*cm))
    
    # DETALLE TECNICO DEL BIEN
    elements.append(Paragraph("<b>DETALLE TECNICO DEL BIEN</b>", label_style))
    elements.append(Spacer(1, 0.2*cm))
    
    # Extraer placa anterior y tipo de vehículo de otros_detalles si existe
    import re
    placa_anterior = ''
    tipo_vehiculo = ''
    
    if bien.otros_detalles:
        # Buscar placa anterior
        match_placa = re.search(r'PLACA\s*ANTERIOR[:\s]*([A-Z0-9-]+)', bien.otros_detalles.upper())
        if match_placa:
            placa_anterior = match_placa.group(1)
        
        # Buscar tipo de vehículo
        if 'DOBLE CABINA' in bien.otros_detalles.upper() or 'DOBLE' in bien.otros_detalles.upper():
            tipo_vehiculo = 'DOBLE CABINA'
        elif 'SIMPLE CABINA' in bien.otros_detalles.upper() or 'SIMPLE' in bien.otros_detalles.upper():
            tipo_vehiculo = 'SIMPLE CABINA'
    
    detalle_tecnico = [
        [Paragraph('MARCA:', label_style), Paragraph(bien.marca or 'N/A', value_style)],
        [Paragraph('MODELO:', label_style), Paragraph(bien.modelo or 'N/A', value_style)],
        [Paragraph('COLOR:', label_style), Paragraph(bien.color or 'N/A', value_style)],
        [Paragraph('CHASIS:', label_style), Paragraph(bien.numero_chasis or 'N/A', value_style)],
        [Paragraph('OTROS / PLACA ANTERIOR:', label_style), Paragraph(placa_anterior or '', value_style)],
        [Paragraph('PLACA:', label_style), Paragraph(bien.placa or 'N/A', value_style)],
        [Paragraph('TIPO:', label_style), Paragraph(tipo_vehiculo or 'N/A', value_style)],
        [Paragraph('MOTOR:', label_style), Paragraph(bien.numero_motor or 'N/A', value_style)],
        [Paragraph('AÑO:', label_style), Paragraph(str(bien.anio_fabricacion) if bien.anio_fabricacion else 'N/A', value_style)],
    ]
    
    detalle_tecnico_table = Table(detalle_tecnico, colWidths=[4*cm, 11*cm])
    detalle_tecnico_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
    ]))
    elements.append(detalle_tecnico_table)

    # Construir PDF
    doc.build(elements)
    return response


# ==============================================================================
# ANEXO N° 03 - FICHA DE ASIGNACIÓN EN USO DE BIENES MUEBLES PATRIMONIALES
# ==============================================================================

def _meses_es():
    return [
        '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
    ]


def _etiqueta_ubicacion_fisica(ubicacion):
    """Nombre CORTO del ambiente, tal como debe salir en el Anexo N° 03.

    El Órgano y la Oficina van en sus propias filas de la ficha, así que aquí
    solo interesa el ambiente: "Almacen", "Planillas", "Piso 3"... (el __str__
    del modelo repite área + oficina + local y no sirve para esa fila).
    """
    if ubicacion is None:
        return ''
    detalle = (ubicacion.detalle or '').strip()
    if detalle:
        return detalle
    if ubicacion.piso is not None:
        return f"Piso {ubicacion.piso}"
    return ubicacion.local.nombre if ubicacion.local else ''


def _distintos(valores):
    """Valores no vacíos, sin repetir y conservando el orden de aparición."""
    unicos = []
    for valor in valores:
        valor = (valor or '').strip()
        if valor and valor not in unicos:
            unicos.append(valor)
    return unicos


def ficha_anexo03_index(request):
    """Página de selección de usuario y bienes para generar el Anexo N° 03."""
    entidad = Entidad.objects.first()
    entidad_nombre = entidad.nombre if entidad else "Municipalidad Distrital de José Luis Bustamante y Rivero"
    return render(request, 'inventario/ficha_anexo03_seleccion.html', {
        'entidad_nombre': entidad_nombre,
    })


@require_http_methods(["GET"])
def buscar_personal_anexo03(request):
    """AJAX: busca personal por nombre, apellido o DNI para el Select2 del Anexo N° 03."""
    query = (request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    personal = Personal.objects.select_related('area', 'oficina').filter(
        Q(nombres__icontains=query) |
        Q(apellidos__icontains=query) |
        Q(numero_documento__icontains=query)
    ).order_by('apellidos', 'nombres')[:25]

    results = []
    for p in personal:
        area_nombre = p.area.nombre if p.area else ''
        results.append({
            'id': p.id,
            'text': f"{p.apellidos}, {p.nombres} — DNI: {p.numero_documento}" + (f" ({area_nombre})" if area_nombre else "")
        })
    return JsonResponse({'results': results})


@require_http_methods(["GET"])
def datos_personal_anexo03(request):
    """AJAX: retorna los datos del usuario para rellenar el formulario."""
    personal_id = request.GET.get('personal_id')
    if not personal_id or not str(personal_id).isdigit():
        return JsonResponse({'error': 'ID inválido'}, status=400)

    personal = get_object_or_404(
        Personal.objects.select_related('area', 'area__local', 'oficina'),
        pk=personal_id
    )

    local_nombre = ''
    direccion = ''
    if personal.area and personal.area.local:
        local_nombre = personal.area.local.nombre
        direccion = personal.area.local.direccion or ''

    return JsonResponse({
        'id': personal.id,
        'nombre_completo': f"{personal.apellidos}, {personal.nombres}",
        'dni': personal.numero_documento,
        'area': personal.area.nombre if personal.area else '',
        'oficina': personal.oficina.nombre if personal.oficina else '',
        'local': local_nombre,
        'direccion': direccion,
        'cargo': personal.cargo or '',
    })


@require_http_methods(["GET"])
def bienes_personal_anexo03(request):
    """AJAX: lista los bienes activos asignados al usuario seleccionado."""
    personal_id = request.GET.get('personal_id')
    if not personal_id or not str(personal_id).isdigit():
        return JsonResponse({'error': 'ID inválido', 'bienes': []}, status=400)

    bienes = Bien.objects.select_related(
        'denominacion', 'local', 'area', 'oficina',
        'ubicacion_fisica', 'ubicacion_fisica__local',
    ).filter(
        usuario_asignado_id=int(personal_id)
    ).exclude(estado='BAJA').order_by('codigo_patrimonial')

    data = []
    for b in bienes:
        denominacion = b.descripcion or (b.denominacion.nombre if b.denominacion else '')
        data.append({
            'id': b.id,
            'codigo_patrimonial': b.codigo_patrimonial or '',
            'denominacion': denominacion,
            'marca': b.marca or '',
            'modelo': b.modelo or '',
            'serie': b.serie or '',
            'color': b.color or '',
            'resolucion_alta': b.resolucion_alta or '',
            'estado': b.estado,
            'estado_label': b.get_estado_display(),
            # Dónde está el bien: permite filtrar la ficha por ambiente
            # (ej. sacar solo los bienes que están en "Almacen").
            'local': b.local.nombre if b.local else '',
            'area': b.area.nombre if b.area else '',
            'oficina': b.oficina.nombre if b.oficina else '',
            'ubicacion_fisica': _etiqueta_ubicacion_fisica(b.ubicacion_fisica),
        })

    return JsonResponse({'bienes': data})


@require_http_methods(["POST"])
def generar_ficha_anexo03(request):
    """Genera el PDF del Anexo N° 03 con los bienes seleccionados."""
    personal_id = request.POST.get('personal_id')
    bien_ids = request.POST.getlist('bien_ids')
    entidad_input = (request.POST.get('entidad') or '').strip()
    correo = (request.POST.get('correo') or '').strip()
    fecha_str = (request.POST.get('fecha') or '').strip()

    if not personal_id or not bien_ids:
        return HttpResponse("Debe seleccionar un usuario y al menos un bien.", status=400)

    personal = get_object_or_404(
        Personal.objects.select_related('area', 'area__local', 'oficina'),
        pk=personal_id
    )

    bienes = list(
        Bien.objects.select_related(
            'denominacion', 'local', 'area', 'oficina',
            'ubicacion_fisica', 'ubicacion_fisica__local',
        ).filter(
            pk__in=bien_ids,
            usuario_asignado_id=personal.id
        ).exclude(estado='BAJA').order_by('codigo_patrimonial')
    )

    if not bienes:
        return HttpResponse("No se encontraron bienes válidos para este usuario.", status=400)

    # Fecha de la ficha
    try:
        fecha_ficha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else datetime.now().date()
    except ValueError:
        fecha_ficha = datetime.now().date()

    # Datos institucionales / ubicación
    local_obj = personal.area.local if (personal.area and personal.area.local) else None
    local_nombre = local_obj.nombre if local_obj else ''

    # Órgano, oficina y ambiente se leen de los BIENES seleccionados, no de la
    # ficha del trabajador: es donde están realmente los bienes que se entregan
    # (un almacenero puede figurar sin oficina y tener bienes en el "Almacen").
    # Si los bienes no lo traen, se cae al dato del trabajador.
    area_nombre = ' / '.join(_distintos(b.area.nombre if b.area else '' for b in bienes)) or (
        personal.area.nombre if personal.area else ''
    )
    oficina_nombre = ' / '.join(_distintos(b.oficina.nombre if b.oficina else '' for b in bienes)) or (
        personal.oficina.nombre if personal.oficina else ''
    )
    ubicacion_nombre = ' / '.join(
        _distintos(_etiqueta_ubicacion_fisica(b.ubicacion_fisica) for b in bienes)
    )
    # La dirección se toma del Local o sede (no es la dirección del trabajador).
    direccion = local_obj.direccion if (local_obj and local_obj.direccion) else ''
    entidad_nombre = entidad_input or (
        personal.area.local.entidad.nombre
        if personal.area and personal.area.local and personal.area.local.entidad
        else "Municipalidad Distrital de José Luis Bustamante y Rivero"
    )

    # --- Generar PDF ---
    response = HttpResponse(content_type='application/pdf')
    filename = f"anexo03_{personal.numero_documento}_{fecha_ficha.strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'AnexoTitle', parent=styles['Normal'],
        fontSize=11, fontName='Helvetica-Bold', alignment=TA_CENTER, leading=14
    )
    label_style = ParagraphStyle(
        'AnexoLabel', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica-Bold', alignment=TA_LEFT, leading=11
    )
    value_style = ParagraphStyle(
        'AnexoValue', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica', alignment=TA_LEFT, leading=11
    )
    small_style = ParagraphStyle(
        'AnexoSmall', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica', alignment=TA_LEFT, leading=10
    )
    cell_style = ParagraphStyle(
        'AnexoCell', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica', alignment=TA_LEFT, leading=10
    )
    cell_center = ParagraphStyle(
        'AnexoCellCenter', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica', alignment=TA_CENTER, leading=10
    )

    # Encabezado: ANEXO N° 03 + título
    elements.append(Paragraph("ANEXO N° 03", title_style))
    elements.append(Paragraph(
        "FICHA DE ASIGNACIÓN EN USO DE BIENES MUEBLES PATRIMONIALES",
        title_style
    ))
    elements.append(Spacer(1, 0.4 * cm))

    # Entidad + Fecha (dos columnas)
    fecha_dia = fecha_ficha.strftime('%d')
    fecha_mes = fecha_ficha.strftime('%m')
    fecha_anio = fecha_ficha.strftime('%Y')
    fecha_texto = f"{fecha_dia} / {fecha_mes} / {fecha_anio}"

    encabezado_data = [
        [
            Paragraph("<b>ENTIDAD U ORGANIZACIÓN DE LA ENTIDAD:</b>", label_style),
            Paragraph("<b>FECHA:</b>", label_style),
        ],
        [
            Paragraph(entidad_nombre, value_style),
            Paragraph(fecha_texto, value_style),
        ],
    ]
    encabezado_table = Table(encabezado_data, colWidths=[19 * cm, 7.7 * cm])
    encabezado_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 1), (0, 1), 0.5, colors.black),
        ('BOX', (1, 1), (1, 1), 0.5, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(encabezado_table)
    elements.append(Spacer(1, 0.3 * cm))

    # DATOS DEL USUARIO
    usuario_data = [
        [Paragraph("<b>DATOS DEL USUARIO</b>", label_style), '', '', ''],
        [
            Paragraph("Nombres y apellidos", cell_style),
            Paragraph(f"{personal.nombres} {personal.apellidos}", cell_style),
            Paragraph("N° DNI", cell_style),
            Paragraph(personal.numero_documento or '', cell_style),
        ],
        [
            Paragraph("Correo electrónico", cell_style),
            Paragraph(correo, cell_style),
            '', '',
        ],
        [
            Paragraph("Órgano o Unidad Orgánica", cell_style),
            Paragraph(area_nombre, cell_style),
            '', '',
        ],
        [
            Paragraph("Oficina", cell_style),
            Paragraph(oficina_nombre, cell_style),
            '', '',
        ],
        [
            Paragraph("Ubicación Física", cell_style),
            Paragraph(ubicacion_nombre, cell_style),
            '', '',
        ],
        [
            Paragraph("Local o sede", cell_style),
            Paragraph(local_nombre, cell_style),
            '', '',
        ],
        [
            Paragraph("Dirección<super>(1)</super>", cell_style),
            Paragraph(direccion, cell_style),
            '', '',
        ],
    ]
    usuario_table = Table(usuario_data, colWidths=[4.5 * cm, 11 * cm, 3.2 * cm, 8 * cm])
    usuario_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D9D9D9')),
        ('SPAN', (0, 0), (-1, 0)),
        ('SPAN', (1, 2), (3, 2)),
        ('SPAN', (1, 3), (3, 3)),
        ('SPAN', (1, 4), (3, 4)),
        ('SPAN', (1, 5), (3, 5)),
        ('SPAN', (1, 6), (3, 6)),
        ('SPAN', (1, 7), (3, 7)),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(usuario_table)
    elements.append(Spacer(1, 0.4 * cm))

    # TABLA DE BIENES
    header_style = ParagraphStyle(
        'AnexoHeader', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER, leading=10
    )

    # Headers: N° Orden | DESCRIPCIÓN (Código, Denominación, Marca, Modelo, Color, Serie, Otros, Estado) | Observaciones
    bienes_data = [
        [
            Paragraph("N° DE<br/>ORDEN", header_style),
            Paragraph("DESCRIPCIÓN<super>(2)</super>", header_style),
            '', '', '', '', '', '', '',
            Paragraph("OBSERVACIONES", header_style),
        ],
        [
            '',
            Paragraph("CÓDIGO<br/>PATRIMONIAL", header_style),
            Paragraph("DENOMINACIÓN", header_style),
            Paragraph("MARCA", header_style),
            Paragraph("MODELO", header_style),
            Paragraph("COLOR", header_style),
            Paragraph("SERIE", header_style),
            Paragraph("OTROS", header_style),
            Paragraph("ESTADO DE<br/>CONSERVACIÓN<super>(3)</super>", header_style),
            '',
        ],
    ]

    for idx, b in enumerate(bienes, start=1):
        denominacion = b.descripcion or (b.denominacion.nombre if b.denominacion else '')
        otros = ''
        if b.placa:
            otros = f"Placa: {b.placa}"
        elif b.dimension:
            otros = b.dimension
        bienes_data.append([
            Paragraph(str(idx), cell_center),
            Paragraph(b.codigo_patrimonial or '', cell_center),
            Paragraph(denominacion, cell_style),
            Paragraph(b.marca or '', cell_style),
            Paragraph(b.modelo or '', cell_style),
            Paragraph(b.color or '', cell_style),
            Paragraph(b.serie or '', cell_style),
            Paragraph(otros, cell_style),
            Paragraph(b.get_estado_display(), cell_center),
            Paragraph('', cell_style),  # Observaciones (en blanco para llenado manual)
        ])

    # Anchos de columna en A4 horizontal (suma ≈ 26.7 cm útil)
    col_widths = [1.3 * cm, 2.5 * cm, 5.5 * cm, 2.5 * cm, 2.5 * cm, 1.7 * cm, 2.7 * cm, 2.3 * cm, 2.3 * cm, 3.4 * cm]
    bienes_table = Table(bienes_data, colWidths=col_widths, repeatRows=2)
    bienes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 1), colors.HexColor('#F2F2F2')),
        ('SPAN', (0, 0), (0, 1)),       # N° DE ORDEN ocupa 2 filas
        ('SPAN', (1, 0), (8, 0)),       # DESCRIPCIÓN abarca 8 columnas
        ('SPAN', (9, 0), (9, 1)),       # OBSERVACIONES ocupa 2 filas
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(bienes_table)
    elements.append(Spacer(1, 0.3 * cm))

    # Notas al pie
    notas = [
        "(1) Se consigna para el caso de entrega o devolución de bienes muebles patrimoniales para teletrabajo",
        "(2) En caso de vehículos, se utiliza adicionalmente el Formato de Ficha Técnica de Vehículo, contemplado en el Anexo N° 08",
        "(3) El estado es consignado en base a la siguiente escala: nuevo, bueno, regular o malo. En caso de semovientes, utilizar escala de acuerdo a su naturaleza.",
    ]
    for nota in notas:
        elements.append(Paragraph(nota, small_style))
    elements.append(Spacer(1, 0.3 * cm))

    # CONSIDERACIONES
    consideraciones_titulo = ParagraphStyle(
        'ConsidTitle', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica-Bold', alignment=TA_LEFT, leading=11,
        underlineWidth=0.5
    )
    consideraciones = [
        "El usuario es responsable de la permanencia y conservación de cada uno de los bienes descritos, recomendándose tomar las precauciones del caso para evitar sustracciones, deterioros, etc.",
        "Cualquier necesidad de traslado del bien mueble patrimonial dentro o fuera del local de la Entidad u Organización de la Entidad, es previamente comunicado al encargado de la OCP.",
    ]
    bullet_style = ParagraphStyle(
        'AnexoBullet', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica', alignment=TA_LEFT, leading=10,
        leftIndent=14, bulletIndent=4
    )

    # Firmas
    firmas_data = [
        ['___________________________________________', '', '___________________________________________'],
        [Paragraph('<b>Usuario</b>', cell_center), '', Paragraph('<b>Personal de la OCP</b>', cell_center)],
    ]
    firmas_table = Table(firmas_data, colWidths=[10 * cm, 6.7 * cm, 10 * cm])
    firmas_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    # Bloque final: CONSIDERACIONES + espacio para firmar + firmas, todo unido
    # con KeepTogether. Así las firmas NUNCA quedan solas en una hoja (si saltan
    # de página, se llevan las consideraciones consigo) y el Spacer deja siempre
    # un hueco encima de las líneas para que la persona pueda firmar.
    bloque_final = [
        Paragraph("<u><b>CONSIDERACIONES:</b></u>", consideraciones_titulo),
        Spacer(1, 0.15 * cm),
    ]
    for item in consideraciones:
        bloque_final.append(Paragraph(f"➢ {item}", bullet_style))
    bloque_final.append(Spacer(1, 1.5 * cm))  # espacio en blanco para firmar
    bloque_final.append(firmas_table)

    elements.append(KeepTogether(bloque_final))

    doc.build(elements)
    return response
