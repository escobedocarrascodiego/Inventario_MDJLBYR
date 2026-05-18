from django.shortcuts import render
from django.urls import reverse
from django.db.models import Q, Sum, Count
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image, KeepTogether, KeepInFrame
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from datetime import datetime, date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import os
from organizacion.models import Local, Area, Oficina
from catalogos.models import CuentaContable, Denominacion
from bienes.models import Bien, ParametroSistema
from bajas.models import BajaBien


def reportes_index(request):
    """Vista para seleccionar el tipo de reporte a generar"""
    return render(request, 'inventario/reportes_index.html')




def reporte_depreciacion_filtros(request):
    """Vista para seleccionar filtros del reporte de depreciación."""
    locales = Local.objects.order_by('nombre')
    denominaciones = Denominacion.objects.order_by('nombre')
    cuentas_contables = CuentaContable.objects.order_by('codigo')

    context = {
        'locales': locales,
        'denominaciones': denominaciones,
        'cuentas_contables': cuentas_contables,
    }
    return render(request, 'inventario/reporte_depreciacion_filtros.html', context)




def generar_reporte_depreciacion(request):
    """Genera reporte PDF con depreciación anual, mensual y acumulada."""
    local_id = (request.GET.get('local_id') or '').strip()
    area_id = (request.GET.get('area_id') or '').strip()
    oficina_id = (request.GET.get('oficina_id') or '').strip()
    denominacion_id = (request.GET.get('denominacion_id') or '').strip()
    cuenta_contable_id = (request.GET.get('cuenta_contable_id') or '').strip()

    bienes = Bien.objects.exclude(estado='BAJA').select_related(
        'denominacion', 'cuenta_contable', 'local', 'area', 'oficina'
    )

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

    config = ParametroSistema.get_current_config()
    valor_uit = config.valor_uit if config else Decimal('5500.00')
    divisor_umbral = config.divisor_umbral_depreciacion if config else 4
    if not divisor_umbral:
        divisor_umbral = 4
    umbral_depreciacion = valor_uit / Decimal(str(divisor_umbral))

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_depreciacion_{}.pdf"'.format(
        datetime.now().strftime('%Y%m%d_%H%M%S')
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        leftMargin=1*cm,
        rightMargin=1*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#0066CC'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=7,
        leading=9
    )

    elements = []
    elements.append(Paragraph("Reporte de Depreciación", title_style))
    elements.append(Spacer(1, 6))

    data = [[
        'Código',
        'Descripción',
        'Oficina',
        'Valor Adquisición',
        'Tasa (%)',
        'Dep. Anual',
        'Dep. Mensual',
        'Dep. Acumulada',
        'Valor Neto'
    ]]

    for bien in bienes:
        tasa = bien.tasa_depreciacion
        if tasa is None and bien.cuenta_contable:
            tasa = bien.cuenta_contable.tasa_depreciacion

        if not tasa or bien.valor_adquisicion <= umbral_depreciacion:
            dep_anual = Decimal('0.00')
            dep_mensual = Decimal('0.00')
            dep_acumulada = Decimal('0.00')
            valor_neto = bien.valor_adquisicion
            tasa_display = '0.00'
        else:
            dep_anual = (bien.valor_adquisicion * (tasa / 100)).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
            dep_mensual = (dep_anual / 12).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
            meses_transcurridos = bien._meses_transcurridos_desde_pecosa()
            dep_acumulada = (dep_mensual * Decimal(str(meses_transcurridos))).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
            max_depreciacion = (bien.valor_adquisicion - Decimal('1.00')).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
            if dep_acumulada > max_depreciacion:
                dep_acumulada = max_depreciacion
            valor_neto = (bien.valor_adquisicion - dep_acumulada).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
            tasa_display = f"{tasa:.2f}"

        descripcion = bien.denominacion.nombre if bien.denominacion else (bien.descripcion or '')

        oficina_nombre = bien.oficina.nombre if bien.oficina else (bien.area.nombre if bien.area else '')

        data.append([
            bien.codigo_patrimonial or '',
            Paragraph(descripcion or '', cell_style),
            Paragraph(oficina_nombre or '', cell_style),
            f"S/ {bien.valor_adquisicion:.2f}",
            tasa_display,
            f"S/ {dep_anual:.2f}",
            f"S/ {dep_mensual:.2f}",
            f"S/ {dep_acumulada:.2f}",
            f"S/ {valor_neto:.2f}",
        ])

    table = Table(data, colWidths=[2.2*cm, 6.8*cm, 3.8*cm, 2.8*cm, 1.8*cm, 2.4*cm, 2.4*cm, 2.6*cm, 2.4*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f7f7')]),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
    ]))

    elements.append(table)
    doc.build(elements)
    return response




