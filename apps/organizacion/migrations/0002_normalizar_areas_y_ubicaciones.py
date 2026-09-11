# Data migration: normaliza la estructura orgánica.
#
# Se habían dado de alta como ÁREAS (órganos/unidades orgánicas) cosas que en
# realidad son AMBIENTES, es decir, Ubicaciones Físicas:
#
#   1) "AUDITORIO MUNICIPAL"        -> creada DOS veces, ambas en Palacio Municipal.
#      Pasa a ser la ubicación física "Auditorio Municipal" de la Oficina de
#      Control Patrimonial y Servicios Generales (OGAF).
#
#   2) "almacen de VAso de leche"   -> con su oficina "ALMACEN DEL VASO DE LECHE".
#      Pasa a ser la ubicación física "Almacen del Vaso de Leche" de la Oficina
#      de Abastecimientos (OGAF), en el local Palacio Del Deporte.
#
# Además se deduplican las ubicaciones físicas: "MAESTRANZA" estaba registrada
# dos veces (una como detalle sin oficina y otra como oficina sin detalle) y se
# colapsan los duplicados exactos que pudieran quedar.
#
# Todo es idempotente y tolerante a que los nombres ya no existan: si un paso no
# encuentra sus filas, simplemente no hace nada.
from django.db import migrations


# ------------------------------------------------------------------ utilidades

def _limpiar(texto):
    """Colapsa espacios y recorta; '' se trata como None."""
    if texto is None:
        return None
    limpio = ' '.join(str(texto).split())
    return limpio or None


def _clave(ubicacion):
    """Identidad de una ubicación física para detectar repetidos."""
    detalle = _limpiar(ubicacion.detalle)
    return (
        ubicacion.local_id,
        ubicacion.area_id,
        ubicacion.oficina_id,
        ubicacion.piso,
        detalle.lower() if detalle else None,
    )


def _repuntar_ubicacion(apps, desde, hacia):
    """Mueve todo lo que cuelga de la ubicación `desde` hacia `hacia`."""
    Bien = apps.get_model('bienes', 'Bien')
    TrasladoBien = apps.get_model('traslados', 'TrasladoBien')

    Bien.objects.filter(ubicacion_fisica_id=desde.id).update(ubicacion_fisica_id=hacia.id)
    TrasladoBien.objects.filter(ubicacion_origen_id=desde.id).update(ubicacion_origen_id=hacia.id)
    TrasladoBien.objects.filter(ubicacion_destino_id=desde.id).update(ubicacion_destino_id=hacia.id)


def _repuntar_area(apps, area, area_destino, oficina_destino, ubicacion_destino, local_destino=None):
    """Saca a todos los bienes/personal/traslados del área que se va a eliminar."""
    Bien = apps.get_model('bienes', 'Bien')
    Personal = apps.get_model('personal', 'Personal')
    TrasladoBien = apps.get_model('traslados', 'TrasladoBien')
    Oficina = apps.get_model('organizacion', 'Oficina')

    oficinas_ids = list(Oficina.objects.filter(area_id=area.id).values_list('id', flat=True))

    campos_bien = {
        'area_id': area_destino.id,
        'oficina_id': oficina_destino.id if oficina_destino else None,
    }
    if ubicacion_destino is not None:
        campos_bien['ubicacion_fisica_id'] = ubicacion_destino.id
    if local_destino is not None:
        # El local del bien debe coincidir con el del ambiente donde está: si no,
        # el bien "vive" en un local y su ubicación física en otro.
        campos_bien['local_id'] = local_destino.id
    Bien.objects.filter(area_id=area.id).update(**campos_bien)
    if oficinas_ids:
        Bien.objects.filter(oficina_id__in=oficinas_ids).update(**campos_bien)

    Personal.objects.filter(area_id=area.id).update(
        area_id=area_destino.id,
        oficina_id=oficina_destino.id if oficina_destino else None,
    )
    if oficinas_ids:
        Personal.objects.filter(oficina_id__in=oficinas_ids).update(
            area_id=area_destino.id,
            oficina_id=oficina_destino.id if oficina_destino else None,
        )

    for prefijo in ('origen', 'destino'):
        campos_traslado = {
            f'area_{prefijo}_id': area_destino.id,
            f'oficina_{prefijo}_id': oficina_destino.id if oficina_destino else None,
        }
        if ubicacion_destino is not None:
            campos_traslado[f'ubicacion_{prefijo}_id'] = ubicacion_destino.id
        TrasladoBien.objects.filter(**{f'area_{prefijo}_id': area.id}).update(**campos_traslado)
        if oficinas_ids:
            TrasladoBien.objects.filter(
                **{f'oficina_{prefijo}_id__in': oficinas_ids}
            ).update(**campos_traslado)


