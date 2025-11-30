from typing import Optional, Tuple, List, Dict, Any
from django.db import IntegrityError
from django.contrib.auth.hashers import make_password

from .models import Cliente

def create_cliente(nombre: str, password: str, email: Optional[str]=None, telefono: Optional[str]=None) -> Tuple[Optional[Cliente], List[str]]:
    errors: List[str] = []
    nombre = (nombre or '').strip()
    if not nombre:
        errors.append('El nombre es obligatorio.')
    if not password:
        errors.append('La contraseña es obligatoria.')
    if Cliente.objects.filter(nombre=nombre).exists():
        errors.append('Ya existe un cliente con ese nombre.')
    if email and Cliente.objects.filter(email=email).exists():
        errors.append('El correo ya está en uso.')
    if errors:
        return None, errors
    try:
        cliente = Cliente(
            nombre=nombre,
            password=make_password(password),
            email=email or None,
            telefono=telefono or None,
            aprobado=False,
        )
        cliente.save()
        return cliente, []
    except IntegrityError:
        return None, ['Error al crear el cliente.']

def get_cliente(pk: Any) -> Optional[Cliente]:
    try:
        return Cliente.objects.get(pk=pk)
    except Cliente.DoesNotExist:
        return None

def update_cliente(pk: Any, data: Dict[str, Any]) -> List[str]:
    cliente = get_cliente(pk)
    if not cliente:
        return ['Cliente no encontrado.']

    nombre = data.get('nombre')
    if nombre:
        nombre = nombre.strip()
        if nombre != cliente.nombre and Cliente.objects.filter(nombre=nombre).exclude(pk=pk).exists():
            return ['El nombre ya está en uso por otro cliente.']
        cliente.nombre = nombre

    email = data.get('email')
    if email is not None:
        email = email.strip() or None
        if email != cliente.email and email and Cliente.objects.filter(email=email).exclude(pk=pk).exists():
            return ['El correo ya está en uso por otro cliente.']
        cliente.email = email

    telefono = data.get('telefono')
    if telefono is not None:
        cliente.telefono = telefono.strip() or None

    password = data.get('password')
    if password:
        cliente.password = make_password(password)

    if 'aprobado' in data and data['aprobado'] is not None:
        cliente.aprobado = bool(data['aprobado'])

    try:
        cliente.save()
        return []
    except IntegrityError:
        return ['Error al actualizar el cliente.']

def delete_cliente(pk: Any) -> bool:
    cliente = get_cliente(pk)
    if not cliente:
        return False
    cliente.delete()
    return True

def list_clientes(filters: Optional[Dict[str, Any]] = None):
    qs = Cliente.objects.all()
    if not filters:
        return qs
    if 'aprobado' in filters and filters['aprobado'] is not None:
        qs = qs.filter(aprobado=filters['aprobado'])
    if 'nombre' in filters and filters['nombre']:
        qs = qs.filter(nombre__icontains=filters['nombre'])
    return qs
