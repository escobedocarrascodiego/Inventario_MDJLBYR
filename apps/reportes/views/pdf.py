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
from xml.sax.saxutils import escape
import os
from io import BytesIO
from PIL import Image as PILImage
from organizacion.models import Local, Area, Oficina
from catalogos.models import CuentaContable, Denominacion
from bienes.models import Bien, ParametroSistema
from bajas.models import BajaBien
from .carga import cargar_bienes_con_relaciones
from .comunes import (
    CanvasNumerado, bienes_para_reporte, cabecera_reporte, nombre_archivo,
)


def reportes_index(request):
    """Vista para seleccionar el tipo de reporte a generar.

    Además de las tarjetas fijas, entrega los criterios de agrupación y los
    catálogos que alimentan el modal de filtros del reporte agrupado
    (ver apps/reportes/views/agrupado.py).
    """
    from .agrupado import CRITERIOS

    context = {
        'criterios_agrupacion': [
            (clave, config['label']) for clave, config in CRITERIOS.items()
        ],
        'locales': Local.objects.order_by('nombre'),
        'cuentas_contables': CuentaContable.objects.order_by('codigo'),
        'estado_choices': Bien.ESTADO_BIEN,
        'situacion_choices': Bien.SITUACION_CHOICES,
    }
    return render(request, 'inventario/reportes_index.html', context)




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

    bienes = Bien.objects.exclude(estado='BAJA')

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

    # Sin JOINs ni ORDER BY en SQL (ver carga.py): en este servidor esas consultas
    # esperan hasta 25s por memoria de ejecución (RESOURCE_SEMAPHORE). Las
    # relaciones se cosen en Python y el orden se aplica aquí.
    bienes = cargar_bienes_con_relaciones(bienes)
    bienes.sort(key=lambda b: b.codigo_patrimonial or '')

    # Fuente ÚNICA de verdad: el cálculo vive en el modelo (Bien.calcular_depreciacion).
    # Corte = hoy para el snapshot del reporte. (CAMBIO 2)
    fecha_corte = date.today()

    # Parámetros UIT cargados UNA sola vez para evitar una consulta por cada bien.
    parametros_uit = list(ParametroSistema.objects.all())

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
        dep = bien.calcular_depreciacion(fecha_corte, parametros=parametros_uit)  # fuente única (CAMBIO 2)
        if not dep['depreciable']:
            dep_anual = Decimal('0.00')
            dep_mensual = Decimal('0.00')
            dep_acumulada = Decimal('0.00')
            valor_neto = dep['valor_neto']
            tasa_display = '0.00'
        else:
            dep_mensual = dep['cuota_mensual']
            dep_anual = dep_mensual * 12
            dep_acumulada = dep['depreciacion_acumulada']
            valor_neto = dep['valor_neto']
            tasa_display = f"{dep['tasa']:.2f}"

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




_ACTIVOS_NAVY = colors.HexColor('#1B365D')
_ACTIVOS_NAVY_SOFT = colors.HexColor('#EEF3F8')
_ACTIVOS_GRID = colors.HexColor('#8A99A8')
_ACTIVOS_ANCHO = 19 * cm


def _activos_txt(valor, vacio='—'):
    if valor is None:
        return vacio
    texto = str(valor).strip()
    return texto if texto else vacio


def _activos_campo(etiqueta, valor, style):
    return Paragraph(f"<b>{escape(etiqueta)}:</b> {escape(_activos_txt(valor))}", style)


def _activos_moneda(valor):
    if valor is None:
        return '—'
    return f"S/ {valor:,.2f}"