def _ubicacion_destino(apps, ubicaciones_del_area, local, area, oficina, piso, detalle):
    """Reutiliza una de las ubicaciones del área que se elimina (así conserva los
    bienes que ya apunta) o crea una nueva; el resto se colapsa contra ella."""
    UbicacionFisica = apps.get_model('organizacion', 'UbicacionFisica')

    # ¿Ya existe la ubicación correcta (por ejemplo, al reejecutar)?
    existente = UbicacionFisica.objects.filter(
        local_id=local.id, area_id=area.id,
        oficina_id=oficina.id if oficina else None,
        detalle__iexact=detalle,
    ).first()

    ubicaciones = list(ubicaciones_del_area)
    if existente is not None:
        destino = existente
    elif ubicaciones:
        destino = ubicaciones.pop(0)
    else:
        destino = UbicacionFisica.objects.create(
            local_id=local.id, area_id=area.id,
            oficina_id=oficina.id if oficina else None,
            piso=piso, detalle=detalle, activo=True,
        )
        return destino

    destino.local_id = local.id
    destino.area_id = area.id
    destino.oficina_id = oficina.id if oficina else None
    if piso is not None:
        destino.piso = piso
    destino.detalle = detalle
    destino.activo = True
    destino.save()

    for sobrante in ubicaciones:
        if sobrante.id == destino.id:
            continue
        _repuntar_ubicacion(apps, sobrante, destino)
        sobrante.delete()

    return destino


# --------------------------------------------------------------------- pasos

def _mover_area_a_ubicacion(apps, nombre_area, local_nombre, area_destino_nombre,
                            oficina_destino_nombre, detalle, piso=None):
    Local = apps.get_model('organizacion', 'Local')
    Area = apps.get_model('organizacion', 'Area')
    Oficina = apps.get_model('organizacion', 'Oficina')
    UbicacionFisica = apps.get_model('organizacion', 'UbicacionFisica')

    areas = list(Area.objects.filter(nombre__iexact=nombre_area))
    if not areas:
        return

    local = Local.objects.filter(nombre__iexact=local_nombre).first()
    area_destino = Area.objects.filter(nombre__iexact=area_destino_nombre).first()
    if local is None or area_destino is None:
        return
    oficina_destino = None
    if oficina_destino_nombre:
        oficina_destino = Oficina.objects.filter(
            area_id=area_destino.id, nombre__iexact=oficina_destino_nombre
        ).first()
        if oficina_destino is None:
            return

    ubicaciones = list(
        UbicacionFisica.objects.filter(area_id__in=[a.id for a in areas]).order_by('id')
    )
    destino = _ubicacion_destino(
        apps, ubicaciones, local, area_destino, oficina_destino, piso, detalle
    )

    for area in areas:
        _repuntar_area(apps, area, area_destino, oficina_destino, destino, local_destino=local)

    # Ya nadie apunta a las áreas mal creadas: se eliminan ellas y sus oficinas.
    Oficina.objects.filter(area_id__in=[a.id for a in areas]).delete()
    Area.objects.filter(id__in=[a.id for a in areas]).delete()


def _fusionar_maestranza(apps):
    """MAESTRANZA estaba dos veces: como `detalle` suelto y como oficina propia.
    Se conserva la que cuelga de la oficina MAESTRANZA."""
    Area = apps.get_model('organizacion', 'Area')
    Oficina = apps.get_model('organizacion', 'Oficina')
    UbicacionFisica = apps.get_model('organizacion', 'UbicacionFisica')

    area = Area.objects.filter(nombre__iexact='Gerencia de Servicios a la Ciudad').first()
    if area is None:
        return
    oficina = Oficina.objects.filter(area_id=area.id, nombre__iexact='MAESTRANZA').first()
    if oficina is None:
        return

    destino = UbicacionFisica.objects.filter(
        area_id=area.id, oficina_id=oficina.id
    ).order_by('id').first()
    if destino is None:
        return

    sueltas = UbicacionFisica.objects.filter(
        area_id=area.id, oficina__isnull=True, detalle__iexact='MAESTRANZA'
    ).exclude(id=destino.id)
    for suelta in sueltas:
        _repuntar_ubicacion(apps, suelta, destino)
        suelta.delete()


def _colapsar_repetidas(apps):
    """Deja una sola ubicación física por (local, área, oficina, piso, detalle)."""
    UbicacionFisica = apps.get_model('organizacion', 'UbicacionFisica')

    vistas = {}
    for ubicacion in UbicacionFisica.objects.order_by('id'):
        detalle = _limpiar(ubicacion.detalle)
        if detalle != ubicacion.detalle:
            ubicacion.detalle = detalle
            ubicacion.save(update_fields=['detalle'])

        clave = _clave(ubicacion)
        if clave in vistas:
            _repuntar_ubicacion(apps, ubicacion, vistas[clave])
            ubicacion.delete()
        else:
            vistas[clave] = ubicacion


def normalizar(apps, schema_editor):
    _mover_area_a_ubicacion(
        apps,
        nombre_area='AUDITORIO MUNICIPAL',
        local_nombre='Palacio Municipal',
        area_destino_nombre='Oficina General de Administración Financiera',
        oficina_destino_nombre='Oficina de Control Patrimonial y Servicios Generales',
        detalle='Auditorio Municipal',
    )
    _mover_area_a_ubicacion(
        apps,
        nombre_area='almacen de VAso de leche',
        local_nombre='Palacio Del Deporte',
        area_destino_nombre='Oficina General de Administración Financiera',
        oficina_destino_nombre='Oficina de Abastecimientos',
        detalle='Almacen del Vaso de Leche',
        piso=1,
    )
    _fusionar_maestranza(apps)
    _colapsar_repetidas(apps)


def revertir(apps, schema_editor):
    # Correctiva: no se vuelven a crear las áreas mal registradas.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('organizacion', '0001_initial'),
        ('bienes', '0005_situacion_normal_faltante_sobrante'),
        ('personal', '0001_initial'),
        ('traslados', '0002_trasladobien_documento_autoriza'),
    ]

    operations = [
        migrations.RunPython(normalizar, revertir),
    ]
