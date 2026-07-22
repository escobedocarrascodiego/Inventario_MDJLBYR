"""Carga de bienes con sus relaciones SIN usar JOINs en SQL.

¿Por qué existe esto? El SQL Server del sistema trabaja corto de memoria:
cualquier consulta con JOINs grandes u ORDER BY sobre la tabla de bienes pide
una concesión de memoria de ejecución (memory grant) y el servidor la deja
esperando hasta 25 segundos en RESOURCE_SEMAPHORE antes de ejecutarla. Por eso
los reportes tardaban ~50-70s aunque el cálculo y el archivo en sí tomen ~2s.

La alternativa: traer cada tabla por separado (consultas planas que no piden
memoria de ejecución) y "coser" las relaciones en Python. Las tablas
relacionadas son catálogos chicos (decenas a pocos miles de filas), así que
todo el proceso tarda ~2 segundos y el resultado es idéntico al de
select_related().
"""
from catalogos.models import CuentaContable, Denominacion, GrupoGenerico, Clase
from organizacion.models import Entidad, Local, Area, Oficina
from personal.models import Personal


def cargar_bienes_con_relaciones(queryset):
    """Materializa un queryset de Bien y deja precargadas las relaciones:
    denominacion (con grupo_generico y clase), cuenta_contable,
    usuario_asignado (con area y oficina), local (con entidad), area y oficina.

    El queryset NO debe llevar select_related ni order_by (aquí se eliminan);
    si se necesita un orden, ordenar la lista devuelta con sorted()/list.sort().
    """
    # .order_by() vacío elimina cualquier ordering (incluido Meta.ordering)
    # para que ninguna de estas consultas genere un sort en el servidor.
    bienes = list(queryset.order_by())

    grupos = {g.pk: g for g in GrupoGenerico.objects.order_by()}
    clases = {c.pk: c for c in Clase.objects.order_by()}
    cuentas = {c.pk: c for c in CuentaContable.objects.order_by()}
    denominaciones = {d.pk: d for d in Denominacion.objects.order_by()}
    entidades = {e.pk: e for e in Entidad.objects.order_by()}
    locales = {l.pk: l for l in Local.objects.order_by()}
    areas = {a.pk: a for a in Area.objects.order_by()}
    oficinas = {o.pk: o for o in Oficina.objects.order_by()}
    personales = {p.pk: p for p in Personal.objects.order_by()}

    # Relaciones anidadas de los catálogos
    for d in denominaciones.values():
        if d.grupo_generico_id:
            d.grupo_generico = grupos.get(d.grupo_generico_id)
        if d.clase_id:
            d.clase = clases.get(d.clase_id)
    for l in locales.values():
        if l.entidad_id:
            l.entidad = entidades.get(l.entidad_id)
    for a in areas.values():
        if a.local_id:
            a.local = locales.get(a.local_id)
    for p in personales.values():
        if p.area_id:
            p.area = areas.get(p.area_id)
        if p.oficina_id:
            p.oficina = oficinas.get(p.oficina_id)

    # Relaciones directas de cada bien
    for b in bienes:
        if b.denominacion_id:
            b.denominacion = denominaciones.get(b.denominacion_id)
        if b.cuenta_contable_id:
            b.cuenta_contable = cuentas.get(b.cuenta_contable_id)
        if b.usuario_asignado_id:
            b.usuario_asignado = personales.get(b.usuario_asignado_id)
        if b.local_id:
            b.local = locales.get(b.local_id)
        if b.area_id:
            b.area = areas.get(b.area_id)
        if b.oficina_id:
            b.oficina = oficinas.get(b.oficina_id)

    return bienes
