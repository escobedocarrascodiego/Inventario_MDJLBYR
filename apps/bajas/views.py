from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import os
from bienes.models import Bien
from bienes.forms import BuscarBienForm
from .models import BajaBien
from .forms import BajaBienForm


# ==============================================================================
# MÓDULO DE BAJA DE BIENES
# ==============================================================================

def baja_bienes_list(request):
    """Lista de bienes dados de baja"""
    bajas = BajaBien.objects.select_related(
        'bien', 'bien__denominacion', 'bien__local', 'bien__area', 'bien__oficina'
    ).all().order_by('-fecha_registro')
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        bajas = bajas.filter(
            Q(bien__codigo_patrimonial__icontains=search) |
            Q(bien__descripcion__icontains=search) |
            Q(resolucion_baja__icontains=search) |
            Q(causal_baja__icontains=search)
        )
    
    return render(request, 'inventario/baja_bienes_list.html', {
        'bajas': bajas,
        'search': search
    })


def baja_bien_create(request):
    """Vista para registrar la baja de un bien"""
    buscar_form = BuscarBienForm(request.GET or None)
    bien = None
    baja_form = None
    
    # Si se busca un bien
    if request.GET.get('tipo_busqueda') and request.GET.get('valor_busqueda'):
        if buscar_form.is_valid():
            tipo = buscar_form.cleaned_data['tipo_busqueda']
            valor = buscar_form.cleaned_data['valor_busqueda'].strip()
            
            if valor:
                # Buscar el bien
                if tipo == 'codigo_patrimonial':
                    bien = Bien.objects.exclude(estado='BAJA').filter(
                        codigo_patrimonial__iexact=valor
                    ).select_related(
                        'denominacion', 'cuenta_contable', 'usuario_asignado',
                        'local', 'area', 'oficina'
                    ).first()
                elif tipo == 'codigo_interno':
                    bien = Bien.objects.exclude(estado='BAJA').filter(
                        codigo_interno__iexact=valor
                    ).select_related(
                        'denominacion', 'cuenta_contable', 'usuario_asignado',
                        'local', 'area', 'oficina'
                    ).first()
                elif tipo == 'denominacion':
                    bien = Bien.objects.exclude(estado='BAJA').filter(
                        Q(descripcion__icontains=valor) |
                        Q(denominacion__nombre__icontains=valor)
                    ).select_related(
                        'denominacion', 'cuenta_contable', 'usuario_asignado',
                        'local', 'area', 'oficina'
                    ).first()
                
                if bien:
                    # Verificar si ya tiene baja registrada
                    if hasattr(bien, 'baja'):
                        messages.warning(request, f"El bien {bien.codigo_patrimonial} ya tiene una baja registrada.")
                        bien = None
                    else:
                        # Crear formulario de baja con el bien encontrado
                        baja_form = BajaBienForm(initial={'bien': bien.id})
                else:
                    messages.error(request, "No se encontró ningún bien con los criterios de búsqueda.")
    
    # Si se envía el formulario de baja
    if request.method == 'POST':
        bien_id = request.POST.get('bien_id')
        if bien_id:
            try:
                bien = Bien.objects.get(id=bien_id)
                # Verificar que no tenga baja ya registrada
                if hasattr(bien, 'baja'):
                    messages.error(request, "Este bien ya tiene una baja registrada.")
                    return redirect('inventario:baja_bien_create')
                
                baja_form = BajaBienForm(request.POST)
                if baja_form.is_valid():
                    baja = baja_form.save(commit=False)
                    baja.bien = bien
                    # Actualizar el estado del bien a BAJA
                    bien.estado = 'BAJA'
                    bien.save()
                    # Guardar la baja
                    baja.save()
                    messages.success(request, f"Baja registrada exitosamente para el bien {bien.codigo_patrimonial}. Puede imprimir la ficha de baja desde el detalle.")
                    return redirect('inventario:baja_bien_detail', pk=baja.pk)
            except Bien.DoesNotExist:
                messages.error(request, "El bien especificado no existe.")
    
    return render(request, 'inventario/baja_bien_form.html', {
        'buscar_form': buscar_form,
        'bien': bien,
        'baja_form': baja_form
    })


