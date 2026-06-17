# Data migration: corrige la tasa de depreciación de los BIENES de vehículos de
# transporte TERRESTRE (cuenta 1503.0101) de 20% a 10%, según la Directiva
# N° 005-2016-EF/51.01 del MEF (vida útil de vehículos = 10 años -> 10%).
#
# Importante: el campo que realmente usa el cálculo es Bien.tasa_depreciacion
# (la cuenta contable ya estaba en 10%, pero los bienes tenían 20% "congelado").
#
# APARTE a propósito: aéreo (1503.0102) y acuático (1503.0103) NO se tocan; su
# tasa la definirá el usuario por separado.
from decimal import Decimal

from django.db import migrations


def corregir_tasa_vehiculos_terrestres(apps, schema_editor):
    Bien = apps.get_model('bienes', 'Bien')
    # Solo se tocan los bienes terrestres cuya tasa difiere de 10 (idempotente).
    Bien.objects.filter(
        cuenta_contable__codigo__startswith='1503.0101'
    ).exclude(
        tasa_depreciacion=Decimal('10.00')
    ).update(tasa_depreciacion=Decimal('10.00'))


def revertir(apps, schema_editor):
    # No-op: correctiva; no se restaura el 20%.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bienes', '0003_bien_bien_cuenta_cob_idx'),
    ]

    operations = [
        migrations.RunPython(corregir_tasa_vehiculos_terrestres, revertir),
    ]
