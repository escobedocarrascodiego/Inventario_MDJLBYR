from django.http import HttpResponse
from django.conf import settings
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import os
from organizacion.models import Local
from catalogos.models import CuentaContable
from bienes.models import Bien, ParametroSistema
from bajas.models import BajaBien
from .carga import cargar_bienes_con_relaciones
from .comunes import bienes_para_reporte, nombre_archivo


def generar_reporte_excel_bienes_detallados(request):
    """Reporte Excel detallado de bienes activos con todos los datos disponibles.

    Acepta por querystring los MISMOS filtros de la búsqueda avanzada del
    listado de bienes (ver apps/bienes/filtros.py): es la versión en Excel del
    botón "Generar reporte" de esa búsqueda. Sin filtros exporta todo.
    """
    # bienes_para_reporte carga sin JOINs ni ORDER BY en SQL (ver carga.py): en
    # este servidor esas consultas esperan hasta 25s por memoria
    # (RESOURCE_SEMAPHORE). Las relaciones se cosen en Python.
    bienes, filtros_texto, hay_filtros = bienes_para_reporte(request)

    # Crear libro de trabajo Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Bienes Detallados"
    
    # Estilos
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border_style = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    center_alignment = Alignment(horizontal='center', vertical='center')
    left_alignment = Alignment(horizontal='left', vertical='center')
    right_alignment = Alignment(horizontal='right', vertical='center')

    # Encabezados
    headers = [
        'Código Patrimonial',
        'Código Interno',
        'Denominación',
        'Grupo Genérico',
        'Clase',
        'Tipo de Cuenta',
        'Cuenta Contable',
        'Forma de Adquisición',
        'Fecha de Adquisición',
        'Resolución de Alta',
        'Valor de Adquisición',
        'Valor Neto',
        'Estado',
        'Usuario Asignado',
        'Documento Usuario',
        'Cargo Usuario',
        'Entidad',
        'Local',
        'Dirección Local',
        'Área',
        'Oficina',
        'Marca',
        'Modelo',
        'Color',
        'Serie',
        'Placa',
        'Número Motor',
        'Número Chasis',
        'Año Fabricación',
        'Otros Detalles',
        # --- Detalle de depreciación (CAMBIO 6, calculado por el modelo) ---
        'Tasa Depreciación (%)',
        'Fecha Inicio Depreciación',
        'Meses Depreciados',
        'Depreciación del Ejercicio (Mensual)',
        'Depreciación Acumulada',
        'Valor Neto (Calculado)',
        '¿Depreciable?'
    ]

    # Fila 1: constancia de los filtros con los que se generó el archivo, para
    # que quien lo reciba sepa si es el inventario completo o un subconjunto.
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    celda_filtros = ws.cell(row=1, column=1)
    celda_filtros.value = 'Filtros aplicados: ' + (
        ' | '.join(filtros_texto) if filtros_texto else 'ninguno (todos los bienes activos)'
    )
    celda_filtros.font = Font(bold=True, size=10)
    celda_filtros.alignment = left_alignment
    celda_filtros.fill = PatternFill(start_color="F2F6FC", end_color="F2F6FC", fill_type="solid")

    # Escribir encabezados (fila 2)
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_alignment
        cell.border = border_style
    
    # Corte = hoy para el snapshot de depreciación (fuente única: modelo). (CAMBIO 6)
    fecha_corte = datetime.now().date()

    # Parámetros UIT cargados UNA sola vez: sin esto, calcular_depreciacion()
    # consulta la BD por cada bien (N viajes al servidor SQL, muy lento en IIS).
    parametros_uit = list(ParametroSistema.objects.all())

    # Escribir datos (arrancan en la fila 3: 1 = filtros, 2 = encabezados)
    for row_num, bien in enumerate(bienes, 3):
        # Cálculo de depreciación con la MISMA lógica del modelo (sin reimplementar fórmula)
        dep = bien.calcular_depreciacion(fecha_corte, parametros=parametros_uit)
        fecha_inicio_dep = dep['fecha_inicio'].strftime('%d/%m/%Y') if dep['fecha_inicio'] else 'N/A'
        if dep['depreciable']:
            depreciable_txt = 'Sí'
        else:
            motivo = dep['motivo_no_depreciable']
            depreciable_txt = f"No ({motivo})" if motivo else 'No'
        tasa_pct = float(dep['tasa']) if dep['tasa'] is not None else 0.0

        # Obtener datos relacionados
        denominacion_nombre = bien.denominacion.nombre if bien.denominacion else bien.descripcion or 'N/A'
        grupo_generico = bien.denominacion.grupo_generico.nombre if bien.denominacion and bien.denominacion.grupo_generico else bien.grupo_generico or 'N/A'
        clase = bien.denominacion.clase.nombre if bien.denominacion and bien.denominacion.clase else bien.clase or 'N/A'
        cuenta_contable = str(bien.cuenta_contable) if bien.cuenta_contable else 'N/A'
        
        # Datos del usuario
        usuario_nombre = f"{bien.usuario_asignado.apellidos}, {bien.usuario_asignado.nombres}" if bien.usuario_asignado else 'N/A'
        usuario_doc = bien.usuario_asignado.numero_documento if bien.usuario_asignado else 'N/A'
        usuario_cargo = bien.usuario_asignado.cargo if bien.usuario_asignado else 'N/A'
        
        # Datos de ubicación
        entidad_nombre = bien.local.entidad.nombre if bien.local and bien.local.entidad else 'N/A'
        local_nombre = bien.local.nombre if bien.local else 'N/A'
        local_direccion = bien.local.direccion if bien.local else 'N/A'
        area_nombre = bien.area.nombre if bien.area else 'N/A'
        oficina_nombre = bien.oficina.nombre if bien.oficina else 'N/A'
        
        # Fecha formateada
        fecha_adq = bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else 'N/A'
        
        # Construir fila de datos
        row_data = [
            bien.codigo_patrimonial or 'N/A',
            bien.codigo_interno or 'N/A',
            denominacion_nombre,
            grupo_generico,
            clase,
            bien.get_tipo_cuenta_display(),
            cuenta_contable,
            bien.get_forma_adquisicion_display(),
            fecha_adq,
            bien.resolucion_alta or 'N/A',
            float(bien.valor_adquisicion),
            float(dep['valor_neto']),  # CAMBIO 6a: ahora usa el método del modelo
            bien.get_estado_display(),
            usuario_nombre,
            usuario_doc,
            usuario_cargo,
            entidad_nombre,
            local_nombre,
            local_direccion,
            area_nombre,
            oficina_nombre,
            bien.marca or 'N/A',
            bien.modelo or 'N/A',
            bien.color or 'N/A',
            bien.serie or 'N/A',
            bien.placa or 'N/A',
            bien.numero_motor or 'N/A',
            bien.numero_chasis or 'N/A',
            bien.anio_fabricacion or 'N/A',
            bien.otros_detalles or 'N/A',
            # --- Detalle de depreciación (CAMBIO 6) ---
            tasa_pct,                              # 31 Tasa Depreciación (%)
            fecha_inicio_dep,                      # 32 Fecha Inicio Depreciación
            dep['meses'],                          # 33 Meses Depreciados
            float(dep['cuota_mensual']),           # 34 Depreciación del Ejercicio (Mensual)
            float(dep['depreciacion_acumulada']),  # 35 Depreciación Acumulada
            float(dep['valor_neto']),              # 36 Valor Neto (Calculado)
            depreciable_txt                        # 37 ¿Depreciable?
        ]

        # Escribir fila
        for col_num, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell.value = value
            cell.border = border_style
            cell.alignment = left_alignment

            # Formato especial para columnas numéricas
            if col_num in [11, 12, 34, 35, 36]:  # Valores monetarios
                cell.number_format = '#,##0.00'
                cell.alignment = right_alignment
            elif col_num == 31:  # Tasa (%)
                cell.number_format = '0.00'
                cell.alignment = right_alignment
            elif col_num == 33:  # Meses (entero)
                cell.alignment = center_alignment
    
    # Ajustar ancho de columnas
    column_widths = {
        'A': 18,  # Código Patrimonial
        'B': 15,  # Código Interno
        'C': 40,  # Denominación
        'D': 20,  # Grupo Genérico
        'E': 20,  # Clase
        'F': 15,  # Tipo de Cuenta
        'G': 25,  # Cuenta Contable
        'H': 20,  # Forma de Adquisición
        'I': 15,  # Fecha de Adquisición
        'J': 20,  # Resolución de Alta
        'K': 18,  # Valor de Adquisición
        'L': 15,  # Valor Neto
        'M': 12,  # Estado
        'N': 30,  # Usuario Asignado
        'O': 15,  # Documento Usuario
        'P': 25,  # Cargo Usuario
        'Q': 40,  # Entidad
        'R': 30,  # Local
        'S': 40,  # Dirección Local
        'T': 30,  # Área
        'U': 30,  # Oficina
        'V': 15,  # Marca
        'W': 15,  # Modelo
        'X': 12,  # Color
        'Y': 20,  # Serie
        'Z': 12,  # Placa
        'AA': 20,  # Número Motor
        'AB': 20,  # Número Chasis
        'AC': 15,  # Año Fabricación
        'AD': 40,  # Otros Detalles
        'AE': 18,  # Tasa Depreciación (%)
        'AF': 20,  # Fecha Inicio Depreciación
        'AG': 16,  # Meses Depreciados
        'AH': 22,  # Depreciación del Ejercicio (Mensual)
        'AI': 20,  # Depreciación Acumulada
        'AJ': 18,  # Valor Neto (Calculado)
        'AK': 28,  # ¿Depreciable?
    }
    
    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width
    
    # Congelar la fila de filtros y la de encabezados
    ws.freeze_panes = 'A3'

    # Crear respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(
        nombre_archivo('reporte_bienes_detallados', 'xlsx', hay_filtros)
    )
    
    # Guardar libro de trabajo en la respuesta
    wb.save(response)
    return response




