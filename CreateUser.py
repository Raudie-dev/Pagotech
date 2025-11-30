import os
import django
import argparse
import getpass
import sys
from django.contrib.auth.hashers import make_password

# Configura Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto.settings')
django.setup()

from app2.models import User_admin


def crear_usuario(nombre: str, password: str, email: str | None, telefono: str | None) -> None:
    if not nombre or not password:
        print("Error: 'nombre' y 'password' son obligatorios.")
        sys.exit(2)

    if User_admin.objects.filter(nombre=nombre).exists():
        print("Error: El nombre de usuario ya existe.")
        sys.exit(3)

    if email and User_admin.objects.filter(email=email).exists():
        print("Error: El email ya está registrado.")
        sys.exit(4)

    hashed_password = make_password(password)
    user = User_admin(
        nombre=nombre,
        password=hashed_password,
        email=email if email else None,
        telefono=telefono if telefono else None,
    )
    user.save()
    print("Usuario registrado correctamente:", nombre)


def parse_args():
    parser = argparse.ArgumentParser(description='Registrar un usuario admin (modo consola)')
    parser.add_argument('--nombre', '-n', help='Nombre de usuario')
    parser.add_argument('--password', '-p', help='Contraseña (no recomendado en la línea de comandos)')
    parser.add_argument('--email', '-e', help='Email del usuario', default=None)
    parser.add_argument('--telefono', '-t', help='Teléfono del usuario', default=None)
    parser.add_argument('--no-interactive', action='store_true', help='No pedir entrada interactiva; fallar si faltan campos')
    return parser.parse_args()


def main():
    args = parse_args()

    nombre = args.nombre
    password = args.password
    email = args.email
    telefono = args.telefono

    if not nombre:
        if args.no_interactive:
            print("Error: --nombre es obligatorio en modo no interactivo")
            sys.exit(1)
        nombre = input('Nombre: ').strip()

    if not password:
        if args.no_interactive:
            print("Error: --password es obligatorio en modo no interactivo")
            sys.exit(1)
        # ocultar contraseña al teclear
        password = getpass.getpass('Contraseña: ')

    # Normalizar cadenas vacías a None para email/telefono
    email = email.strip() if (email and email.strip()) else None
    telefono = telefono.strip() if (telefono and telefono.strip()) else None

    try:
        crear_usuario(nombre, password, email, telefono)
    except Exception as e:
        print('Error al crear el usuario:', str(e))
        sys.exit(10)


if __name__ == '__main__':
    main()