def _tarjeta_bien_activo(idx, bien, dep, value_style, header_style, money_style):
    """Ficha compacta de un bien: una sola tabla, sin anidar (rinde con miles de filas)."""
    denominacion = bien.descripcion or (bien.denominacion.nombre if bien.denominacion else '')
    codigo = _activos_txt(bien.codigo_patrimonial)
    usuario = ''
    if bien.usuario_asignado:
        usuario = f"{bien.usuario_asignado.apellidos}, {bien.usuario_asignado.nombres}".strip(', ')

    cuenta = ''
    if bien.cuenta_contable:
        cuenta = bien.cuenta_contable.codigo or str(bien.cuenta_contable)

    fecha_adq = bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else ''
    if dep['depreciable'] and dep['tasa'] is not None:
        tasa = f"{dep['tasa']:.2f} %"
    else:
        tasa = 'No dep.' if dep.get('motivo_no_depreciable') else '—'

    header = Paragraph(
        f"<b>{idx}.  {escape(_activos_txt(denominacion))}</b>"
        f"&nbsp;&nbsp;&nbsp;Cód. patrimonial: {escape(codigo)}",
        header_style,
    )
    filas = [
        [header, '', '', ''],
        [
            _activos_campo('Cód. interno', bien.codigo_interno, value_style),
            _activos_campo('Marca', bien.marca, value_style),
            _activos_campo('Modelo', bien.modelo, value_style),
            _activos_campo('Serie', bien.serie, value_style),
        ],
        [
            _activos_campo('Local', bien.local.nombre if bien.local else '', value_style),
            _activos_campo('Área', bien.area.nombre if bien.area else '', value_style),
            _activos_campo('Oficina', bien.oficina.nombre if bien.oficina else '', value_style),
            _activos_campo('Usuario', usuario, value_style),
        ],
        [
            _activos_campo('Cuenta', cuenta, value_style),
            _activos_campo('Forma adq.', bien.get_forma_adquisicion_display(), value_style),
            _activos_campo('F. adquisición', fecha_adq, value_style),
            _activos_campo('Doc. adq.', bien.resolucion_alta, value_style),
        ],
        [
            _activos_campo('Estado', bien.get_estado_display(), value_style),
            _activos_campo('Situación', bien.get_situacion_display(), value_style),
            _activos_campo('Color', bien.color, value_style),
            _activos_campo('Dimensión', bien.dimension, value_style),
        ],
    ]

    if bien.placa or bien.numero_motor or bien.numero_chasis or bien.anio_fabricacion:
        filas.append([
            _activos_campo('Placa', bien.placa, value_style),
            _activos_campo('Motor', bien.numero_motor, value_style),
            _activos_campo('Chasis', bien.numero_chasis, value_style),
            _activos_campo('Año', bien.anio_fabricacion, value_style),
        ])

    fila_valores = len(filas)
    filas.append([
        _activos_campo('Valor adquisición', _activos_moneda(bien.valor_adquisicion), money_style),
        _activos_campo('Depreciación acum.', _activos_moneda(dep['depreciacion_acumulada']), money_style),
        _activos_campo('Valor neto', _activos_moneda(dep['valor_neto']), money_style),
        _activos_campo('Tasa', tasa, money_style),
    ])

    fila_otros = None
    if bien.otros_detalles:
        extra = Paragraph(
            f"<b>Otros detalles:</b> {escape(_activos_txt(bien.otros_detalles))}",
            value_style,
        )
        fila_otros = len(filas)
        filas.append([KeepInFrame(_ACTIVOS_ANCHO, 1.4 * cm, [extra], mode='shrink'), '', '', ''])

    anchos = [_ACTIVOS_ANCHO / 4.0] * 4
    tabla = Table(filas, colWidths=anchos)
    cmds = [
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), _ACTIVOS_NAVY),
        ('BACKGROUND', (0, fila_valores), (-1, fila_valores), _ACTIVOS_NAVY_SOFT),
        ('BOX', (0, 0), (-1, -1), 0.7, _ACTIVOS_NAVY),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, _ACTIVOS_GRID),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, 0), 5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING', (0, 1), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
    ]
    if fila_otros is not None:
        cmds.append(('SPAN', (0, fila_otros), (-1, fila_otros)))
        cmds.append(('VALIGN', (0, fila_otros), (-1, fila_otros), 'TOP'))
    tabla.setStyle(TableStyle(cmds))
    return KeepTogether([tabla, Spacer(1, 0.18 * cm)])


