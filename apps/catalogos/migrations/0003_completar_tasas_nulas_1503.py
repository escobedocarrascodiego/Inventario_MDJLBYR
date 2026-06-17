# Data migration: completa las tasas de depreciación NULL/0 de las cuentas 1503*
# según la Directiva N° 005-2016-EF/51.01 del MEF.
#
# ALCANCE (confirmado): SOLO cuentas 1503* que TIENEN bienes registrados.
# Los nodos agregadores y cuentas especiales sin bienes (Arrendamiento Financiero,
# Concesiones/APP, Afectación en Uso, Por Recibir/Distribuir, etc.) NO se tocan.
#
# Reglas:
#   1) Vehículos (1503.01*)            -> 10%  (override: aunque tengan otra tasa != 0)
#   2) Cómputo (1503.0203*, .020301)  -> 25%  (solo si tasa NULL o 0)
#   3) Cualquier otra 1503* (con bienes) con tasa NULL o 0 -> 10%
# No se modifican cuentas con tasa != 0 (salvo los vehículos del punto 1).
#
# Efecto esperado con los datos actuales: 4 cuentas ("Cultura y Arte" y
# "Deportes y Recreación") pasan de NULL a 10%. Vehículos y cómputo no cambian.
from decimal import Decimal

from django.db import migrations
from django.db.models import Q


def completar_tasas(apps, schema_editor):
    CuentaContable = apps.get_model('catalogos', 'CuentaContable')
    Bien = apps.get_model('bienes', 'Bien')
    nula_o_cero = Q(tasa_depreciacion__isnull=True) | Q(tasa_depreciacion=0)

    # Alcance conservador: ids de cuentas 1503* que TIENEN al menos un bien.
    ids_con_bienes = set(
        Bien.objects
        .filter(cuenta_contable__codigo__startswith='1503')
        .values_list('cuenta_contable_id', flat=True)
    )
    base = CuentaContable.objects.filter(id__in=ids_con_bienes)

    # 1) Vehículos (1503.01*) -> 10% (override, solo si difiere de 10).
    base.filter(codigo__startswith='1503.01').exclude(
        tasa_depreciacion=Decimal('10.00')
    ).update(tasa_depreciacion=Decimal('10.00'))

    # 2) Cómputo (1503.0203*) -> 25%, solo en las NULL o 0 (no pisa tasas existentes).
    base.filter(nula_o_cero, codigo__startswith='1503.0203').update(
        tasa_depreciacion=Decimal('25.00')
    )

    # 3) Resto 1503* (con bienes) con tasa NULL o 0 -> 10%.
    base.filter(nula_o_cero).exclude(
        codigo__startswith='1503.01'
    ).exclude(
        codigo__startswith='1503.0203'
    ).update(tasa_depreciacion=Decimal('10.00'))


def revertir(apps, schema_editor):
    # No-op: correctiva; no se restauran las tasas NULL/0 previas.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0002_corregir_tasas_directiva'),
        # Necesaria para consultar el modelo Bien (cuenta con bienes) en el estado histórico.
        ('bienes', '0003_bien_bien_cuenta_cob_idx'),
    ]

    operations = [
        migrations.RunPython(completar_tasas, revertir),
    ]
