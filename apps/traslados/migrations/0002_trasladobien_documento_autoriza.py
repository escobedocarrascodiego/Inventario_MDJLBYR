from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('traslados', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='trasladobien',
            name='documento_autoriza',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Documento que autoriza el Traslado'),
        ),
    ]
