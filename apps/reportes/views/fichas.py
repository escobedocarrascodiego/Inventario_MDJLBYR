from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
from io import BytesIO
import qrcode
import os
from PIL import Image as PILImage
from organizacion.models import Local, Area, Oficina
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