def generar_reporte_bienes_activos(request):
    """Genera un reporte PDF detallado de todos los bienes activos con formato estructurado"""
    from reportlab.platypus import KeepTogether
    
    # Obtener todos los bienes activos (excluyendo los dados de baja)
    bienes = Bien.objects.exclude(estado='BAJA').select_related(
        'denominacion', 'denominacion__grupo_generico', 'denominacion__clase',
        'cuenta_contable', 'usuario_asignado', 'usuario_asignado__area', 'usuario_asignado__area__local',
        'usuario_asignado__oficina', 'local', 'local__entidad', 'area', 'oficina'
    ).order_by('codigo_patrimonial')
    
    # Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_bienes_activos_{}.pdf"'.format(
        datetime.now().strftime('%Y%m%d_%H%M%S')
    )
    
    # Crear documento PDF con márgenes
    doc = SimpleDocTemplate(
        response, 
        pagesize=A4,
        leftMargin=1*cm,
        rightMargin=1*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    elements = []
    
    # Ruta del logo
    logo_path = os.path.join(settings.BASE_DIR, 'images', 'logo_transparente.png')
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Estilo para el título principal (azul, negrita, centrado)
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#0066CC'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para etiquetas de datos
    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontSize=8,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )
    
    # Estilo para valores de datos
    value_style = ParagraphStyle(
        'ValueStyle',
        parent=styles['Normal'],
        fontSize=8,
        fontName='Helvetica',
        alignment=TA_LEFT
    )
    
    # Estilo para encabezado de página
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=7,
        fontName='Helvetica',
        alignment=TA_RIGHT
    )
    
    # Estilo para entidad/dependencia
    entity_style = ParagraphStyle(
        'EntityStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica',
        alignment=TA_CENTER,
        spaceAfter=5
    )
    
    # ===== ENCABEZADO DE PÁGINA =====
    # Crear tabla para encabezado: Logo (izq) | Título (centro) | Página/Fecha (der)
    header_table_data = []
    
    # Columna izquierda: Logo
    logo_cell = []
    if os.path.exists(logo_path):
        try:
            pil_logo = PILImage.open(logo_path)
            if pil_logo.mode in ('RGBA', 'LA', 'P'):
                background = PILImage.new('RGB', pil_logo.size, (255, 255, 255))
                if pil_logo.mode == 'P':
                    pil_logo = pil_logo.convert('RGBA')
                if pil_logo.mode == 'RGBA':
                    background.paste(pil_logo, mask=pil_logo.split()[-1])
                else:
                    background.paste(pil_logo)
                pil_logo = background
            elif pil_logo.mode != 'RGB':
                pil_logo = pil_logo.convert('RGB')
            
            # Tamaño del logo: 1.5cm
            target_size_pixels = 177  # 1.5cm a 300 DPI
            pil_logo.thumbnail((target_size_pixels, target_size_pixels), PILImage.Resampling.LANCZOS)
            final_logo = PILImage.new('RGB', (target_size_pixels, target_size_pixels), (255, 255, 255))
            if pil_logo.size[0] <= target_size_pixels and pil_logo.size[1] <= target_size_pixels:
                x_offset = (target_size_pixels - pil_logo.size[0]) // 2
                y_offset = (target_size_pixels - pil_logo.size[1]) // 2
                final_logo.paste(pil_logo, (x_offset, y_offset))
            else:
                final_logo = pil_logo.resize((target_size_pixels, target_size_pixels), PILImage.Resampling.LANCZOS)
            
            logo_buffer = BytesIO()
            final_logo.save(logo_buffer, format='PNG', dpi=(300, 300))
            logo_buffer.seek(0)
            logo_size = 1.5*cm
            logo_img = Image(logo_buffer, width=logo_size, height=logo_size)
            logo_cell.append(logo_img)
            logo_cell.append(Paragraph("Software Inventario Mobiliario Institucional", 
                                     ParagraphStyle('LogoText', parent=styles['Normal'], fontSize=6, 
                                                   fontName='Helvetica', alignment=TA_CENTER)))
        except Exception:
            logo_cell.append(Paragraph("SBN", label_style))
            logo_cell.append(Paragraph("Software Inventario Mobiliario Institucional", 
                                     ParagraphStyle('LogoText', parent=styles['Normal'], fontSize=6, 
                                                   fontName='Helvetica', alignment=TA_CENTER)))
    else:
        logo_cell.append(Paragraph("SBN", label_style))
        logo_cell.append(Paragraph("Software Inventario Mobiliario Institucional", 
                                 ParagraphStyle('LogoText', parent=styles['Normal'], fontSize=6, 
                                               fontName='Helvetica', alignment=TA_CENTER)))
    
    # Columna central: Título
    title_cell = [Paragraph("REPORTE DETALLADO DE BIENES ACTIVOS", title_style)]
    
    # Columna derecha: Página y Fecha
    page_cell = [
        Paragraph(f"Pag. : 1 de 1", header_style),
        Paragraph(f"Fecha : {datetime.now().strftime('%d/%m/%Y')}", header_style)
    ]
    
    header_table = Table(
        [[logo_cell, title_cell, page_cell]],
        colWidths=[3*cm, 12*cm, 3*cm]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.2*cm))
    
    # Entidad y Dependencia
    entidad_nombre = "MUNICIPALIDAD DISTRITAL DE JOSÉ LUIS BUSTAMANTE Y RIVERO"
    dependencia_nombre = "MUNICIPALIDAD DISTRITAL DE JOSE LUIS BUS"  # Truncado como en la imagen
    
    elements.append(Paragraph(f"ENTIDAD : {entidad_nombre}", entity_style))
    elements.append(Paragraph(f"DEPENDENCIA : {dependencia_nombre}", entity_style))
    elements.append(Spacer(1, 0.3*cm))
    
    # ===== CUERPO: BIENES DETALLADOS =====
    total_bienes = bienes.count()
    
    if bienes.exists():
        for idx, bien in enumerate(bienes, 1):
            # Obtener datos
            codigo_patrimonial = bien.codigo_patrimonial or 'N/A'
            codigo_interno = bien.codigo_interno or ''
            denominacion = bien.denominacion.nombre if bien.denominacion else bien.descripcion or 'N/A'
            local = bien.local.nombre if bien.local else 'N/A'
            area = bien.area.nombre if bien.area else 'N/A'
            oficina = bien.oficina.nombre if bien.oficina else 'N/A'
            usuario = f"{bien.usuario_asignado.apellidos}, {bien.usuario_asignado.nombres}" if bien.usuario_asignado else 'N/A'
            cuenta = bien.cuenta_contable.codigo if bien.cuenta_contable else 'N/A'
            forma_adq = bien.get_forma_adquisicion_display()
            det_tecnico = bien.otros_detalles or ''
            valorizacion = f"{bien.valor_neto:,.2f}"
            fecha_adq = bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else 'N/A'
            estado = bien.get_estado_display()
            doc_adq = bien.resolucion_alta or ''
            
            # Crear bloque para cada bien con borde
            # Estructura según la imagen:
            # - Primera fila: número (en caja), COD. PATRIMONIAL, COD. INT., DENOMINACION
            # - Filas siguientes: dos columnas (izquierda y derecha)
            
            # Construir la tabla principal del bien
            bien_table_data = []
            
            # Primera fila: número, códigos y denominación
            # Crear número en una tabla pequeña con borde
            num_table = Table(
                [[Paragraph(f"{idx}", ParagraphStyle('NumStyle', parent=styles['Normal'], fontSize=9, 
                                                    fontName='Helvetica-Bold', alignment=TA_CENTER))]],
                colWidths=[0.6*cm]
            )
            num_table.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            
            bien_table_data.append([
                num_table,
                Paragraph(f"COD. PATRIMONIAL: {codigo_patrimonial}", value_style),
                Paragraph(f"COD. INT.: {codigo_interno}", value_style),
                Paragraph(f"DENOMINACION: {denominacion}", value_style)
            ])
            
            # Filas siguientes: dos columnas
            # Datos izquierda
            datos_izq = [
                ("LOCAL :", local),
                ("USUARIO :", usuario),
                ("CUENTA :", cuenta),
                ("FORMA ADQ :", forma_adq),
                ("DET TECNICO:", det_tecnico),
            ]
            
            # Datos derecha
            datos_der = [
                ("AREA :", area),
                ("OFICINA :", oficina),
                ("VALORIZACION (S/.):", valorizacion),
                ("FEC. ADQUISICION:", fecha_adq),
                ("ESTADO:", estado),
                ("DOC. ADQ.:", doc_adq),
            ]
            
            # Crear filas combinadas (máximo de filas entre izquierda y derecha)
            max_rows = max(len(datos_izq), len(datos_der))
            
            for i in range(max_rows):
                # Columna izquierda
                if i < len(datos_izq):
                    label_izq = datos_izq[i][0]
                    value_izq = datos_izq[i][1]
                    texto_izq = f"{label_izq} {value_izq}"
                else:
                    texto_izq = ""
                
                # Columna derecha
                if i < len(datos_der):
                    label_der = datos_der[i][0]
                    value_der = datos_der[i][1]
                    texto_der = f"{label_der} {value_der}"
                else:
                    texto_der = ""
                
                # Agregar fila a la tabla principal
                bien_table_data.append([
                    "",  # Columna del número vacía
                    Paragraph(texto_izq, value_style) if texto_izq else "",
                    "",  # Columna código interno vacía
                    Paragraph(texto_der, value_style) if texto_der else ""
                ])
            
            # Crear tabla principal
            bien_table = Table(bien_table_data, colWidths=[0.8*cm, 8.5*cm, 3*cm, 5.7*cm])
            bien_table.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),  # Número centrado
                ('ALIGN', (1, 0), (-1, 0), 'LEFT'),  # Primera fila a la izquierda
                ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Columna izquierda
                ('ALIGN', (3, 1), (3, -1), 'LEFT'),  # Columna derecha
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.grey),  # Línea horizontal después de la primera fila
            ]))
            
            elements.append(bien_table)
            elements.append(Spacer(1, 0.3*cm))
    else:
        elements.append(Paragraph("No se encontraron bienes activos.", styles['Normal']))
    
    # ===== PIE DE PÁGINA =====
    elements.append(Spacer(1, 0.5*cm))
    footer_table = Table(
        [[Paragraph(f"TOTAL DE BIENES : {total_bienes}", 
                    ParagraphStyle('FooterStyle', parent=styles['Normal'], fontSize=9, 
                                 fontName='Helvetica-Bold', alignment=TA_RIGHT))]],
        colWidths=[18*cm]
    )
    footer_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(footer_table)
    
    # Construir PDF
    doc.build(elements)
    return response