def generar_reporte_excel_bienes_por_local(request):
    """Genera un reporte Excel de bienes agrupados por local"""
    # Una sola carga de todos los bienes activos sin JOINs (ver carga.py) y
    # agrupación/orden/totales en Python: evita la consulta con agregados y las
    # ~30 consultas con JOINs (una por local) que esperaban memoria en el servidor.
    bienes_activos = cargar_bienes_con_relaciones(Bien.objects.exclude(estado='BAJA'))
    bienes_por_local = {}
    for b in bienes_activos:
        bienes_por_local.setdefault(b.local_id, []).append(b)

    locales = sorted(
        (l for l in Local.objects.order_by() if l.pk in bienes_por_local),
        key=lambda l: l.nombre or ''
    )
    
    # Crear libro de trabajo Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Bienes por Local"
    
    # Estilos
    header_fill = PatternFill(start_color="0d6efd", end_color="0d6efd", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    local_header_fill = PatternFill(start_color="cfe2ff", end_color="cfe2ff", fill_type="solid")
    local_header_font = Font(bold=True, size=11)
    border_style = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    center_alignment = Alignment(horizontal='center', vertical='center')
    left_alignment = Alignment(horizontal='left', vertical='center')
    
    row_num = 1
    
    # Iterar por cada local
    for local in locales:
        bienes = sorted(bienes_por_local[local.pk], key=lambda b: b.codigo_patrimonial or '')
        total_bienes = len(bienes)
        valor_total = sum((b.valor_neto or 0) for b in bienes)

        # Encabezado del local
        ws.merge_cells(f'A{row_num}:F{row_num}')
        cell = ws.cell(row=row_num, column=1)
        cell.value = f"LOCAL: {local.nombre}"
        cell.fill = local_header_fill
        cell.font = local_header_font
        cell.alignment = center_alignment
        cell.border = border_style
        row_num += 1

        ws.merge_cells(f'A{row_num}:F{row_num}')
        cell = ws.cell(row=row_num, column=1)
        cell.value = f"Dirección: {local.direccion} | Total Bienes: {total_bienes} | Valor Total: S/ {valor_total or 0:,.2f}"
        cell.border = border_style
        row_num += 1
        
        # Encabezados de la tabla
        headers = ['Código Patrimonial', 'Denominación', 'Área', 'Usuario', 'Valor Neto', 'Estado']
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_alignment
            cell.border = border_style
        row_num += 1
        
        # Datos de bienes
        for bien in bienes:
            denominacion = bien.denominacion.nombre if bien.denominacion else bien.descripcion or 'N/A'
            area = bien.area.nombre if bien.area else 'N/A'
            usuario = f"{bien.usuario_asignado.apellidos}, {bien.usuario_asignado.nombres}" if bien.usuario_asignado else 'N/A'
            
            row_data = [
                bien.codigo_patrimonial or 'N/A',
                denominacion,
                area,
                usuario,
                float(bien.valor_neto),
                bien.get_estado_display()
            ]
            
            for col_num, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=col_num)
                cell.value = value
                cell.border = border_style
                cell.alignment = left_alignment
                
                if col_num == 5:  # Valor Neto
                    cell.number_format = '#,##0.00'
                    cell.alignment = Alignment(horizontal='right', vertical='center')
            
            row_num += 1
        
        # Espacio entre locales
        row_num += 1
    
    # Ajustar ancho de columnas
    ws.column_dimensions['A'].width = 18
    ws.column_dimensions['B'].width = 40
    ws.column_dimensions['C'].width = 30
    ws.column_dimensions['D'].width = 30
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 12
    
    # Congelar primera fila
    ws.freeze_panes = 'A1'
    
    # Crear respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="reporte_bienes_por_local_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    
    wb.save(response)
    return response




