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
import socket
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
    """Genera etiquetas en PDF (o ZPL para Zebra) según los filtros seleccionados"""
    tipo_generacion = form_data.get('tipo_generacion')
    año = form_data.get('año')
    formato = form_data.get('formato') or 'pdf'

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
    elif tipo_generacion == 'por_usuario':
        usuario = form_data.get('usuario')
        if usuario:
            bienes = bienes.filter(usuario_asignado=usuario)
        else:
            messages.error(request, "Debe seleccionar un usuario.")
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

    # === Formato ZPL nativo para la impresora Zebra ZT411 ===
    if formato == 'zebra_zpl':
        return _responder_etiquetas_zpl(request, bienes, año, tipo_generacion)

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
# GENERACIÓN DE ETIQUETAS EN ZPL (IMPRESORA ZEBRA ZT411)
# ==============================================================================

def _zpl_dots(value_mm, dpi):
    """Convierte milímetros a puntos (dots) según la resolución del cabezal."""
    return int(round(value_mm * dpi / 25.4))


def _zpl_sanitizar(texto):
    """Quita los caracteres de control de ZPL (^ y ~) para no romper el formato."""
    if not texto:
        return ''
    return str(texto).replace('^', ' ').replace('~', ' ').strip()


def _logo_zpl_grf(target_w, threshold=150):
    """Convierte el logo de la Municipalidad a un gráfico ZPL (1 bit, blanco/negro).

    Devuelve (total_bytes, bytes_por_fila, alto_px, hex) o None si no hay logo.
    Las térmicas solo imprimen negro puro: se aplica un umbral (sin tramado) que
    deja el escudo como una silueta nítida y reconocible.
    """
    logo_path = os.path.join(settings.BASE_DIR, 'images', 'logo_transparente.png')
    if not os.path.exists(logo_path):
        return None
    try:
        img = PILImage.open(logo_path).convert('RGBA')
        fondo = PILImage.new('RGB', img.size, (255, 255, 255))
        fondo.paste(img, mask=img.split()[-1])
        gris = fondo.convert('L')
        w0, h0 = gris.size
        target_h = max(1, round(h0 * target_w / w0))
        gris = gris.resize((target_w, target_h), PILImage.Resampling.LANCZOS)
        bw = gris.point(lambda p: 255 if p >= threshold else 0).convert('1', dither=PILImage.Dither.NONE)
        px = bw.load()
        bytes_por_fila = (target_w + 7) // 8
        data = bytearray()
        for y in range(target_h):
            for bx in range(bytes_por_fila):
                byte = 0
                for bit in range(8):
                    x = bx * 8 + bit
                    if x < target_w and px[x, y] == 0:  # píxel negro
                        byte |= (1 << (7 - bit))
                data.append(byte)
        return len(data), bytes_por_fila, target_h, data.hex().upper()
    except Exception:
        return None


def _campos_etiqueta_zpl(bien, x_base, dpi, qr_mag, logo, anio, institucion,
                         x_titulo, ancho_titulo, x_datos, ancho_datos, margen=0):
    """Devuelve los comandos ZPL de UNA etiqueta, desplazada en X por `x_base`.

    `x_base` (en dots) permite colocar varias etiquetas lado a lado en la misma
    fila del rollo. `margen` (en dots) separa el logo y el QR del borde
    izquierdo de la etiqueta. El resto de coordenadas son relativas a la etiqueta.
    """
    def d(mm):
        return _zpl_dots(mm, dpi)

    codigo = _zpl_sanitizar(bien.codigo_patrimonial)
    denominacion = _zpl_sanitizar(bien.descripcion)
    fecha = bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else ''
    oficina = _zpl_sanitizar(bien.oficina.nombre if bien.oficina else '')

    campos = []
    # Logo (escudo) arriba a la izquierda
    if logo:
        campos.append(f'^FO{x_base + margen + d(0.7)},{d(0.7)}^XGR:LOGO.GRF,1,1^FS')
    campos += [
        # Control Patrimonial (arriba, centrado a la derecha del logo)
        f'^FO{x_base + x_titulo},{d(1.0)}^FB{ancho_titulo},1,0,C,0'
        f'^A0N,{d(2.3)},{d(2.3)}^FDControl Patrimonial {anio}^FS',
        # Institución (centrado, hasta 2 líneas)
        f'^FO{x_base + x_titulo},{d(3.7)}^FB{ancho_titulo},2,0,C,0'
        f'^A0N,{d(2.2)},{d(2.2)}^FD{institucion}^FS',
        # QR con el código patrimonial (izquierda)
        f'^FO{x_base + margen + d(0.7)},{d(9.2)}^BQN,2,{qr_mag}^FDMA,{codigo}^FS',
        # Bloque de datos (derecha): código en grande
        f'^FO{x_base + x_datos},{d(8.8)}'
        f'^A0N,{d(2.8)},{d(2.8)}^FD{codigo}^FS',
        # Denominación (hasta 2 líneas)
        f'^FO{x_base + x_datos},{d(11.9)}^FB{ancho_datos},2,0,L,0'
        f'^A0N,{d(2.0)},{d(2.0)}^FD{denominacion}^FS',
        # Fecha de adquisición
        f'^FO{x_base + x_datos},{d(16.6)}'
        f'^A0N,{d(1.9)},{d(1.9)}^FD{fecha}^FS',
        # Oficina (hasta 2 líneas)
        f'^FO{x_base + x_datos},{d(18.7)}^FB{ancho_datos},2,0,L,0'
        f'^A0N,{d(1.9)},{d(1.9)}^FD{oficina}^FS',
    ]
    return campos


