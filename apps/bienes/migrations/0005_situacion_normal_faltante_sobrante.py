# Cambia el campo Bien.situacion de USO/DESUSO a las 3 situaciones de
# verificación de inventario: N (Normal), F (Faltante), S (Sobrante).
#
# Todos los bienes existentes (sin importar la situación que tuvieran) pasan a
# 'N' (Normal); la regularización posterior la hace el usuario desde el sistema.
#
# Nota: max_length se mantiene en 10 a propósito. La columna forma parte del
# índice (estado, situacion) y en SQL Server un ALTER COLUMN sobre una columna
# indexada obliga a soltar/recrear el índice sin necesidad real.
from django.db import migrations, models


def situaciones_a_normal(apps, schema_editor):
    Bien = apps.get_model('bienes', 'Bien')
    # Idempotente: solo toca lo que aún no está en 'N'.
    Bien.objects.exclude(situacion='N').update(situacion='N')


def revertir(apps, schema_editor):
    # No-op: los valores anteriores (USO/DESUSO) no se pueden reconstruir.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bienes', '0004_corregir_tasa_vehiculos_terrestres'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bien',
            name='situacion',
            field=models.CharField(
                choices=[('N', 'Normal'), ('F', 'Faltante'), ('S', 'Sobrante')],
                default='N',
                max_length=10,
                verbose_name='Situación',
            ),
        ),
        migrations.RunPython(situaciones_a_normal, revertir),
    ]
