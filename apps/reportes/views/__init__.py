# Re-exportar todas las vistas de reportes para acceso simple
from .pdf import (
    reportes_index,
    reporte_depreciacion_filtros,
    generar_reporte_depreciacion,
    generar_reporte_bienes_activos,
    generar_reporte_bienes_por_local,
    generar_reporte_bienes_baja,
    generar_reporte_por_cuentas_contables,
)
from .excel import (
    generar_reporte_excel_bienes_detallados,
    generar_reporte_excel_bienes_por_local,
    generar_reporte_excel_bienes_baja,
)
from .etiquetas import (
    etiquetas_index,
    generar_etiquetas_pdf,
)
from .fichas import (
    fichas_index,
    buscar_bienes_para_ficha,
    generar_ficha_computo,
    generar_ficha_vehiculo,
    ficha_anexo03_index,
    buscar_personal_anexo03,
    datos_personal_anexo03,
    bienes_personal_anexo03,
    generar_ficha_anexo03,
)
