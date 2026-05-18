# ==============================================================================
# FACHADA DE FORMULARIOS
# ==============================================================================
# Re-exporta todos los formularios desde sus nuevas apps.
# Necesario para retrocompatibilidad con templates que importen desde aquí.
# ==============================================================================

from organizacion.forms import EntidadForm, LocalForm, AreaForm, OficinaForm, UbicacionFisicaForm
from personal.forms import PersonalForm
from catalogos.forms import CuentaContableForm, GrupoGenericoForm, ClaseForm, DenominacionForm
from bienes.forms import BienForm, EtiquetaFiltroForm, BuscarBienForm
from bajas.forms import BajaBienForm
