"""Recalcula y guarda el campo Bien.valor_neto usando la lógica vigente del modelo.

El campo `Bien.valor_neto` es una foto del último save(); tras cambiar tasas o UIT
hay que recalcularlo para que los reportes (Excel/PDF/listados) muestren valores
actualizados. Este comando usa Bien.valor_neto_en() (fuente única) y guarda con
bulk_update (NO dispara el save() completo, así no regenera códigos ni otros campos).

Ejemplos:
    # Simular (no escribe nada), corte = hoy:
    python manage.py recalcular_valores_netos --dry-run
    # Aplicar de verdad:
    python manage.py recalcular_valores_netos
    # A una fecha de corte específica, incluyendo bajas:
    python manage.py recalcular_valores_netos --fecha-corte 2026-06-08 --incluir-bajas
"""
from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from bienes.models import Bien


class Command(BaseCommand):
    help = (
        "Recalcula y guarda Bien.valor_neto con la lógica vigente del modelo "
        "(Bien.valor_neto_en). Use --dry-run para simular sin escribir."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No guarda nada; solo informa cuántos bienes cambiarían.',
        )
        parser.add_argument(
            '--fecha-corte', dest='fecha_corte', default=None,
            help='Fecha de corte YYYY-MM-DD (por defecto: hoy).',
        )
        parser.add_argument(
            '--incluir-bajas', action='store_true',
            help='Incluye también los bienes en estado BAJA (por defecto se excluyen).',
        )
        parser.add_argument(
            '--batch-size', type=int, default=500,
            help='Tamaño de lote para bulk_update (por defecto 500).',
        )

    def handle(self, *args, **options):
        fecha_corte = None
        if options['fecha_corte']:
            try:
                fecha_corte = datetime.strptime(options['fecha_corte'], '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR(
                    'Formato de --fecha-corte inválido. Use YYYY-MM-DD.'
                ))
                return

        dry = options['dry_run']
        batch_size = max(1, options['batch_size'])

        qs = Bien.objects.select_related('cuenta_contable')
        if not options['incluir_bajas']:
            qs = qs.exclude(estado='BAJA')

        total = qs.count()
        self.stdout.write(
            f"Bienes a evaluar: {total} "
            f"(corte: {fecha_corte or 'hoy'}, bajas: {'incluidas' if options['incluir_bajas'] else 'excluidas'})"
        )

        procesados = 0
        cambiados = 0
        pendientes = []

        def _flush(lote):
            if lote and not dry:
                with transaction.atomic():
                    Bien.objects.bulk_update(lote, ['valor_neto'])

        for bien in qs.iterator(chunk_size=batch_size):
            procesados += 1
            nuevo = bien.valor_neto_en(fecha_corte)
            if nuevo is not None and Decimal(nuevo) != bien.valor_neto:
                bien.valor_neto = nuevo
                pendientes.append(bien)
                cambiados += 1
            if len(pendientes) >= batch_size:
                _flush(pendientes)
                pendientes = []

        _flush(pendientes)

        modo = 'SIMULACIÓN (no se guardó nada)' if dry else 'APLICADO'
        self.stdout.write(self.style.SUCCESS(
            f"[{modo}] Procesados: {procesados} | con cambio de valor_neto: {cambiados}"
        ))
        if dry and cambiados:
            self.stdout.write(
                "Ejecute sin --dry-run para guardar los cambios."
            )