def generar_reporte_bienes_activos(request):
    """Reporte PDF detallado de bienes activos: una ficha compacta por bien.

    Acepta por querystring los MISMOS filtros de la búsqueda avanzada del
    listado de bienes (ver apps/bienes/filtros.py), de modo que sirve tanto
    para el inventario completo como para imprimir exactamente el resultado de
    una búsqueda. Sin filtros imprime todos los bienes activos.
    """
    bienes, filtros_texto, hay_filtros = bienes_para_reporte(request)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(
        nombre_archivo('reporte_bienes_activos', 'pdf', hay_filtros)
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        leftMargin=1 * cm,
        rightMargin=1 * cm,
        topMargin=1.3 * cm,
        bottomMargin=1.4 * cm,
    )
    elements = []
    styles = getSampleStyleSheet()

    value_style = ParagraphStyle(
        'ActivosValue', parent=styles['Normal'],
        fontSize=7.5, leading=9.5, fontName='Helvetica', alignment=TA_LEFT,
    )
    header_style = ParagraphStyle(
        'ActivosHeader', parent=styles['Normal'],
        fontSize=8.5, leading=11, fontName='Helvetica-Bold',
        alignment=TA_LEFT, textColor=colors.white,
    )
    money_style = ParagraphStyle(
        'ActivosMoney', parent=styles['Normal'],
        fontSize=7.5, leading=9.5, fontName='Helvetica-Bold', alignment=TA_LEFT,
    )
    total_style = ParagraphStyle(
        'ActivosTotal', parent=styles['Normal'],
        fontSize=8, leading=10, fontName='Helvetica-Bold',
        alignment=TA_CENTER, textColor=colors.white,
    )
    total_value = ParagraphStyle(
        'ActivosTotalVal', parent=styles['Normal'],
        fontSize=8, leading=10, fontName='Helvetica-Bold', alignment=TA_CENTER,
    )

    elements.extend(cabecera_reporte(
        "REPORTE DETALLADO DE BIENES ACTIVOS",
        filtros_texto,
        ancho_total=_ACTIVOS_ANCHO,
        dependencia="Órgano de Control Patrimonial",
    ))

    fecha_corte = date.today()
    parametros_uit = list(ParametroSistema.objects.all())
    total_bienes = len(bienes)
    suma_adq = Decimal('0.00')
    suma_dep = Decimal('0.00')
    suma_neto = Decimal('0.00')

    if bienes:
        for idx, bien in enumerate(bienes, 1):
            dep = bien.calcular_depreciacion(fecha_corte, parametros=parametros_uit)
            suma_adq += bien.valor_adquisicion or Decimal('0.00')
            suma_dep += dep['depreciacion_acumulada'] or Decimal('0.00')
            suma_neto += dep['valor_neto'] or Decimal('0.00')
            elements.append(_tarjeta_bien_activo(
                idx, bien, dep, value_style, header_style, money_style
            ))
    else:
        elements.append(Paragraph("No se encontraron bienes activos.", styles['Normal']))

    elements.append(Spacer(1, 0.2 * cm))
    totales = Table(
        [
            [
                Paragraph("TOTALES DEL REPORTE", total_style),
                '', '', '',
            ],
            [
                Paragraph(f"Bienes<br/>{total_bienes}", total_value),
                Paragraph(f"Valor adquisición<br/>{_activos_moneda(suma_adq)}", total_value),
                Paragraph(f"Depreciación acum.<br/>{_activos_moneda(suma_dep)}", total_value),
                Paragraph(f"Valor neto<br/>{_activos_moneda(suma_neto)}", total_value),
            ],
        ],
        colWidths=[_ACTIVOS_ANCHO / 4.0] * 4,
    )
    totales.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), _ACTIVOS_NAVY),
        ('BACKGROUND', (0, 1), (-1, 1), _ACTIVOS_NAVY_SOFT),
        ('BOX', (0, 0), (-1, -1), 0.7, _ACTIVOS_NAVY),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, _ACTIVOS_GRID),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(totales)

    doc.build(elements, canvasmaker=CanvasNumerado)
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
    # Obtener todos los bienes dados de baja con sus datos de baja.
    # Se materializa una sola vez y se hace select_related solo de lo que se usa,
    # evitando repetir consultas pesadas (.exists()/.first()/.count()) contra el
    # servidor remoto. (Se quita el prefetch_related redundante: 'baja' ya viene
    # en el select_related.)
    bienes = list(Bien.objects.filter(estado='BAJA').select_related(
        'denominacion', 'cuenta_contable',
        'usuario_asignado', 'usuario_asignado__area', 'usuario_asignado__oficina',
        'local', 'local__entidad', 'area', 'oficina', 'baja'
    ).order_by('codigo_patrimonial'))
    total_bienes = len(bienes)
    
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
    if bienes:
        primer_bien = bienes[0]
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
    if bienes:
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
    
    # Obtener bienes agrupados por cuenta contable.
    # IMPORTANTE: se materializa en una lista para NO re-ejecutar la consulta de
    # agregación (GROUP BY) varias veces más adelante. Antes se recorría este
    # queryset hasta 4 veces (agrupar + 3 totales), cada una un viaje completo al
    # servidor SQL remoto -> de ahí la lentitud extrema.
    bienes_por_cuenta = list(bienes_query.values(
        'cuenta_contable__id',
        'cuenta_contable__codigo',
        'cuenta_contable__descripcion'
    ).annotate(
        cantidad=Count('id'),
        valor_adquisicion_total=Sum('valor_adquisicion'),
        valor_neto_total=Sum('valor_neto')
    ).order_by('cuenta_contable__codigo'))

    # Descripciones de las cuentas "base" (la parte antes del punto) en UNA sola
    # consulta, en lugar de una consulta por cada código base dentro del bucle.
    codigos_base_set = set()
    for item in bienes_por_cuenta:
        codigo = item['cuenta_contable__codigo']
        codigos_base_set.add(codigo.split('.')[0] if '.' in codigo else codigo)
    descripciones_base = dict(
        CuentaContable.objects.filter(codigo__in=codigos_base_set).values_list('codigo', 'descripcion')
    )
    
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
            # Descripción de la cuenta base (ya precargada en una sola consulta);
            # si no existe, se usa la descripción de la primera subcuenta.
            descripcion_base = descripciones_base.get(codigo_base) or item['cuenta_contable__descripcion']

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

