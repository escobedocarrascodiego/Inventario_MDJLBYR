"""Filtros compartidos de Bienes (búsqueda simple + búsqueda avanzada).

¿Por qué existe este módulo? Los criterios de la búsqueda avanzada vivían
dentro de ``bienes_datatable`` mezclados con la paginación y el armado del
HTML de la tabla. Para poder generar un reporte "de lo que estoy viendo en
pantalla" había que copiar esa lógica en cada reporte, y a la primera
modificación la tabla y el PDF/Excel dejaban de coincidir.

Aquí queda la ÚNICA definición: el listado (apps/bienes/views.py) y los
reportes (apps/reportes/views/*) traducen la misma querystring al mismo
queryset, así que lo que se ve en pantalla es exactamente lo que sale impreso.

Nota de rendimiento: estas funciones solo arman el WHERE. Nunca agregan
``order_by`` ni ``select_related`` porque el servidor SQL no soporta esas
consultas sobre la tabla de bienes (ver apps/reportes/views/carga.py).
"""
from datetime import datetime

from django.db.models import Q


# Nombres de los parámetros que se aceptan por querystring. El listado los
# manda por AJAX y los reportes los reciben en la URL con los mismos nombres.
CAMPOS_FILTRO = (
    'search',            # buscador general (descripción, código, marca, modelo, placa)
    'codigo',            # código patrimonial (contiene)
    'denominacion',      # denominación / descripción (contiene)
    'denominacion_id',   # denominación exacta del catálogo
    'ubicacion_fisica',  # texto libre sobre la ubicación física
    'personal_id',
    'cuenta_id',
    'estado',
    'situacion',
    'resolucion_alta',   # Orden de Compra / Resolución de Alta (contiene)
    'marca',             # marca (contiene)
    'local_id',
    'area_id',
    'oficina_id',
    'fecha_inicio',      # fecha de adquisición desde (YYYY-MM-DD)
    'fecha_fin',         # fecha de adquisición hasta (YYYY-MM-DD)
)

# Etiquetas legibles para imprimir en la cabecera de los reportes.
ETIQUETAS_FILTRO = {
    'search': 'Búsqueda',
    'codigo': 'Código patrimonial',
    'denominacion': 'Denominación',
    'denominacion_id': 'Denominación',
    'ubicacion_fisica': 'Ubicación física',
    'personal_id': 'Personal asignado',
    'cuenta_id': 'Cuenta contable',
    'estado': 'Condición',
    'situacion': 'Situación',
    'resolucion_alta': 'Orden de compra / Resolución',
    'marca': 'Marca',
    'local_id': 'Local',
    'area_id': 'Área',
    'oficina_id': 'Oficina',
    'fecha_inicio': 'Adquisición desde',
    'fecha_fin': 'Adquisición hasta',
}


def parametros_filtro(request):
    """Extrae y limpia del request SOLO los parámetros de filtro reconocidos."""
    datos = request.GET
    params = {campo: (datos.get(campo, '') or '').strip() for campo in CAMPOS_FILTRO}
    # DataTables manda el buscador general como 'search[value]'.
    if not params['search']:
        params['search'] = (datos.get('search[value]', '') or '').strip()
    return params