def generar_reporte_excel_bienes_baja(request):
    """Genera un reporte Excel de todos los bienes dados de baja"""
    # Obtener todos los bienes dados de baja.
    # Sin JOINs ni ORDER BY en SQL (ver carga.py: evita esperas RESOURCE_SEMAPHORE).
    # Se ordena en Python replicando el mismo orden: fecha descendente, sin fecha al final.
    bienes = cargar_bienes_con_relaciones(Bien.objects.filter(estado='BAJA'))
    bienes.sort(
        key=lambda b: (b.fecha_adquisicion is not None, b.fecha_adquisicion or date.min),
        reverse=True
    )
    
    # Crear libro de trabajo Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Bienes Dados de Baja"
    
    # Estilos
    header_fill = PatternFill(start_color="dc3545", end_color="dc3545", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border_style = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    center_alignment = Alignment(horizontal='center', vertical='center')
    left_alignment = Alignment(horizontal='left', vertical='center')
    
    # Encabezados
    headers = [
        'Código Patrimonial',
        'Denominación',
        'Local',
        'Área',
        'Usuario Asignado',
        'Fecha de Adquisición',
        'Valor de Adquisición',
        'Valor Neto',
        'Forma de Adquisición',
        'Resolución de Alta'
    ]
    
    # Escribir encabezados
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_alignment
        cell.border = border_style
    
    # Escribir datos
    for row_num, bien in enumerate(bienes, 2):
        denominacion = bien.denominacion.nombre if bien.denominacion else bien.descripcion or 'N/A'
        local = bien.local.nombre if bien.local else 'N/A'
        area = bien.area.nombre if bien.area else 'N/A'
        usuario = f"{bien.usuario_asignado.apellidos}, {bien.usuario_asignado.nombres}" if bien.usuario_asignado else 'N/A'
        fecha_adq = bien.fecha_adquisicion.strftime('%d/%m/%Y') if bien.fecha_adquisicion else 'N/A'
        
        row_data = [
            bien.codigo_patrimonial or 'N/A',
            denominacion,
            local,
            area,
            usuario,
            fecha_adq,
            float(bien.valor_adquisicion),
            float(bien.valor_neto),
            bien.get_forma_adquisicion_display(),
            bien.resolucion_alta or 'N/A'
        ]
        
        for col_num, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell.value = value
            cell.border = border_style
            cell.alignment = left_alignment
            
            if col_num in [7, 8]:  # Valores
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal='right', vertical='center')
    
    # Ajustar ancho de columnas
    column_widths = {
        'A': 18, 'B': 40, 'C': 30, 'D': 30, 'E': 30,
        'F': 15, 'G': 18, 'H': 15, 'I': 20, 'J': 20
    }
    
    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width
    
    # Congelar primera fila
    ws.freeze_panes = 'A2'
    
    # Crear respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="reporte_bienes_baja_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    
    wb.save(response)
    return response


# ==============================================================================
# GENERACIÓN DE ETIQUETAS
# ==============================================================================

