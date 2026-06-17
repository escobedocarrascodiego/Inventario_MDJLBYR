"""Tests del cálculo de depreciación según la Directiva N° 005-2016-EF/51.01 del MEF.

Regla clave validada: el umbral de 1/4 UIT se evalúa con la UIT del AÑO DE
ADQUISICIÓN del bien (no la del año en curso). Corte fijo de evaluación: 2026-06-08.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from bienes.models import Bien, ParametroSistema
from catalogos.models import CuentaContable


class DepreciacionDirectivaTests(TestCase):

    CORTE = date(2026, 6, 8)

    @classmethod
    def setUpTestData(cls):
        # UIT oficiales necesarias para los casos (divisor = 4 -> umbral = 1/4 UIT).
        ParametroSistema.objects.create(
            anio_fiscal=2006, valor_uit=Decimal('3400.00'), divisor_umbral_depreciacion=4,
        )
        ParametroSistema.objects.create(
            anio_fiscal=2025, valor_uit=Decimal('5350.00'), divisor_umbral_depreciacion=4,
        )
        ParametroSistema.objects.create(
            anio_fiscal=2026, valor_uit=Decimal('5500.00'), divisor_umbral_depreciacion=4,
            es_activo=True,
        )

        cls.cuenta_resto = CuentaContable.objects.create(
            codigo='1503.020502', descripcion='Mobiliario',
            tasa_depreciacion=Decimal('10.00'), vida_util_meses=120,
        )
        cls.cuenta_computo = CuentaContable.objects.create(
            codigo='1503.020301', descripcion='Equipos computacionales',
            tasa_depreciacion=Decimal('25.00'), vida_util_meses=48,
        )

    def test_caso_a_bien_2006_supera_umbral_y_toca_piso(self):
        """Caso A: 1503.020502, S/900, adquisición 2006-06-01.
        900 > 1/4 UIT 2006 (3400/4 = 850) -> SÍ depreciable.
        Bien de 2006 al 10%: ya tocó el piso de S/ 1.00."""
        bien = Bien(
            valor_adquisicion=Decimal('900.00'),
            fecha_adquisicion=date(2006, 6, 1),
            cuenta_contable=self.cuenta_resto,
        )
        dep = bien.calcular_depreciacion(self.CORTE)

        self.assertEqual(dep['anio_base_uit'], 2006)
        self.assertEqual(dep['umbral'], Decimal('850.00'))
        self.assertTrue(dep['depreciable'])
        self.assertEqual(dep['valor_neto'], Decimal('1.00'))
        self.assertEqual(bien.valor_neto_en(self.CORTE), Decimal('1.00'))

    def test_caso_b_computo_2025(self):
        """Caso B: 1503.020301, S/4599, adquisición 2025-04-28, tasa 25%.
        Depreciable; valor neto ≈ 3353.47 al 2026-06-08."""
        bien = Bien(
            valor_adquisicion=Decimal('4599.00'),
            fecha_adquisicion=date(2025, 4, 28),
            cuenta_contable=self.cuenta_computo,
        )
        dep = bien.calcular_depreciacion(self.CORTE)

        self.assertEqual(dep['anio_base_uit'], 2025)
        self.assertTrue(dep['depreciable'])
        self.assertEqual(dep['tasa'], Decimal('25.00'))
        self.assertEqual(dep['meses'], 13)
        self.assertEqual(dep['cuota_mensual'], Decimal('95.81'))
        self.assertEqual(dep['valor_neto'], Decimal('3353.47'))
        self.assertEqual(bien.valor_neto_en(self.CORTE), Decimal('3353.47'))

    def test_regresion_no_usa_uit_del_anio_en_curso(self):
        """El Caso A demostraría el bug si se usara la UIT 2026 (5500/4 = 1375):
        900 <= 1375 daría 'no depreciable'. Con la UIT 2006 (850) sí se deprecia."""
        bien = Bien(
            valor_adquisicion=Decimal('900.00'),
            fecha_adquisicion=date(2006, 6, 1),
            cuenta_contable=self.cuenta_resto,
        )
        dep = bien.calcular_depreciacion(self.CORTE)
        # Si tomara la UIT del año en curso (2026), el umbral sería 1375 y no depreciaría.
        self.assertNotEqual(dep['umbral'], Decimal('1375.00'))
        self.assertTrue(dep['depreciable'])