def generar_reporte_bienes_por_local(request):
    """Genera un reporte PDF de bienes agrupados por local"""
    # Obtener todos los locales con sus bienes activos
    from django.db.models import F
    locales = Local.objects.prefetch_related(
        'bien_set'
    ).annotate(
        total_bienes=Count('bien', filter=~Q(bien__estado='BAJA')),
        valor_total=Sum('bien__valor_neto', filter=~Q(bien__estado='BAJA'))
    ).filter(total_bienes__gt=0).order_by('nombre')
    
    # Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_bienes_por_local_{}.pdf"'.format(
        datetime.now().strftime('%Y%m%d_%H%M%S')
    )
    
    # Crear documento PDF
    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a1d20'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    # Título
    elements.append(Paragraph("REPORTE DE BIENES POR LOCAL", title_style))
    elements.append(Paragraph("Municipalidad Distrital de José Luis Bustamante y Rivero", styles['Normal']))
    elements.append(Paragraph(f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Iterar por cada local
    for local in locales:
        bienes = Bien.objects.filter(local=local).exclude(estado='BAJA').select_related(
            'denominacion', 'cuenta_contable', 'usuario_asignado', 'area', 'oficina'
        ).order_by('codigo_patrimonial')
        
        # Encabezado del local
        local_heading = ParagraphStyle(
            'LocalHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#0d6efd'),
            spaceAfter=8,
            spaceBefore=12
        )
        elements.append(Paragraph(f"LOCAL: {local.nombre}", local_heading))
        elements.append(Paragraph(f"Dirección: {local.direccion}", styles['Normal']))
        elements.append(Paragraph(f"Total de Bienes: {local.total_bienes} | Valor Total: S/ {local.valor_total or 0:,.2f}", styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))
        
        if bienes.exists():
            # Tabla de bienes del local
            data = [['Código', 'Denominación', 'Área', 'Valor Neto', 'Estado']]
            
            for bien in bienes:
                denominacion = bien.denominacion.nombre if bien.denominacion else bien.descripcion or 'N/A'
                area = bien.area.nombre if bien.area else 'N/A'
                valor = f"S/ {bien.valor_neto:,.2f}"
                estado = bien.get_estado_display()
                
                if len(denominacion) > 45:
                    denominacion = denominacion[:42] + '...'
                if len(area) > 30:
                    area = area[:27] + '...'
                
                data.append([
                    bien.codigo_patrimonial or 'N/A',
                    denominacion,
                    area,
                    valor,
                    estado
                ])
            
            table = Table(data, colWidths=[1.2*inch, 3*inch, 1.8*inch, 1.2*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("No hay bienes activos en este local.", styles['Normal']))
        
        elements.append(Spacer(1, 0.3*inch))
    
    # Construir PDF
    doc.build(elements)
    return response




def generar_reporte_bienes_baja(request):
    """Genera un reporte PDF detallado de todos los bienes dados de baja"""
    # Obtener todos los bienes dados de baja con sus datos de baja
    bienes = Bien.objects.filter(estado='BAJA').select_related(
        'denominacion', 'denominacion__grupo_generico', 'denominacion__clase',
        'cuenta_contable', 'usuario_asignado', 'usuario_asignado__area', 
        'usuario_asignado__area__local', 'usuario_asignado__oficina',
        'local', 'local__entidad', 'area', 'oficina', 'baja'
    ).prefetch_related('baja').order_by('codigo_patrimonial')
    
    # Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="reporte_bienes_baja_{}.pdf"'.format(
        datetime.now().strftime('%Y%m%d_%H%M%S')
    )
    
    # Crear documento PDF con márgenes
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
    
    # Estilo para el título principal
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#000000'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para etiquetas
    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontSize=8,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )
    
    # Estilo para valores
    value_style = ParagraphStyle(
        'ValueStyle',
        parent=styles['Normal'],
        fontSize=8,
        fontName='Helvetica',
        alignment=TA_LEFT
    )
    
    # Estilo para encabezados de tabla
    table_header_style = ParagraphStyle(
        'TableHeaderStyle',
        parent=styles['Normal'],
        fontSize=7,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        leading=8
    )
    
    # Estilo para datos de tabla
    table_data_style = ParagraphStyle(
        'TableDataStyle',
        parent=styles['Normal'],
        fontSize=7,
        fontName='Helvetica',
        alignment=TA_LEFT,
        leading=8
    )
    
    # ===== LOGO Y ENCABEZADO =====
    logo_path = os.path.join(settings.BASE_DIR, 'images', 'logo_transparente.png')
    if os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=2*cm, height=2*cm)
            logo_table = Table([[logo]], colWidths=[2*cm])
            logo_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(logo_table)
        except:
            pass
    
    elements.append(Spacer(1, 0.2*cm))
    
    # ===== TÍTULO =====
    elements.append(Paragraph("REPORTE DETALLADO DE BIENES DADOS DE BAJA", title_style))
    elements.append(Spacer(1, 0.3*cm))
    
    # ===== PÁGINA Y FECHA =====
    fecha_actual = datetime.now().strftime('%d/%m/%Y')
    header_info = Table(
        [[
            Paragraph(f"Pag.: 1 de 1", value_style),
            Paragraph(f"Fecha: {fecha_actual}", value_style)
        ]],
        colWidths=[9*cm, 9*cm]
    )
    header_info.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(header_info)
    elements.append(Spacer(1, 0.3*cm))
    
    # ===== ENTIDAD Y DEPENDENCIA =====
    # Obtener entidad del primer bien o usar default
    entidad_nombre = "MUNICIPALIDAD DISTRITAL DE JOSÉ LUIS BUSTAMANTE Y RIVERO"
    if bienes.exists():
        primer_bien = bienes.first()
        if primer_bien.local and primer_bien.local.entidad:
            entidad_nombre = primer_bien.local.entidad.nombre.upper()
    
    dependencia_nombre = entidad_nombre[:40]  # Truncar si es muy largo
    
    entidad_table = Table([
        [Paragraph("ENTIDAD:", label_style), Paragraph(entidad_nombre, value_style)],
        [Paragraph("DEPENDENCIA:", label_style), Paragraph(dependencia_nombre, value_style)]
    ], colWidths=[3*cm, 15*cm])
    entidad_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(entidad_table)
    elements.append(Spacer(1, 0.4*cm))
    
    # ===== BIENES DADOS DE BAJA =====
    if bienes.exists():
        total_bienes = bienes.count()
        
        for idx, bien in enumerate(bienes, 1):
            # Obtener datos de baja
            baja = getattr(bien, 'baja', None)
            
            # Datos básicos del bien
            denominacion = bien.denominacion.nombre if bien.denominacion else bien.descripcion or 'N/A'
            codigo_patrimonial = bien.codigo_patrimonial or '-'
            codigo_interno = bien.codigo_interno or '-'
            
            # Tabla de identificación del bien
            ident_table_data = [[
                Paragraph(str(idx), table_data_style),
                Paragraph(f"COD. PATRIMONIAL: {codigo_patrimonial}", value_style),
                Paragraph(f"COD. INT: {codigo_interno}", value_style),
                Paragraph(f"DENOMINACION: {denominacion}", value_style)
            ]]
            ident_table = Table(ident_table_data, colWidths=[0.8*cm, 5*cm, 3*cm, 8.2*cm])
            ident_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(ident_table)
            elements.append(Spacer(1, 0.2*cm))
            
            # ===== DATOS DE LA BAJA =====
            if baja:
                causal_display = dict(BajaBien.CAUSAL_BAJA_CHOICES).get(baja.causal_baja, baja.causal_baja)
                resolucion = baja.resolucion_baja or '-'
                fecha_resol = baja.fecha_resolucion.strftime('%d/%m/%Y') if baja.fecha_resolucion else '-'
                documento_sbn = baja.documento_sbn or '-'
            else:
                causal_display = '-'
                resolucion = '-'
                fecha_resol = '-'
                documento_sbn = '-'
            
            # Tabla de datos de baja
            baja_header = Table([
                [Paragraph("DATOS DE LA BAJA", table_header_style)]
            ], colWidths=[17*cm])
            baja_header.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e0e0e0')),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(baja_header)
            
            baja_table_data = [
                [
                    Paragraph("NUMERO DE RESOLUCION", table_header_style),
                    Paragraph("FECHA DE RESOLUCION", table_header_style),
                    Paragraph("CAUSAL DE BAJA", table_header_style),
                    Paragraph("DOCUMENTO SBN", table_header_style)
                ],
                [
                    Paragraph(resolucion, table_data_style),
                    Paragraph(fecha_resol, table_data_style),
                    Paragraph(causal_display, table_data_style),
                    Paragraph(documento_sbn, table_data_style)
                ]
            ]
            baja_table = Table(baja_table_data, colWidths=[4.5*cm, 4.5*cm, 4.5*cm, 3.5*cm])
            baja_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e0e0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 7),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(baja_table)
            elements.append(Spacer(1, 0.2*cm))
            
            # ===== DETALLES ADICIONALES =====
            local = bien.local.nombre if bien.local else 'N/A'
            usuario = f"{bien.usuario_asignado.apellidos}, {bien.usuario_asignado.nombres}" if bien.usuario_asignado else 'N/A'
            cuenta = bien.cuenta_contable.codigo if bien.cuenta_contable else 'N/A'
            forma_adq = bien.get_forma_adquisicion_display() if bien.forma_adquisicion else 'N/A'
            detalle_tecnico = f"{bien.marca or ''} {bien.modelo or ''} {bien.color or ''}".strip() or '-'
            
            area = bien.area.nombre if bien.area else (bien.usuario_asignado.area.nombre if bien.usuario_asignado and bien.usuario_asignado.area else 'N/A')
            oficina = bien.oficina.nombre if bien.oficina else (bien.usuario_asignado.oficina.nombre if bien.usuario_asignado and bien.usuario_asignado.oficina else '-')
            valorizacion = f"{bien.valor_neto:,.2f}"
            estado = bien.get_estado_display() if bien.estado else 'N/A'
            fecha_adq = bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else 'N/A'
            doc_adq = bien.resolucion_alta or '-'
            
            detalles_table = Table([
                [
                    Paragraph(f"LOCAL : {local}", value_style),
                    Paragraph(f"AREA : {area}", value_style)
                ],
                [
                    Paragraph(f"USUARIO : {usuario}", value_style),
                    Paragraph(f"OFICINA : {oficina}", value_style)
                ],
                [
                    Paragraph(f"CUENTA : {cuenta}", value_style),
                    Paragraph(f"VALORIZACION (S/.): {valorizacion}", value_style)
                ],
                [
                    Paragraph(f"FORMA ADQ : {forma_adq}", value_style),
                    Paragraph(f"ESTADO: {estado}", value_style)
                ],
                [
                    Paragraph(f"D. TECNICO : {detalle_tecnico}", value_style),
                    Paragraph(f"FEC. ADQUISICION: {fecha_adq}", value_style)
                ],
                [
                    Paragraph("", value_style),
                    Paragraph(f"DOC. ADQ.: {doc_adq}", value_style)
                ]
            ], colWidths=[9*cm, 9*cm])
            detalles_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            elements.append(detalles_table)
            elements.append(Spacer(1, 0.4*cm))
            
            # Salto de página si no es el último bien
            if idx < total_bienes:
                elements.append(PageBreak())
    
    else:
        elements.append(Paragraph("No se encontraron bienes dados de baja.", styles['Normal']))
    
    # ===== FOOTER CON TOTAL =====
    elements.append(Spacer(1, 0.3*cm))
    footer_table = Table([
        [Paragraph("TOTAL DE BIENES :", label_style), Paragraph(str(total_bienes), value_style)]
    ], colWidths=[15*cm, 3*cm])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (1, 0), (1, 0), 0.5, colors.grey),
    ]))
    elements.append(footer_table)
    
    # Construir PDF
    doc.build(elements)
    return response




