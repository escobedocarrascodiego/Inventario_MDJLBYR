# ==============================================================================
# FACHADA DE MODELOS
# ==============================================================================
# Este archivo re-exporta todos los modelos desde sus nuevas apps.
# Es NECESARIO para que las migraciones existentes en inventario/migrations/
# sigan resolviendo los imports correctamente.
# NO ELIMINAR ESTE ARCHIVO.
# ==============================================================================

from organizacion.models import Entidad, Local, Area, Oficina, UbicacionFisica
from personal.models import Personal
from catalogos.models import CuentaContable, GrupoGenerico, Clase, Denominacion
from bienes.models import Bien, ParametroSistema, HistoricoDepreciacion, validar_cierre_anterior
from bajas.models import BajaBien
from traslados.models import TrasladoBien, EscaneoCodigoBarra
