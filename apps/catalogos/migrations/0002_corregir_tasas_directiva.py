# Data migration: corrige las tasas de depreciación de las cuentas contables
# para que coincidan con la Directiva N° 005-2016-EF/51.01 del MEF.
#
# Alcance (confirmado): SOLO las familias auditadas en el diagnóstico (punto 4a):
#   - Vehículos      (códigos que empiezan en '1503.01')   -> 10%
#   - Equipos cómputo (códigos que empiezan en '1503.0203') -> 25%  (incluye 1503.020301)
# NO se modifican otras cuentas ("resto") porque no fueron auditadas.
#
# Es idempotente y data-driven: solo actualiza las filas cuya tasa NO coincide con
# la Directiva (con los datos actuales, las 4 cuentas de vehículos pasan de 20% a 10%
# y las de cómputo no cambian porque ya están en 25%).
from django.db import migrations
from decimal import Decimal


TASAS_DIRECTIVA = [
    ('1503.01', Decimal('10.00')),    # Vehículos (incluye .0101 / .0102 / .0103)
    ('1503.0203', Decimal('25.00')),  # Cómputo (incluye .020301 / .020302 / .020303)
]


def corregir_tasas(apps, schema_editor):
    CuentaContable = apps.get_model('catalogos', 'CuentaContable')
    for prefijo, tasa in TASAS_DIRECTIVA:
        # Solo se actualizan las cuentas cuya tasa NO coincide con la Directiva.
        CuentaContable.objects.filter(
            codigo__startswith=prefijo
        ).exclude(tasa_depreciacion=tasa).update(tasa_depreciacion=tasa)


def revertir(apps, schema_editor):
    # No-op: la migración es correctiva; no se restauran las tasas erróneas previas.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(corregir_tasas, revertir),
    ]