def construir_zpl_etiquetas(bienes, anio, nombre_institucion, dpi=203,
                            columnas=2, ancho_mm=50, alto_mm=25, gap_mm=2,
                            margen_izq_mm=2.0, darkness=None, speed=None):
    """Construye el ZPL de una tanda de etiquetas para una Zebra.

    El rollo trae `columnas` etiquetas lado a lado (cada una de
    `ancho_mm` x `alto_mm`), separadas `gap_mm`. Por eso cada formato
    (^XA...^XZ) imprime una FILA completa de etiquetas y el papel avanza una
    sola vez por fila. Cada etiqueta lleva: 'Control Patrimonial {año}', el
    nombre de la institución, un QR con el código patrimonial y, al costado,
    código, denominación, fecha de adquisición y oficina.

    Todas las posiciones se calculan en milímetros y se convierten a dots según
    el DPI, por lo que el mismo código sirve para 203/300/600 dpi.
    """
    def d(mm):
        return _zpl_dots(mm, dpi)

    ancho = d(ancho_mm)
    alto = d(alto_mm)
    paso = d(ancho_mm + gap_mm)                 # distancia entre inicios de columna
    ancho_total = columnas * ancho + (columnas - 1) * d(gap_mm)
    # Magnificación del QR: módulos de ~0.4 mm -> siempre escaneable.
    qr_mag = max(2, round(dpi / 60))            # 203 dpi -> 3, 300 dpi -> 5

    # Margen izquierdo: separa logo, QR y título del borde de la etiqueta.
    margen = d(margen_izq_mm)

    institucion = _zpl_sanitizar(nombre_institucion)
    x_datos = d(14)
    ancho_datos = ancho - x_datos - d(0.5)

    # Logo del escudo: se descarga UNA sola vez a la memoria de la impresora
    # (~DG) y cada etiqueta solo lo invoca con ^XG. Si no hay logo, el título
    # ocupa todo el ancho centrado.
    logo = _logo_zpl_grf(d(6.8))
    if logo:
        logo_total, logo_bpr, _logo_h, logo_hex = logo
        x_titulo = margen + d(8.0)
    else:
        x_titulo = margen
    ancho_titulo = ancho - x_titulo - d(0.5)

    salida = []
    # Oscuridad y velocidad: comandos de control que se aplican a toda la tanda.
    # ~SD fija la oscuridad (0-30) ignorando el ajuste del driver de Windows.
    if darkness is not None:
        nivel = max(0, min(30, int(round(darkness))))
        salida.append(f'~SD{nivel:02d}')
    # ^PR fija la velocidad de impresión en pulgadas/seg (mm/s -> pulg/seg).
    if speed:
        pulg_seg = max(1, int(round(speed / 25.4)))
        salida.append(f'^XA^PR{pulg_seg}^XZ')
    if logo:
        # Comando de descarga del gráfico (una vez para toda la tanda)
        salida.append(f'~DGR:LOGO.GRF,{logo_total},{logo_bpr},{logo_hex}')

    # Agrupar los bienes en filas de `columnas` etiquetas
    lista = list(bienes)
    for inicio in range(0, len(lista), columnas):
        fila = lista[inicio:inicio + columnas]
        z = [
            '^XA',
            '^CI28',                            # UTF-8 (acentos y Ñ)
            f'^PW{ancho_total}',
            f'^LL{alto}',
            '^LH0,0',
        ]
        for col, bien in enumerate(fila):
            x_base = col * paso
            z += _campos_etiqueta_zpl(
                bien, x_base, dpi, qr_mag, logo, anio, institucion,
                x_titulo, ancho_titulo, x_datos, ancho_datos, margen,
            )
        z.append('^XZ')
        salida.append('\n'.join(z))

    return '\n'.join(salida)


