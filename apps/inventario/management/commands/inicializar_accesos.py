"""
Comando de configuración inicial de accesos del sistema.

Crea (de forma idempotente: se puede correr varias veces sin duplicar nada):
  1. Grupo "Administrador"  -> con TODOS los permisos.
  2. Grupo "Trabajador"     -> solo lectura + registrar traslados.
  3. Usuario superusuario "admin" / "Admin123" (el administrador definitivo).

Uso:
    python manage.py inicializar_accesos

Opciones:
    --admin-pass NUEVA_CLAVE   Define otra contraseña para el usuario admin.

Para crear un usuario TRABAJADOR nuevo no hace falta este comando: se hace
desde el panel /admin (Usuarios -> Agregar) y se le asigna el grupo "Trabajador".
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

# Permisos que tendrá el grupo "Trabajador" (además de poder ver todo, que el
# sistema permite a cualquier usuario con sesión iniciada).
PERMISOS_TRABAJADOR = [
    ('traslados', 'add_trasladobien'),
    ('traslados', 'change_trasladobien'),
    ('traslados', 'view_trasladobien'),
]

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD_DEFECTO = 'Admin123'


class Command(BaseCommand):
    help = 'Crea los grupos de roles (Administrador / Trabajador) y el superusuario admin.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-pass',
            dest='admin_pass',
            default=ADMIN_PASSWORD_DEFECTO,
            help='Contraseña para el usuario admin (por defecto: Admin123).',
        )

    def handle(self, *args, **options):
        self._crear_grupo_administrador()
        self._crear_grupo_trabajador()
        self._crear_admin(options['admin_pass'])
        self.stdout.write(self.style.SUCCESS('\nAccesos inicializados correctamente.'))

    # ------------------------------------------------------------------ grupos
    def _crear_grupo_administrador(self):
        grupo, creado = Group.objects.get_or_create(name='Administrador')
        grupo.permissions.set(Permission.objects.all())
        verbo = 'creado' if creado else 'actualizado'
        self.stdout.write(
            self.style.SUCCESS(f'  Grupo "Administrador" {verbo} (todos los permisos).')
        )

    def _crear_grupo_trabajador(self):
        grupo, creado = Group.objects.get_or_create(name='Trabajador')

        permisos = []
        for app_label, codename in PERMISOS_TRABAJADOR:
            try:
                permisos.append(
                    Permission.objects.get(
                        content_type__app_label=app_label, codename=codename
                    )
                )
            except Permission.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ! Permiso {app_label}.{codename} no existe todavía '
                        f'(¿faltan migraciones?). Se omite.'
                    )
                )

        grupo.permissions.set(permisos)
        verbo = 'creado' if creado else 'actualizado'
        self.stdout.write(
            self.style.SUCCESS(
                f'  Grupo "Trabajador" {verbo} '
                f'(solo lectura + registrar traslados).'
            )
        )

    # ------------------------------------------------------------- superusuario
    def _crear_admin(self, password):
        User = get_user_model()
        user, creado = User.objects.get_or_create(
            username=ADMIN_USERNAME,
            defaults={'is_staff': True, 'is_superuser': True},
        )

        if creado:
            # set_password NO pasa por los validadores, así que 'Admin123' se
            # acepta aunque sea parecida al nombre de usuario.
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            grupo_admin = Group.objects.filter(name='Administrador').first()
            if grupo_admin:
                user.groups.add(grupo_admin)
            self.stdout.write(
                self.style.SUCCESS(
                    f'  Usuario superusuario "{ADMIN_USERNAME}" creado '
                    f'(contraseña: {password}).'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'  Usuario "{ADMIN_USERNAME}" ya existía: no se modificó su '
                    f'contraseña. (Para reiniciarla usa: '
                    f'python manage.py changepassword {ADMIN_USERNAME})'
                )
            )
