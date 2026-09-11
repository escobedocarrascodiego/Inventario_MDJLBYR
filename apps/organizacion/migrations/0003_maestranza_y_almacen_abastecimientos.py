# Data migration correctiva, continúa a 0002_normalizar_areas_y_ubicaciones.
#
#   1) El "Almacen del Vaso de Leche" (Palacio Del Deporte) es un almacén
#      INDEPENDIENTE. Los dos bienes que figuraban ahí no le corresponden: van
#      al "Almacen" de la Oficina de Abastecimientos, en el Palacio Municipal.
#      Se mueven por código patrimonial para no arrastrar nada más.
#
#   2) "MAESTRANZA" estaba dada de alta como OFICINA de la Gerencia de Servicios
#      a la Ciudad, pero es un ambiente. Pasa a ser la ubicación física
#      "Maestranza" de esa gerencia (sin oficina) y sus 131 bienes se reubican
#      ahí antes de eliminar la oficina.
from django.db import migrations


# Los dos bienes mal ubicados (ver ANEXO N° 03 de RETAMOZO OJEDA, DNI 29571858).
CODIGOS_MAL_UBICADOS = ['602292810001', '112279700011']


def _ubicacion(apps, local, area, oficina, piso, detalle):
    """Busca la ubicación física indicada; si no existe, la crea."""
    UbicacionFisica = apps.get_model('organizacion', 'UbicacionFisica')
    encontrada = UbicacionFisica.objects.filter(
        local_id=local.id, area_id=area.id,
        oficina_id=oficina.id if oficina else None,
        detalle__iexact=detalle,
    ).order_by('id').first()
    if encontrada is not None:
        return encontrada
    return UbicacionFisica.objects.create(
        local_id=local.id, area_id=area.id,
        oficina_id=oficina.id if oficina else None,
        piso=piso, detalle=detalle, activo=True,
    )


def devolver_bienes_al_almacen_de_abastecimientos(apps):
    Local = apps.get_model('organizacion', 'Local')
    Area = apps.get_model('organizacion', 'Area')
    Oficina = apps.get_model('organizacion', 'Oficina')
    UbicacionFisica = apps.get_model('organizacion', 'UbicacionFisica')
    Bien = apps.get_model('bienes', 'Bien')

    palacio = Local.objects.filter(nombre__iexact='Palacio Municipal').first()
    ogaf = Area.objects.filter(
        nombre__iexact='Oficina General de Administración Financiera'
    ).first()
    if palacio is None or ogaf is None:
        return
    abastecimientos = Oficina.objects.filter(
        area_id=ogaf.id, nombre__iexact='Oficina de Abastecimientos'
    ).first()
    if abastecimientos is None:
        return

    almacen = _ubicacion(apps, palacio, ogaf, abastecimientos, piso=2, detalle='Almacen')

    # Solo se mueven si siguen en el almacén del Vaso de Leche: si alguien ya los
    # reubicó a mano, esta migración no le pisa el cambio.
    vaso_de_leche = list(
        UbicacionFisica.objects
        .filter(detalle__iexact='Almacen del Vaso de Leche')
        .values_list('id', flat=True)
    )
    if not vaso_de_leche:
        return

    Bien.objects.filter(
        codigo_patrimonial__in=CODIGOS_MAL_UBICADOS,
        ubicacion_fisica_id__in=vaso_de_leche,
    ).update(
        local_id=palacio.id,
        area_id=ogaf.id,
        oficina_id=abastecimientos.id,
        ubicacion_fisica_id=almacen.id,
    )


def maestranza_de_oficina_a_ubicacion(apps):
    Area = apps.get_model('organizacion', 'Area')
    Oficina = apps.get_model('organizacion', 'Oficina')
    UbicacionFisica = apps.get_model('organizacion', 'UbicacionFisica')
    Bien = apps.get_model('bienes', 'Bien')
    Personal = apps.get_model('personal', 'Personal')
    TrasladoBien = apps.get_model('traslados', 'TrasladoBien')

    gsc = Area.objects.filter(nombre__iexact='Gerencia de Servicios a la Ciudad').first()
    if gsc is None:
        return
    oficina = Oficina.objects.filter(area_id=gsc.id, nombre__iexact='MAESTRANZA').first()
    if oficina is None:
        return

    # La ubicación que ya colgaba de la oficina se reaprovecha (así conserva los
    # bienes que ya tenía) y se le quita la oficina.
    destino = UbicacionFisica.objects.filter(oficina_id=oficina.id).order_by('id').first()
    if destino is not None:
        destino.oficina_id = None
        destino.detalle = 'Maestranza'
        destino.save()
        sobrantes = UbicacionFisica.objects.filter(oficina_id=oficina.id).exclude(id=destino.id)
        for sobrante in sobrantes:
            Bien.objects.filter(ubicacion_fisica_id=sobrante.id).update(ubicacion_fisica_id=destino.id)
            TrasladoBien.objects.filter(ubicacion_origen_id=sobrante.id).update(ubicacion_origen_id=destino.id)
            TrasladoBien.objects.filter(ubicacion_destino_id=sobrante.id).update(ubicacion_destino_id=destino.id)
            sobrante.delete()
    else:
        local_id = (
            Bien.objects.filter(oficina_id=oficina.id)
            .values_list('local_id', flat=True).first()
        )
        if local_id is None:
            return
        destino = UbicacionFisica.objects.create(
            local_id=local_id, area_id=gsc.id, oficina_id=None,
            piso=1, detalle='Maestranza', activo=True,
        )

    # Los bienes de la oficina pasan al ambiente. Solo se les asigna la ubicación
    # si no tenían una y si están en el mismo local: nunca se pisa un dato mejor.
    Bien.objects.filter(
        oficina_id=oficina.id,
        ubicacion_fisica__isnull=True,
        local_id=destino.local_id,
    ).update(ubicacion_fisica_id=destino.id)
    Bien.objects.filter(oficina_id=oficina.id).update(area_id=gsc.id, oficina_id=None)

    Personal.objects.filter(oficina_id=oficina.id).update(area_id=gsc.id, oficina_id=None)
    for prefijo in ('origen', 'destino'):
        TrasladoBien.objects.filter(**{f'oficina_{prefijo}_id': oficina.id}).update(**{
            f'area_{prefijo}_id': gsc.id,
            f'oficina_{prefijo}_id': None,
        })

    oficina.delete()


def corregir(apps, schema_editor):
    devolver_bienes_al_almacen_de_abastecimientos(apps)
    maestranza_de_oficina_a_ubicacion(apps)


def revertir(apps, schema_editor):
    # Correctiva: no se vuelve a crear la oficina MAESTRANZA.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('organizacion', '0002_normalizar_areas_y_ubicaciones'),
        ('bienes', '0005_situacion_normal_faltante_sobrante'),
        ('personal', '0001_initial'),
        ('traslados', '0002_trasladobien_documento_autoriza'),
    ]

    operations = [
        migrations.RunPython(corregir, revertir),
    ]
