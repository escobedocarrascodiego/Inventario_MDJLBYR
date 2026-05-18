from django.db import models
from organizacion.models import Area, Oficina


# ==============================================================================
# 2. PERSONAL
# ==============================================================================

class Personal(models.Model):
    TIPO_DOCUMENTO = [
        ('DNI', 'DNI'),
        ('CE', 'Carnet de Extranjería'),
        ('PAS', 'Pasaporte'),
    ]
    
    MODALIDAD_CONTRATO = [
        ('CAS', 'CAS'),
        ('728', 'D.L. 728'),
        ('276', 'D.L. 276'),
        ('LOC', 'Locación de Servicios'),
        ('FUN', 'Funcionario'),
    ]

    nombres = models.CharField(max_length=150)
    apellidos = models.CharField(max_length=150)
    tipo_documento = models.CharField(max_length=10, choices=TIPO_DOCUMENTO, default='DNI')
    numero_documento = models.CharField(max_length=15, unique=True)
    modalidad = models.CharField(max_length=10, choices=MODALIDAD_CONTRATO)
    
    # Asignación Orgánica
    # Área es obligatoria (para casos como subgerentes que no tienen oficina)
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name='personal', verbose_name="Área")
    # Oficina es opcional (puede ser null para personal que solo pertenece al área)
    oficina = models.ForeignKey(Oficina, on_delete=models.PROTECT, related_name='personal', null=True, blank=True, verbose_name="Oficina")
    cargo = models.CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return f"{self.apellidos}, {self.nombres}"

    class Meta:
        verbose_name_plural = "Personal"
        db_table = 'inventario_personal'
