"""Piezas compartidas por los reportes: carga filtrada, cabecera y paginado.

Los reportes que antes traían "todos los bienes activos" ahora aceptan por
querystring los mismos filtros de la búsqueda avanzada del listado (ver
apps/bienes/filtros.py). Este módulo concentra el paso de request -> lista de
bienes lista para imprimir, para no repetirlo en cada reporte.
"""
import os
from datetime import datetime
from io import BytesIO

from django.conf import settings
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from bienes.filtros import describir_filtros, filtrar_bienes, parametros_filtro
from bienes.models import Bien

from .carga import cargar_bienes_con_relaciones


ENTIDAD_NOMBRE = "MUNICIPALIDAD DISTRITAL DE JOSÉ LUIS BUSTAMANTE Y RIVERO"


def bienes_para_reporte(request, incluir_bajas=False):
    """Devuelve ``(bienes, filtros_texto, hay_filtros)`` según la querystring.

    Los bienes vienen con sus relaciones precargadas y ordenados por código
    patrimonial. Se usa ``cargar_bienes_con_relaciones`` (sin JOINs ni ORDER BY
    en SQL) porque este servidor deja esperando 25s las consultas que piden
    memoria de ejecución; ver apps/reportes/views/carga.py.
    """
    base = Bien.objects.all() if incluir_bajas else Bien.objects.exclude(estado='BAJA')
    params = parametros_filtro(request)
    queryset, hay_filtros = filtrar_bienes(base, params)

    bienes = cargar_bienes_con_relaciones(queryset)
    bienes.sort(key=lambda b: b.codigo_patrimonial or '')
    return bienes, describir_filtros(params), hay_filtros


class CanvasNumerado(canvas.Canvas):
    """Canvas que imprime "Pág. X de Y" al pie de cada página.

    ReportLab no conoce el total de páginas hasta terminar el documento, así
    que se guardan los estados de página y se escriben todos al final (receta
    estándar de ReportLab). Antes la cabecera decía "Pag. : 1 de 1" fijo.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas_guardadas = []

    def showPage(self):
        self._paginas_guardadas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas_guardadas)
        for estado in self._paginas_guardadas:
            self.__dict__.update(estado)
            self._dibujar_pie(total)
            super().showPage()
        super().save()

    def _dibujar_pie(self, total):
        ancho, _alto = self._pagesize
        self.setFont('Helvetica', 7)
        self.drawRightString(ancho - 1 * cm, 0.7 * cm, f"Pág. {self._pageNumber} de {total}")
        self.drawString(1 * cm, 0.7 * cm, f"Emitido: {datetime.now().strftime('%d/%m/%Y %H:%M')}")


def _logo_flowable(styles, label_style, tamano=1.5 * cm):
    """Celda con el logo institucional (o texto de respaldo si no existe)."""
    logo_path = os.path.join(settings.BASE_DIR, 'images', 'logo_transparente.png')
    texto_style = ParagraphStyle(
        'LogoText', parent=styles['Normal'], fontSize=6,
        fontName='Helvetica', alignment=TA_CENTER
    )
    pie = Paragraph("Software Inventario Mobiliario Institucional", texto_style)

    if os.path.exists(logo_path):
        try:
            pil_logo = PILImage.open(logo_path)
            if pil_logo.mode in ('RGBA', 'LA', 'P'):
                fondo = PILImage.new('RGB', pil_logo.size, (255, 255, 255))
                if pil_logo.mode == 'P':
                    pil_logo = pil_logo.convert('RGBA')
                if pil_logo.mode == 'RGBA':
                    fondo.paste(pil_logo, mask=pil_logo.split()[-1])
                else:
                    fondo.paste(pil_logo)
                pil_logo = fondo
            elif pil_logo.mode != 'RGB':
                pil_logo = pil_logo.convert('RGB')

            lado = 177  # 1.5 cm a 300 DPI
            pil_logo.thumbnail((lado, lado), PILImage.Resampling.LANCZOS)
            final = PILImage.new('RGB', (lado, lado), (255, 255, 255))
            x = (lado - pil_logo.size[0]) // 2
            y = (lado - pil_logo.size[1]) // 2
            final.paste(pil_logo, (x, y))

            buffer = BytesIO()
            final.save(buffer, format='PNG', dpi=(300, 300))
            buffer.seek(0)
            return [Image(buffer, width=tamano, height=tamano), pie]
        except Exception:
            pass

    return [Paragraph("SBN", label_style), pie]


def cabecera_reporte(titulo, filtros_texto=None, ancho_total=18 * cm, dependencia=None):
    """Bloque de cabecera común: logo, título, fecha, entidad y filtros aplicados.

    Devuelve la lista de flowables lista para insertar al inicio del PDF.
    ``filtros_texto`` es la lista que devuelve ``describir_filtros``; si viene
    vacía se imprime "Todos los bienes activos", para que el que recibe el
    reporte sepa siempre sobre qué universo se generó.
    """
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Heading1'], fontSize=14,
        textColor=colors.HexColor('#0066CC'), spaceAfter=10,
        alignment=TA_CENTER, fontName='Helvetica-Bold'
    )
    label_style = ParagraphStyle(
        'LabelStyle', parent=styles['Normal'], fontSize=8,
        fontName='Helvetica-Bold', alignment=TA_LEFT
    )
    header_style = ParagraphStyle(
        'HeaderStyle', parent=styles['Normal'], fontSize=7,
        fontName='Helvetica', alignment=TA_RIGHT
    )
    entity_style = ParagraphStyle(
        'EntityStyle', parent=styles['Normal'], fontSize=9,
        fontName='Helvetica', alignment=TA_CENTER, spaceAfter=5
    )
    filtro_style = ParagraphStyle(
        'FiltroStyle', parent=styles['Normal'], fontSize=8,
        fontName='Helvetica', alignment=TA_LEFT
    )

    ancho_lados = 3 * cm
    tabla_cabecera = Table(
        [[
            _logo_flowable(styles, label_style),
            [Paragraph(titulo, title_style)],
            [Paragraph(f"Fecha : {datetime.now().strftime('%d/%m/%Y')}", header_style),
             Paragraph(f"Hora : {datetime.now().strftime('%H:%M')}", header_style)],
        ]],
        colWidths=[ancho_lados, ancho_total - (2 * ancho_lados), ancho_lados]
    )
    tabla_cabecera.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))

    elementos = [tabla_cabecera, Spacer(1, 0.2 * cm),
                 Paragraph(f"ENTIDAD : {ENTIDAD_NOMBRE}", entity_style)]
    if dependencia:
        elementos.append(Paragraph(f"DEPENDENCIA : {dependencia}", entity_style))

    if filtros_texto:
        detalle = " &nbsp;|&nbsp; ".join(filtros_texto)
        texto = f"<b>Filtros aplicados:</b> {detalle}"
    else:
        texto = "<b>Filtros aplicados:</b> ninguno (todos los bienes activos)"

    tabla_filtros = Table([[Paragraph(texto, filtro_style)]], colWidths=[ancho_total])
    tabla_filtros.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#AAAAAA')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F2F6FC')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elementos.append(Spacer(1, 0.15 * cm))
    elementos.append(tabla_filtros)
    elementos.append(Spacer(1, 0.3 * cm))
    return elementos


def nombre_archivo(base, extension, hay_filtros=False):
    """Nombre de archivo con marca de tiempo (y aviso de filtrado)."""
    sufijo = '_filtrado' if hay_filtros else ''
    return f"{base}{sufijo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"
