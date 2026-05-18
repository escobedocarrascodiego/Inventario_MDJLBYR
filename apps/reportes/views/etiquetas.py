from django.shortcuts import render
from django.http import HttpResponse
from django.contrib import messages
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepInFrame, Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.utils import ImageReader
from datetime import datetime
from io import BytesIO
import json
import qrcode
import os
from PIL import Image as PILImage
from organizacion.models import Local, Area, Oficina, Entidad
from bienes.models import Bien
from bienes.forms import EtiquetaFiltroForm


def etiquetas_index(request):
    """Vista para seleccionar el tipo de generación de etiquetas"""
    if request.method == 'POST':
        form = EtiquetaFiltroForm(request.POST)
        if form.is_valid():
            return generar_etiquetas_pdf(request, form.cleaned_data)
    else:
        form = EtiquetaFiltroForm()
    
    return render(request, 'inventario/etiquetas_index.html', {'form': form})




def generar_etiquetas_pdf(request, form_data):
    """Genera etiquetas en PDF según los filtros seleccionados"""
    tipo_generacion = form_data.get('tipo_generacion')
    año = form_data.get('año')
    
    if not año:
        messages.error(request, "El campo 'Año' es obligatorio.")
        form = EtiquetaFiltroForm(request.POST)
        return render(request, 'inventario/etiquetas_index.html', {'form': form})
    
    # Obtener bienes según el tipo de generación
    bienes = Bien.objects.exclude(estado='BAJA').select_related(
        'denominacion', 'cuenta_contable', 'usuario_asignado',
        'local', 'area', 'oficina'
    )
    
    if tipo_generacion == 'bien_especifico':
        bien_id = form_data.get('bien')
        if bien_id:
            bienes = bienes.filter(id=bien_id.id)
        else:
            messages.error(request, "Debe seleccionar un bien específico.")
            form = EtiquetaFiltroForm(request.POST)
            return render(request, 'inventario/etiquetas_index.html', {'form': form})
    elif tipo_generacion == 'por_local':
        local = form_data.get('local')
        if local:
            bienes = bienes.filter(local=local)
        else:
            messages.error(request, "Debe seleccionar un local.")
            form = EtiquetaFiltroForm(request.POST)
            return render(request, 'inventario/etiquetas_index.html', {'form': form})
    elif tipo_generacion == 'por_area':
        area = form_data.get('area')
        if area:
            bienes = bienes.filter(area=area)
        else:
            messages.error(request, "Debe seleccionar un área.")
            form = EtiquetaFiltroForm(request.POST)
            return render(request, 'inventario/etiquetas_index.html', {'form': form})
    elif tipo_generacion == 'por_oficina':
        oficina = form_data.get('oficina')
        if oficina:
            bienes = bienes.filter(oficina=oficina)
        else:
            messages.error(request, "Debe seleccionar una oficina.")
            form = EtiquetaFiltroForm(request.POST)
            return render(request, 'inventario/etiquetas_index.html', {'form': form})
    elif tipo_generacion == 'por_año':
        año_adq = form_data.get('año_adquisicion')
        if año_adq:
            bienes = bienes.filter(fecha_adquisicion__year=año_adq)
        else:
            messages.error(request, "Debe especificar el año de adquisición.")
            form = EtiquetaFiltroForm(request.POST)
            return render(request, 'inventario/etiquetas_index.html', {'form': form})
    # Si es 'todos', no se filtra nada
    
    bienes = bienes.order_by('codigo_patrimonial')
    
    if not bienes.exists():
        messages.warning(request, "No se encontraron bienes con los criterios seleccionados.")
        form = EtiquetaFiltroForm(request.POST)
        return render(request, 'inventario/etiquetas_index.html', {'form': form})
    
    # Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="etiquetas_{}_{}.pdf"'.format(
        tipo_generacion, datetime.now().strftime('%Y%m%d_%H%M%S')
    )
    
    # Etiqueta 5cm x 2.5cm: una sola hoja por etiqueta
    etiqueta_width = 5*cm
    etiqueta_height = 2.5*cm
    pdf = canvas.Canvas(response, pagesize=(etiqueta_width, etiqueta_height))
    
    # Nombre de la institución desde el modelo Entidad
    entidad = Entidad.objects.first()
    nombre_institucion = entidad.nombre if entidad else "Municipalidad Distrital de José Luis Bustamante y Rivero"
    control_patrimonial_text = f"Control Patrimonial {año}"
    
    # Ruta del logo (se procesa una sola vez para evitar carga repetitiva)
    logo_path = os.path.join(settings.BASE_DIR, 'images', 'logo_transparente.png')
    logo_reader = None
    logo_buffer = None
    logo_size_cm = 0.40*cm
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
            target_px = 24
            pil_logo.thumbnail((target_px, target_px), PILImage.Resampling.LANCZOS)
            final_logo = PILImage.new('RGB', (target_px, target_px), (255, 255, 255))
            x_off = (target_px - pil_logo.size[0]) // 2
            y_off = (target_px - pil_logo.size[1]) // 2
            final_logo.paste(pil_logo, (x_off, y_off))
            logo_buffer = BytesIO()
            final_logo.save(logo_buffer, format='PNG')
            logo_buffer.seek(0)
            logo_reader = ImageReader(logo_buffer)
        except Exception:
            logo_reader = None
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Control Patrimonial: arriba, centrado, letra chica, no negrita
    control_style = ParagraphStyle(
        'ControlStyle',
        parent=styles['Normal'],
        fontSize=5.0,
        fontName='Helvetica',
        alignment=TA_CENTER,
        spaceAfter=0,
        spaceBefore=0,
        leading=5.0,
    )
    # Nombre institución: grande y negrita, a la derecha del logo
    institucion_style = ParagraphStyle(
        'InstitucionStyle',
        parent=styles['Normal'],
        fontSize=6.0,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        spaceAfter=0,
        spaceBefore=0,
        leading=6.2,
        leftIndent=0,
    )
    
    # Constantes de diseño
    h1, h2 = 0.28*cm, 0.42*cm
    h3 = etiqueta_height - h1 - h2
    ancho_col1 = 2.2*cm
    ancho_col2 = etiqueta_width - ancho_col1
    qr_size = 1.4*cm
    
    # Generar etiqueta para cada bien sin acumular en memoria
    first_page = True
    for bien in bienes.iterator(chunk_size=500):
        if not first_page:
            pdf.showPage()
        first_page = False
        # Crear datos para el QR
        qr_data = {
            'Codigo Patrimonial': bien.codigo_patrimonial or 'N/A',
            'Fecha Adquisición': bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else 'N/A',
            'valor_adquisicion': f"{bien.valor_adquisicion:,.2f}",
            'Nombre Oficina': bien.oficina.nombre if bien.oficina else 'N/A',
            'Usuario Asignado': f"{bien.usuario_asignado.apellidos}, {bien.usuario_asignado.nombres}" if bien.usuario_asignado else 'N/A'
        }
        qr_text = json.dumps(qr_data, ensure_ascii=False)
        
        # QR más grande para que se pueda leer
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=3,
            border=1,
        )
        qr.add_data(qr_text)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)

        # ===== Encabezado: Control Patrimonial + Nombre institución (logo centrado entre ambos) =====
        logo_cell_content = []
        if logo_reader and logo_buffer:
            logo_cell_content.append(
                Image(BytesIO(logo_buffer.getvalue()), width=logo_size_cm, height=logo_size_cm)
            )
        else:
            logo_cell_content.append(Paragraph("MD", institucion_style))
        
        nombre_cell = Paragraph(nombre_institucion, institucion_style)
        
        codigo_patrimonial = (bien.codigo_patrimonial or 'N/A').replace('.', '')
        denominacion_text = (bien.denominacion.nombre if bien.denominacion else bien.descripcion or 'N/A').upper()
        fecha_text = bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else 'N/A'
        oficina_text = bien.oficina.nombre if bien.oficina else 'N/A'
        
        codigo_style = ParagraphStyle(
            'CodigoStyle', parent=styles['Normal'],
            fontSize=7.2, fontName='Helvetica-Bold', alignment=TA_LEFT, spaceAfter=0, rightIndent=0, leftIndent=0, leading=7.6
        )
        den_font = 6.2 if len(denominacion_text) <= 24 else 5.6
        denominacion_style = ParagraphStyle(
            'DenominacionStyle', parent=styles['Normal'],
            fontSize=den_font, fontName='Helvetica-Bold', alignment=TA_LEFT, spaceAfter=0,
            rightIndent=0, leftIndent=0, leading=6.2, wordWrap='LTR', splitLongWords=False
        )
        fecha_style = ParagraphStyle(
            'FechaStyle', parent=styles['Normal'],
            fontSize=5.0, fontName='Helvetica', alignment=TA_LEFT, rightIndent=0, leftIndent=0, leading=5.4
        )
        oficina_style = ParagraphStyle(
            'OficinaStyle', parent=styles['Normal'],
            fontSize=4.8, fontName='Helvetica', alignment=TA_LEFT, rightIndent=0, leftIndent=0, leading=5.2
        )
        
        datos_flowables = [
            Paragraph(codigo_patrimonial, codigo_style),
            Paragraph(denominacion_text, denominacion_style),
            Paragraph(fecha_text, fecha_style),
            Paragraph(oficina_text, oficina_style),
        ]
        
        # Una sola tabla = una sola hoja. Alturas fijas para que NUNCA haya salto
        logo_cell = KeepInFrame(0.35*cm, h1 + h2, logo_cell_content, mode='shrink')
        control_cell = KeepInFrame(
            etiqueta_width - 0.7*cm, h1,
            [Paragraph(control_patrimonial_text, control_style)],
            mode='shrink'
        )
        nombre_cell_fit = KeepInFrame(
            etiqueta_width - 0.7*cm, h2,
            [nombre_cell],
            mode='shrink'
        )
        header_table = Table(
            [
                [logo_cell, control_cell, ''],
                ['', nombre_cell_fit, ''],
            ],
            colWidths=[0.35*cm, etiqueta_width - 0.7*cm, 0.35*cm],
            rowHeights=[h1, h2],
        )
        header_table.setStyle(TableStyle([
            ('SPAN', (0, 0), (0, 1)),  # Logo ocupa dos filas
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 1), 'CENTER'),
            ('VALIGN', (0, 0), (0, 1), 'MIDDLE'),
            ('VALIGN', (1, 0), (1, 1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 1), 0.35*cm),
            ('LEFTPADDING', (1, 0), (2, 1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        datos_cell = KeepInFrame(ancho_col2, h3, datos_flowables, mode='shrink')
        etiqueta_table = Table(
            [
                [header_table, ''],
                [Image(qr_buffer, width=qr_size, height=qr_size), datos_cell],
            ],
            colWidths=[ancho_col1, ancho_col2],
            rowHeights=[h1 + h2, h3],
            splitByRow=0,
        )
        etiqueta_table.setStyle(TableStyle([
            ('SPAN', (0, 0), (1, 0)),  # Unir fila del encabezado
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('VALIGN', (0, 1), (1, 1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LEFTPADDING', (1, 1), (1, 1), 3),
            # Separación entre encabezado y QR/datos
            ('TOPPADDING', (0, 1), (1, 1), 0.2*cm),
            # Separación del QR respecto al borde de la etiqueta
            ('LEFTPADDING', (0, 1), (0, 1), 0.3*cm),
            ('RIGHTPADDING', (0, 1), (0, 1), 0.2*cm),
            ('BOTTOMPADDING', (0, 1), (0, 1), 0.1*cm),
        ]))
        
        frame = Frame(
            0, 0, etiqueta_width, etiqueta_height,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
            showBoundary=0
        )
        frame.addFromList([etiqueta_table], pdf)
    
    # Finalizar PDF
    pdf.save()
    return response


# ==============================================================================
# MÓDULO DE BAJA DE BIENES
# ==============================================================================