def _enviar_zpl_a_impresora_windows(nombre_impresora, zpl_bytes):
    """Envía el ZPL crudo (RAW) a una impresora instalada en Windows.

    Usa el spooler de Windows en modo RAW, de modo que el driver ZDesigner
    deja pasar el ZPL tal cual hasta el cabezal (sin re-renderizarlo). Requiere
    el paquete `pywin32`. Lanza una excepción si algo falla.
    """
    import win32print

    handle = win32print.OpenPrinter(nombre_impresora)
    try:
        win32print.StartDocPrinter(handle, 1, ("Etiquetas patrimoniales", None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, zpl_bytes)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)


def _responder_etiquetas_zpl(request, bienes, anio, tipo_generacion):
    """Imprime el ZPL: primero por impresora USB de Windows, luego por red (IP)
    y, si nada está configurado o falla, descarga el archivo .zpl."""
    entidad = Entidad.objects.first()
    nombre_institucion = entidad.nombre if entidad else "Municipalidad Distrital de José Luis Bustamante y Rivero"
    dpi = getattr(settings, 'ZEBRA_PRINTER_DPI', 203)
    columnas = getattr(settings, 'ZEBRA_LABEL_COLUMNAS', 2)
    ancho_mm = getattr(settings, 'ZEBRA_LABEL_ANCHO_MM', 50)
    alto_mm = getattr(settings, 'ZEBRA_LABEL_ALTO_MM', 25)
    gap_mm = getattr(settings, 'ZEBRA_LABEL_GAP_MM', 2)
    margen_izq_mm = getattr(settings, 'ZEBRA_LABEL_MARGEN_IZQ_MM', 2.0)
    darkness = getattr(settings, 'ZEBRA_PRINTER_DARKNESS', None)
    speed = getattr(settings, 'ZEBRA_PRINTER_SPEED', None)

    zpl_bytes = construir_zpl_etiquetas(
        bienes, anio, nombre_institucion, dpi, columnas, ancho_mm, alto_mm,
        gap_mm, margen_izq_mm, darkness, speed
    ).encode('utf-8')

    nombre_impresora = (getattr(settings, 'ZEBRA_PRINTER_NAME', '') or '').strip()
    ip = (getattr(settings, 'ZEBRA_PRINTER_IP', '') or '').strip()
    port = getattr(settings, 'ZEBRA_PRINTER_PORT', 9100)

    # 1) Impresora USB/local instalada en Windows (impresión directa con un clic)
    if nombre_impresora:
        try:
            _enviar_zpl_a_impresora_windows(nombre_impresora, zpl_bytes)
            messages.success(request, f"Etiquetas enviadas a la impresora «{nombre_impresora}».")
            return render(request, 'inventario/etiquetas_index.html', {'form': EtiquetaFiltroForm()})
        except ImportError:
            messages.error(
                request,
                "Falta el paquete 'pywin32' para imprimir por USB. "
                "Instálalo con: pip install pywin32. Se descargó el archivo ZPL."
            )
        except Exception as exc:
            messages.error(
                request,
                f"No se pudo imprimir en «{nombre_impresora}» ({exc}). "
                "Verifica que la impresora esté encendida y con ese nombre exacto. "
                "Se descargó el archivo ZPL para que lo envíes manualmente."
            )

    # 2) Impresora en red por IP (puerto raw 9100)
    elif ip:
        try:
            with socket.create_connection((ip, port), timeout=5) as sock:
                sock.sendall(zpl_bytes)
            messages.success(request, f"Etiquetas enviadas a la impresora Zebra ({ip}).")
            return render(request, 'inventario/etiquetas_index.html', {'form': EtiquetaFiltroForm()})
        except OSError as exc:
            messages.error(
                request,
                f"No se pudo conectar con la impresora Zebra en {ip}:{port} ({exc}). "
                "Se descargó el archivo ZPL para que lo envíes manualmente."
            )

    # 3) Sin impresora configurada (o si falló el envío directo): descargar el .zpl
    response = HttpResponse(zpl_bytes, content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="etiquetas_{}_{}.zpl"'.format(
        tipo_generacion, datetime.now().strftime('%Y%m%d_%H%M%S')
    )
    return response


# ==============================================================================
# MÓDULO DE BAJA DE BIENES
# ==============================================================================