def generar_ficha_baja(request, pk):
    """Genera el PDF 'Ficha de Datos - Baja de Bienes' para una baja registrada"""
    baja = get_object_or_404(BajaBien.objects.select_related(
        'bien', 'bien__denominacion', 'bien__cuenta_contable', 'bien__usuario_asignado',
        'bien__usuario_asignado__area', 'bien__usuario_asignado__oficina',
        'bien__local', 'bien__local__entidad', 'bien__area', 'bien__oficina'
    ), pk=pk)
    
    bien = baja.bien
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="ficha_baja_{}.pdf"'.format(
        datetime.now().strftime('%Y%m%d_%H%M%S')
    )
    
    doc = SimpleDocTemplate(
        response, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'],
        fontSize=14, textColor=colors.HexColor('#000000'),
        spaceAfter=8, alignment=TA_CENTER, fontName='Helvetica-Bold'
    )
    label_style = ParagraphStyle(
        'LabelStyle', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica-Bold', alignment=TA_LEFT
    )
    value_style = ParagraphStyle(
        'ValueStyle', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica', alignment=TA_LEFT
    )
    
    # Logo
    logo_path = os.path.join(settings.BASE_DIR, 'images', 'logo_transparente.png')
    if os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=1.8*cm, height=1.8*cm)
            logo_table = Table([[logo]], colWidths=[1.8*cm])
            logo_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            elements.append(logo_table)
        except Exception:
            pass
    elements.append(Spacer(1, 0.1*cm))
    
    # Título y fecha
    fecha_str = baja.fecha_resolucion.strftime('%d/%m/%Y') if baja.fecha_resolucion else datetime.now().strftime('%d/%m/%Y')
    header_table = Table([[
        Paragraph("FICHA DE DATOS - BAJA DE BIENES", title_style),
        Paragraph(f"Fecha: {fecha_str}", value_style)
    ]], colWidths=[14*cm, 4*cm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.4*cm))
    
    # Entidad y dependencia
    entidad_nombre = bien.local.entidad.nombre if bien.local and bien.local.entidad else "MUNICIPALIDAD DISTRITAL DE JOSÉ LUIS BUSTAMANTE Y RIVERO"
    dependencia_nombre = entidad_nombre[:45]
    
    for lbl, val in [("ENTIDAD :", entidad_nombre), ("DEPENDENCIA:", dependencia_nombre)]:
        elements.append(Paragraph(f"<b>{lbl}</b> {val}", value_style))
    elements.append(Spacer(1, 0.2*cm))
    
    # Denominación y código patrimonial
    denominacion = bien.denominacion.nombre if bien.denominacion else bien.descripcion or 'N/A'
    codigo_pat = bien.codigo_patrimonial or '-'
    denom_table = Table([[
        Paragraph(f"DENOMINACION: {denominacion}", value_style),
        Paragraph(f"CODIGO PATRIMONIAL: {codigo_pat}", value_style)
    ]], colWidths=[12*cm, 6*cm])
    denom_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(denom_table)
    elements.append(Spacer(1, 0.3*cm))
    
    # UBICACION y USUARIO (lado a lado)
    local_n = bien.local.nombre if bien.local else 'N/A'
    area_n = bien.area.nombre if bien.area else (bien.usuario_asignado.area.nombre if bien.usuario_asignado and bien.usuario_asignado.area else 'N/A')
    oficina_n = bien.oficina.nombre if bien.oficina else (bien.usuario_asignado.oficina.nombre if bien.usuario_asignado and bien.usuario_asignado.oficina else '-')
    
    usuario_nombre = f"{bien.usuario_asignado.nombres} {bien.usuario_asignado.apellidos}" if bien.usuario_asignado else 'N/A'
    usuario_dni = bien.usuario_asignado.numero_documento if bien.usuario_asignado else '-'
    usuario_modalidad = bien.usuario_asignado.get_modalidad_display() if bien.usuario_asignado else '-'
    
    ubicacion_table = Table([
        [Paragraph("UBICACION", label_style)],
        [Paragraph(f"LOCAL : {local_n}", value_style)],
        [Paragraph(f"AREA : {area_n}", value_style)],
        [Paragraph(f"OFICINA : {oficina_n}", value_style)],
    ], colWidths=[9*cm])
    usuario_table = Table([
        [Paragraph("USUARIO", label_style)],
        [Paragraph(f"NOMBRE: {usuario_nombre}", value_style)],
        [Paragraph(f"DNI/CARNET EXT.: {usuario_dni}", value_style)],
        [Paragraph(f"MODALIDAD: {usuario_modalidad}", value_style)],
    ], colWidths=[9*cm])
    
    for t in (ubicacion_table, usuario_table):
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
    
    two_col = Table([[ubicacion_table, usuario_table]], colWidths=[9*cm, 9*cm])
    two_col.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(two_col)
    elements.append(Spacer(1, 0.25*cm))
    
    # DATOS SOBRE EL BIEN
    cuenta_cod = bien.cuenta_contable.codigo if bien.cuenta_contable else 'N/A'
    valor_str = f"{bien.valor_neto:,.2f}"
    estado_str = bien.get_estado_display() if bien.estado else 'N/A'
    forma_adq = bien.get_forma_adquisicion_display() if bien.forma_adquisicion else 'N/A'
    fecha_adq = bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else '-'
    doc_adq = bien.resolucion_alta or '-'
    
    datos_bien_table = Table([
        [Paragraph("DATOS SOBRE EL BIEN", label_style)],
        [Paragraph(f"CODIGO INTERNO: {bien.codigo_interno or '-'}", value_style), Paragraph(f"CUENTA: {cuenta_cod}", value_style)],
        [Paragraph(f"VALOR (S/.): {valor_str}", value_style), Paragraph(f"ESTADO: {estado_str}", value_style)],
        [Paragraph(f"FORMA ADQUISICION: {forma_adq}", value_style), Paragraph(f"FEC. ADQUIS.: {fecha_adq}", value_style)],
        [Paragraph("ASEGURADO: NO", value_style), Paragraph(f"DOCUMENTO ADQ. : {doc_adq}", value_style)],
    ], colWidths=[9*cm, 9*cm])
    datos_bien_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(datos_bien_table)
    elements.append(Spacer(1, 0.25*cm))
    
    # DETALLE TECNICO
    detalle_tecnico_table = Table([
        [Paragraph("DETALLE TECNICO", label_style)],
        [
            Paragraph(f"MARCA: {bien.marca or '-'}", value_style),
            Paragraph(f"MODELO: {bien.modelo or '-'}", value_style),
            Paragraph(f"TIPO: -", value_style)
        ],
        [
            Paragraph(f"SERIE: {bien.serie or '-'}", value_style),
            Paragraph(f"COLOR: {bien.color or '-'}", value_style),
            Paragraph(f"OTROS: {bien.otros_detalles or '-'}", value_style)
        ],
    ], colWidths=[6*cm, 6*cm, 6*cm])
    detalle_tecnico_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(detalle_tecnico_table)
    elements.append(Spacer(1, 0.25*cm))
    
    # DATOS DE LA BAJA
    causal_display = dict(BajaBien.CAUSAL_BAJA_CHOICES).get(baja.causal_baja, baja.get_causal_baja_display())
    doc_sbn = baja.documento_sbn or '-'
    fecha_resol = baja.fecha_resolucion.strftime('%d/%m/%Y') if baja.fecha_resolucion else '-'
    
    datos_baja_table = Table([
        [Paragraph("DATOS DE LA BAJA", label_style)],
        [
            Paragraph(f"Nº RESOLUCION: {baja.resolucion_baja}", value_style),
            Paragraph(f"FECHA RESOL.: {fecha_resol}", value_style),
            Paragraph(f"CAUSAL DE BAJA: {causal_display}", value_style),
            Paragraph(f"DOCUMENTO SBN : {doc_sbn}", value_style)
        ],
    ], colWidths=[4.5*cm, 4.5*cm, 4.5*cm, 4.5*cm])
    datos_baja_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(datos_baja_table)
    
    doc.build(elements)
    return response


def baja_bien_detail(request, pk):
    """Detalle de una baja de bien"""
    baja = get_object_or_404(BajaBien.objects.select_related(
        'bien', 'bien__denominacion', 'bien__cuenta_contable', 'bien__usuario_asignado',
        'bien__local', 'bien__area', 'bien__oficina'
    ), pk=pk)
    
    return render(request, 'inventario/baja_bien_detail.html', {'baja': baja})