def generar_reporte_por_cuentas_contables(request):
    """Genera un reporte PDF agrupado por cuentas contables con totales"""
    from django.db.models import Sum, Count, Q
    from django.utils.dateparse import parse_date
    
    # Obtener parámetros de fecha (opcionales)
    fecha_desde_str = request.GET.get('fecha_desde', '')
    fecha_hasta_str = request.GET.get('fecha_hasta', '')
    
    # Construir queryset base
    bienes_query = Bien.objects.exclude(estado='BAJA').filter(
        cuenta_contable__isnull=False
    )
    
    # Filtrar por rango de fechas de adquisición si se proporcionan
    if fecha_desde_str:
        try:
            fecha_desde = parse_date(fecha_desde_str)
            if fecha_desde:
                bienes_query = bienes_query.filter(fecha_adquisicion__gte=fecha_desde)
        except (ValueError, TypeError):
            pass  # Ignorar fechas inválidas
    
    if fecha_hasta_str:
        try:
            fecha_hasta = parse_date(fecha_hasta_str)
            if fecha_hasta:
                bienes_query = bienes_query.filter(fecha_adquisicion__lte=fecha_hasta)
        except (ValueError, TypeError):
            pass  # Ignorar fechas inválidas
    
    # Obtener bienes agrupados por cuenta contable
    bienes_por_cuenta = bienes_query.select_related('cuenta_contable').values(
        'cuenta_contable__id',
        'cuenta_contable__codigo',
        'cuenta_contable__descripcion'
    ).annotate(
        cantidad=Count('id'),
        valor_adquisicion_total=Sum('valor_adquisicion'),
        valor_neto_total=Sum('valor_neto')
    ).order_by('cuenta_contable__codigo')
    
    # Crear nombre de archivo con fechas si están disponibles
    fecha_str = ''
    if fecha_desde_str and fecha_hasta_str:
        try:
            fecha_desde = parse_date(fecha_desde_str)
            fecha_hasta = parse_date(fecha_hasta_str)
            if fecha_desde and fecha_hasta:
                fecha_str = f"_{fecha_desde.strftime('%Y%m%d')}_{fecha_hasta.strftime('%Y%m%d')}"
        except (ValueError, TypeError):
            pass
    
    # Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_por_cuentas_contables{}_{}.pdf"'.format(
        fecha_str,
        datetime.now().strftime('%Y%m%d_%H%M%S')
    )
    
    # Crear documento PDF con márgenes
    doc = SimpleDocTemplate(
        response, 
        pagesize=A4,
        leftMargin=1*cm,
        rightMargin=1*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    elements = []
    
    # Ruta del logo
    logo_path = os.path.join(settings.BASE_DIR, 'images', 'logo_transparente.png')
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Estilo para el título principal
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#0066CC'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para encabezado de página
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=7,
        fontName='Helvetica',
        alignment=TA_RIGHT
    )
    
    # Estilo para entidad/dependencia
    entity_style = ParagraphStyle(
        'EntityStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica',
        alignment=TA_CENTER,
        spaceAfter=5
    )
    
    # Estilo para encabezados de tabla
    header_table_style = ParagraphStyle(
        'HeaderTableStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER
    )
    
    # Estilo para datos normales
    data_style = ParagraphStyle(
        'DataStyle',
        parent=styles['Normal'],
        fontSize=8,
        fontName='Helvetica',
        alignment=TA_LEFT
    )
    
    # Estilo para datos numéricos
    number_style = ParagraphStyle(
        'NumberStyle',
        parent=styles['Normal'],
        fontSize=8,
        fontName='Helvetica',
        alignment=TA_RIGHT
    )
    
    # Estilo para totales (cuentas principales)
    total_style = ParagraphStyle(
        'TotalStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )
    
    # Estilo para totales numéricos
    total_number_style = ParagraphStyle(
        'TotalNumberStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica-Bold',
        alignment=TA_RIGHT
    )
    
    # ===== ENCABEZADO DE PÁGINA =====
    header_table_data = []
    
    # Columna izquierda: Logo
    logo_cell = []
    if os.path.exists(logo_path):
        try:
            pil_logo = PILImage.open(logo_path)
            if pil_logo.mode in ('RGBA', 'LA', 'P'):
                background = PILImage.new('RGB', pil_logo.size, (255, 255, 255))
                if pil_logo.mode == 'P':
                    pil_logo = pil_logo.convert('RGBA')
                if pil_logo.mode == 'RGBA':
                    background.paste(pil_logo, mask=pil_logo.split()[-1])
                else:
                    background.paste(pil_logo)
                pil_logo = background
            elif pil_logo.mode != 'RGB':
                pil_logo = pil_logo.convert('RGB')
            
            target_size_pixels = 177
            pil_logo.thumbnail((target_size_pixels, target_size_pixels), PILImage.Resampling.LANCZOS)
            final_logo = PILImage.new('RGB', (target_size_pixels, target_size_pixels), (255, 255, 255))
            if pil_logo.size[0] <= target_size_pixels and pil_logo.size[1] <= target_size_pixels:
                x_offset = (target_size_pixels - pil_logo.size[0]) // 2
                y_offset = (target_size_pixels - pil_logo.size[1]) // 2
                final_logo.paste(pil_logo, (x_offset, y_offset))
            else:
                final_logo = pil_logo.resize((target_size_pixels, target_size_pixels), PILImage.Resampling.LANCZOS)
            
            logo_buffer = BytesIO()
            final_logo.save(logo_buffer, format='PNG', dpi=(300, 300))
            logo_buffer.seek(0)
            logo_size = 1.5*cm
            logo_img = Image(logo_buffer, width=logo_size, height=logo_size)
            logo_cell.append(logo_img)
            logo_cell.append(Paragraph("Software Inventario Mobiliario Institucional", 
                                     ParagraphStyle('LogoText', parent=styles['Normal'], fontSize=6, 
                                                   fontName='Helvetica', alignment=TA_CENTER)))
        except Exception:
            logo_cell.append(Paragraph("SBN", header_table_style))
    else:
        logo_cell.append(Paragraph("SBN", header_table_style))
    
    # Construir título con rango de fechas si está disponible
    titulo_reporte = "REPORTE POR CUENTAS CONTABLES"
    if fecha_desde_str and fecha_hasta_str:
        try:
            fecha_desde = parse_date(fecha_desde_str)
            fecha_hasta = parse_date(fecha_hasta_str)
            if fecha_desde and fecha_hasta:
                titulo_reporte += f"\n(Adquisiciones del {fecha_desde.strftime('%d/%m/%Y')} al {fecha_hasta.strftime('%d/%m/%Y')})"
        except (ValueError, TypeError):
            pass
    
    # Columna central: Título
    title_cell = [Paragraph(titulo_reporte, title_style)]
    
    # Columna derecha: Página y Fecha
    page_cell = [
        Paragraph(f"Pag. : 1 de 1", header_style),
        Paragraph(f"Fecha : {datetime.now().strftime('%d/%m/%Y')}", header_style)
    ]
    
    header_table = Table(
        [[logo_cell, title_cell, page_cell]],
        colWidths=[3*cm, 12*cm, 3*cm]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.2*cm))
    
    # Entidad y Dependencia
    entidad_nombre = "MUNICIPALIDAD DISTRITAL DE JOSÉ LUIS BUSTAMANTE Y RIVERO"
    dependencia_nombre = "MUNICIPALIDAD DISTRITAL DE JOSE LUIS BUS"
    
    elements.append(Paragraph(f"ENTIDAD : {entidad_nombre}", entity_style))
    elements.append(Paragraph(f"DEPENDENCIA : {dependencia_nombre}", entity_style))
    elements.append(Spacer(1, 0.3*cm))
    
    # ===== TABLA DE DATOS =====
    # Detectar estructura jerárquica de códigos
    # Agrupar por código base (parte antes del punto) para totales
    codigos_base = {}
    for item in bienes_por_cuenta:
        codigo = item['cuenta_contable__codigo']
        # Extraer código base (parte antes del primer punto o todo si no hay punto)
        if '.' in codigo:
            codigo_base = codigo.split('.')[0]
        else:
            codigo_base = codigo
        
        if codigo_base not in codigos_base:
            # Intentar obtener la descripción de la cuenta base si existe
            descripcion_base = ''
            try:
                cuenta_base_obj = CuentaContable.objects.filter(codigo=codigo_base).first()
                if cuenta_base_obj:
                    descripcion_base = cuenta_base_obj.descripcion
            except:
                pass
            
            # Si no se encontró, usar la descripción de la primera subcuenta
            if not descripcion_base:
                descripcion_base = item['cuenta_contable__descripcion']
            
            codigos_base[codigo_base] = {
                'codigo': codigo_base,
                'descripcion': descripcion_base,
                'cantidad': 0,
                'valor_adquisicion': 0,
                'valor_neto': 0,
                'subcuentas': []
            }
        
        codigos_base[codigo_base]['cantidad'] += item['cantidad']
        codigos_base[codigo_base]['valor_adquisicion'] += float(item['valor_adquisicion_total'] or 0)
        codigos_base[codigo_base]['valor_neto'] += float(item['valor_neto_total'] or 0)
        codigos_base[codigo_base]['subcuentas'].append(item)
    
    # Construir tabla de datos
    table_data = []
    
    # Encabezados
    table_data.append([
        Paragraph("CUENTA", header_table_style),
        Paragraph("DESCRIPCIÓN", header_table_style),
        Paragraph("CANTIDAD", header_table_style),
        Paragraph("VALOR ADQUISICIÓN", header_table_style),
        Paragraph("VALOR NETO", header_table_style)
    ])
    
    # Agregar datos agrupados
    for codigo_base in sorted(codigos_base.keys()):
        grupo = codigos_base[codigo_base]
        descripcion_grupo = grupo['descripcion']
        
        # Si hay múltiples subcuentas, mostrar primero el total del grupo
        if len(grupo['subcuentas']) > 1:
            # Fila de total del grupo (en negrita)
            table_data.append([
                Paragraph(codigo_base, total_style),
                Paragraph(descripcion_grupo.upper(), total_style),
                Paragraph(f"{grupo['cantidad']:,}", total_number_style),
                Paragraph(f"{grupo['valor_adquisicion']:,.2f}", total_number_style),
                Paragraph(f"{grupo['valor_neto']:,.2f}", total_number_style)
            ])
            
            # Agregar subcuentas (indentadas visualmente)
            for subcuenta in sorted(grupo['subcuentas'], key=lambda x: x['cuenta_contable__codigo']):
                table_data.append([
                    Paragraph(f"  {subcuenta['cuenta_contable__codigo']}", data_style),
                    Paragraph(subcuenta['cuenta_contable__descripcion'], data_style),
                    Paragraph(f"{subcuenta['cantidad']:,}", number_style),
                    Paragraph(f"{float(subcuenta['valor_adquisicion_total'] or 0):,.2f}", number_style),
                    Paragraph(f"{float(subcuenta['valor_neto_total'] or 0):,.2f}", number_style)
                ])
        else:
            # Solo una cuenta, mostrar directamente
            item = grupo['subcuentas'][0]
            table_data.append([
                Paragraph(item['cuenta_contable__codigo'], data_style),
                Paragraph(item['cuenta_contable__descripcion'], data_style),
                Paragraph(f"{item['cantidad']:,}", number_style),
                Paragraph(f"{float(item['valor_adquisicion_total'] or 0):,.2f}", number_style),
                Paragraph(f"{float(item['valor_neto_total'] or 0):,.2f}", number_style)
            ])
    
    # Calcular totales generales
    total_cantidad = sum(item['cantidad'] for item in bienes_por_cuenta)
    total_valor_adq = sum(float(item['valor_adquisicion_total'] or 0) for item in bienes_por_cuenta)
    total_valor_neto = sum(float(item['valor_neto_total'] or 0) for item in bienes_por_cuenta)
    
    # Fila de total general
    table_data.append([
        Paragraph("TOTAL GENERAL", total_style),
        Paragraph("", total_style),
        Paragraph(f"{total_cantidad:,}", total_number_style),
        Paragraph(f"{total_valor_adq:,.2f}", total_number_style),
        Paragraph(f"{total_valor_neto:,.2f}", total_number_style)
    ])
    
    # Crear tabla
    table = Table(table_data, colWidths=[3*cm, 7*cm, 2.5*cm, 3*cm, 2.5*cm])
    table.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#366092')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        # Filas de datos
        ('FONTNAME', (1, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (1, 1), (-1, -2), 8),
        ('BOTTOMPADDING', (1, 1), (-1, -2), 4),
        ('TOPPADDING', (1, 1), (-1, -2), 4),
        # Fila de total general
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e0e0e0')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 6),
        ('TOPPADDING', (0, -1), (-1, -1), 6),
        # Bordes
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        # Alternar colores de filas
        ('ROWBACKGROUNDS', (1, 1), (-1, -2), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    
    elements.append(table)
    
    # Construir PDF
    doc.build(elements)
    return response


# ==============================================================================
# GENERACIÓN DE REPORTES EN EXCEL
# ==============================================================================

