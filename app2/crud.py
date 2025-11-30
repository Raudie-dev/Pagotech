from typing import Tuple, Optional, Any, Dict, List
from django.db import IntegrityError
from app1.models import Cliente

def list_pending_clientes() -> List[Cliente]:
    return list(Cliente.objects.filter(aprobado=False))

def list_clientes(filters: Optional[Dict[str, Any]] = None):
    qs = Cliente.objects.all()
    if not filters:
        return qs
    if 'aprobado' in filters and filters['aprobado'] is not None:
        qs = qs.filter(aprobado=filters['aprobado'])
    if 'nombre' in filters and filters['nombre']:
        qs = qs.filter(nombre__icontains=filters['nombre'])
    return qs

def get_cliente(pk: Any) -> Optional[Cliente]:
    try:
        return Cliente.objects.get(pk=pk)
    except Cliente.DoesNotExist:
        return None

def approve_cliente(pk: Any) -> Tuple[bool, Optional[str]]:
    cliente = get_cliente(pk)
    if not cliente:
        return False, 'Cliente no encontrado.'
    if cliente.aprobado:
        return False, 'Cliente ya aprobado.'
    cliente.aprobado = True
    try:
        cliente.save()
        return True, None
    except IntegrityError:
        return False, 'Error al aprobar cliente.'

def set_bloqueo(pk: Any, bloqueado: bool = True) -> Tuple[bool, Optional[str]]:
    cliente = get_cliente(pk)
    if not cliente:
        return False, 'Cliente no encontrado.'
    cliente.bloqueado = bool(bloqueado)
    try:
        cliente.save()
        return True, None
    except IntegrityError:
        return False, 'Error al actualizar bloqueo del cliente.'

def update_cliente(pk: Any, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Actualiza campos del cliente: nombre, email, telefono, aprobado (si vienen en data).
    Retorna (True, None) o (False, mensaje_error).
    """
    cliente = get_cliente(pk)
    if not cliente:
        return False, 'Cliente no encontrado.'

    # Solo actualizar si las claves están en data
    if 'nombre' in data and data['nombre'] is not None:
        cliente.nombre = data['nombre'].strip()
    if 'email' in data:
        cliente.email = data['email'].strip() or None
    if 'telefono' in data:
        cliente.telefono = data['telefono'].strip() or None
    if 'aprobado' in data:
        cliente.aprobado = bool(data['aprobado'])

    try:
        cliente.save()
        return True, None
    except IntegrityError as e:
        # puede ser por unique constraint en nombre/email
        return False, 'Error al guardar cliente: posible valor duplicado.'
