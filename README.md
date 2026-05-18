# Sistema de Inventario Patrimonial

Sistema web desarrollado en Django para la gestión y control de bienes patrimoniales institucionales.

## Requisitos previos

- **Python** 3.11 o superior
- **SQL Server** con ODBC Driver instalado (ODBC Driver 13/17/18 for SQL Server)
- **Git** (opcional, para clonar el repositorio)

## Instalación en un nuevo entorno

### 1. Clonar o copiar el proyecto

```bash
# Si usas git:
git clone <url-del-repositorio>
cd "Inventario Nuevo"

# O simplemente copia la carpeta del proyecto al destino deseado.
```

### 2. Crear el entorno virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar la base de datos

Editar el archivo `core/settings.py` y ajustar los datos de conexión:

```python
DATABASES = {
    "default": {
        "ENGINE": "mssql",
        "NAME": "dbInventario",       # Nombre de la base de datos
        "USER": "tu_usuario",          # Usuario de SQL Server
        "PASSWORD": "tu_contraseña",   # Contraseña
        "HOST": "10.0.1.2",            # IP o hostname del servidor
        "PORT": "1433",                # Puerto (por defecto 1433)
        "OPTIONS": {
            "driver": "ODBC Driver 13 for SQL Server",  # Ajustar según versión instalada
        },
    }
}
```

> **Nota:** Para verificar qué drivers ODBC tienes instalados, ejecuta:
> ```bash
> python -c "import pyodbc; print(pyodbc.drivers())"
> ```

### 5. Migraciones con base de datos existente (`--fake`)

Cuando ya existe una base de datos con datos (por ejemplo, al mover el proyecto a otro servidor que apunta a la misma BD), se deben registrar las migraciones sin ejecutarlas realmente, usando `--fake`.

#### Paso a paso:

```bash
# Activar el entorno virtual
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

# 1. Generar las migraciones iniciales (si no existen los archivos de migración)
python manage.py makemigrations organizacion
python manage.py makemigrations personal
python manage.py makemigrations catalogos
python manage.py makemigrations bienes
python manage.py makemigrations bajas
python manage.py makemigrations traslados
python manage.py makemigrations reportes
python manage.py makemigrations inventario

# 2. Aplicar migraciones de Django (auth, sessions, etc.)
#    Si la BD ya tiene estas tablas, usar --fake también:
python manage.py migrate --fake django.contrib.contenttypes
python manage.py migrate --fake django.contrib.auth
python manage.py migrate --fake django.contrib.admin
python manage.py migrate --fake django.contrib.sessions

# 3. Aplicar fake migrations para cada app EN ORDEN DE DEPENDENCIA.
#    El orden es importante porque algunas apps dependen de otras:
python manage.py migrate --fake organizacion
python manage.py migrate --fake personal
python manage.py migrate --fake catalogos
python manage.py migrate --fake bienes
python manage.py migrate --fake bajas
python manage.py migrate --fake traslados
python manage.py migrate --fake reportes
python manage.py migrate --fake inventario
```

#### ¿Por qué este orden?

Las apps tienen dependencias entre sí:

| App | Depende de |
|-----|-----------|
| `organizacion` | — (base) |
| `personal` | `organizacion` |
| `catalogos` | — (base) |
| `bienes` | `organizacion`, `personal`, `catalogos` |
| `bajas` | `bienes`, `personal`, `organizacion` |
| `traslados` | `bienes`, `personal`, `organizacion` |
| `reportes` | `bienes`, `organizacion`, `personal` |
| `inventario` | — (facade, sin modelos propios) |

#### ¿Cuándo usar `--fake`?

- **Base de datos nueva (vacía):** NO usar `--fake`. Ejecutar `python manage.py migrate` normalmente para que Django cree todas las tablas.
- **Base de datos existente con datos:** Usar `--fake` para que Django registre las migraciones como "ya aplicadas" sin intentar crear tablas que ya existen.

#### Limpiar migraciones conflictivas (si hay errores)

Si al ejecutar `migrate --fake` aparece un error de tipo `InconsistentMigrationHistory`, puede ser necesario limpiar la tabla `django_migrations`:

```sql
-- Ejecutar en SQL Server Management Studio o similar:
DELETE FROM django_migrations WHERE app IN (
    'organizacion', 'personal', 'catalogos', 'bienes',
    'bajas', 'traslados', 'reportes', 'inventario'
);
```

Luego volver a ejecutar los `migrate --fake` en el orden indicado arriba.

### 6. Ejecutar el servidor de desarrollo

```bash
python manage.py runserver
```

Acceder a: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

## Estructura del proyecto

```
Inventario Nuevo/
├── core/                    # Configuración principal de Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/                    # Aplicaciones del sistema
│   ├── organizacion/        # Entidad, Locales, Áreas, Oficinas, Ubicaciones
│   ├── personal/            # Gestión de personal
│   ├── catalogos/           # Grupos genéricos, Clases, Denominaciones, Cuentas
│   ├── bienes/              # CRUD de bienes patrimoniales (app principal)
│   ├── bajas/               # Registro de bajas de bienes
│   ├── traslados/           # Traslados entre usuarios/ubicaciones
│   ├── reportes/            # PDFs, Excel, etiquetas, fichas
│   └── inventario/          # Facade: agrupa URLs de todas las apps
├── templates/               # Plantillas HTML
│   ├── base.html            # Layout principal
│   ├── index.html           # Dashboard
│   └── inventario/          # Templates específicos por módulo
├── static/                  # Archivos estáticos (CSS, JS, imágenes)
├── images/                  # Logos e imágenes del sistema
├── venv/                    # Entorno virtual (no incluir en repositorio)
├── requirements.txt         # Dependencias de Python
├── manage.py                # CLI de Django
└── README.md                # Este archivo
```

## Notas adicionales

- El sistema usa **crispy-forms** con **Bootstrap 5** para los formularios.
- Los reportes PDF se generan con **ReportLab** y **xhtml2pdf**.
- Las etiquetas incluyen códigos QR generados con la librería **qrcode**.
- La exportación a Excel usa **openpyxl**.