def _a_fecha(valor):
    """Convierte 'YYYY-MM-DD' a date; devuelve None si el texto no es válido."""
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def filtrar_bienes(queryset, params):
    """Aplica los filtros de ``params`` sobre ``queryset``.

    Devuelve ``(queryset_filtrado, hay_filtros)``. ``hay_filtros`` sirve para
    que el listado se ahorre el segundo COUNT y para que los reportes sepan si
    se pidió el inventario completo o un subconjunto.
    """
    hay_filtros = False

    search = params.get('search', '')
    if search:
        hay_filtros = True
        queryset = queryset.filter(
            Q(descripcion__icontains=search) |
            Q(codigo_patrimonial__icontains=search) |
            Q(codigo_interno__icontains=search) |
            Q(marca__icontains=search) |
            Q(modelo__icontains=search) |
            Q(placa__icontains=search)
        )

    if params.get('codigo'):
        hay_filtros = True
        queryset = queryset.filter(codigo_patrimonial__icontains=params['codigo'])

    if params.get('denominacion'):
        hay_filtros = True
        queryset = queryset.filter(
            Q(denominacion__nombre__icontains=params['denominacion']) |
            Q(descripcion__icontains=params['denominacion'])
        )

    if params.get('denominacion_id', '').isdigit():
        hay_filtros = True
        queryset = queryset.filter(denominacion_id=int(params['denominacion_id']))

    if params.get('ubicacion_fisica'):
        ubicacion = params['ubicacion_fisica']
        hay_filtros = True
        queryset = queryset.filter(
            Q(ubicacion_fisica__detalle__icontains=ubicacion) |
            Q(ubicacion_fisica__area__nombre__icontains=ubicacion) |
            Q(ubicacion_fisica__oficina__nombre__icontains=ubicacion) |
            Q(ubicacion_fisica__local__nombre__icontains=ubicacion)
        )

    if params.get('personal_id', '').isdigit():
        hay_filtros = True
        queryset = queryset.filter(usuario_asignado_id=int(params['personal_id']))

    if params.get('cuenta_id', '').isdigit():
        hay_filtros = True
        queryset = queryset.filter(cuenta_contable_id=int(params['cuenta_id']))

    if params.get('local_id', '').isdigit():
        hay_filtros = True
        queryset = queryset.filter(local_id=int(params['local_id']))

    if params.get('area_id', '').isdigit():
        hay_filtros = True
        queryset = queryset.filter(area_id=int(params['area_id']))

    if params.get('oficina_id', '').isdigit():
        hay_filtros = True
        queryset = queryset.filter(oficina_id=int(params['oficina_id']))

    if params.get('estado'):
        hay_filtros = True
        queryset = queryset.filter(estado=params['estado'])

    if params.get('situacion'):
        hay_filtros = True
        queryset = queryset.filter(situacion=params['situacion'])

    if params.get('resolucion_alta'):
        hay_filtros = True
        queryset = queryset.filter(resolucion_alta__icontains=params['resolucion_alta'])

    if params.get('marca'):
        hay_filtros = True
        queryset = queryset.filter(marca__icontains=params['marca'])

    fecha_i = _a_fecha(params.get('fecha_inicio'))
    if fecha_i:
        hay_filtros = True
        queryset = queryset.filter(fecha_adquisicion__gte=fecha_i)

    fecha_f = _a_fecha(params.get('fecha_fin'))
    if fecha_f:
        hay_filtros = True
        queryset = queryset.filter(fecha_adquisicion__lte=fecha_f)

    return queryset, hay_filtros


def describir_filtros(params):
    """Traduce los filtros a una lista de textos legibles para la cabecera de
    los reportes (ej: ["Marca: HP", "Local: Palacio Municipal"]).

    Los ids se resuelven a su nombre. Son consultas puntuales a catálogos
    chicos (una por filtro usado), no afectan el rendimiento del reporte.
    """
    # Imports locales: este módulo lo importan los reportes y no conviene
    # arrastrar dependencias de otras apps al cargar bienes.filtros.
    from catalogos.models import CuentaContable, Denominacion
    from organizacion.models import Local, Area, Oficina
    from personal.models import Personal
    from .models import Bien

    def _nombre(modelo, pk, atributo='nombre'):
        obj = modelo.objects.filter(pk=pk).first()
        return getattr(obj, atributo, None) or f"#{pk}"

    descripciones = []
    for campo in CAMPOS_FILTRO:
        valor = (params.get(campo) or '').strip()
        if not valor:
            continue

        etiqueta = ETIQUETAS_FILTRO[campo]

        if campo == 'denominacion_id' and valor.isdigit():
            texto = _nombre(Denominacion, int(valor))
        elif campo == 'personal_id' and valor.isdigit():
            persona = Personal.objects.filter(pk=int(valor)).first()
            texto = f"{persona.apellidos}, {persona.nombres}" if persona else f"#{valor}"
        elif campo == 'cuenta_id' and valor.isdigit():
            cuenta = CuentaContable.objects.filter(pk=int(valor)).first()
            texto = str(cuenta) if cuenta else f"#{valor}"
        elif campo == 'local_id' and valor.isdigit():
            texto = _nombre(Local, int(valor))
        elif campo == 'area_id' and valor.isdigit():
            texto = _nombre(Area, int(valor))
        elif campo == 'oficina_id' and valor.isdigit():
            texto = _nombre(Oficina, int(valor))
        elif campo == 'estado':
            texto = dict(Bien.ESTADO_BIEN).get(valor, valor)
        elif campo == 'situacion':
            texto = dict(Bien.SITUACION_CHOICES).get(valor, valor)
        elif campo in ('fecha_inicio', 'fecha_fin'):
            fecha = _a_fecha(valor)
            texto = fecha.strftime('%d/%m/%Y') if fecha else valor
        else:
            texto = valor

        descripciones.append(f"{etiqueta}: {texto}")

    return descripciones
