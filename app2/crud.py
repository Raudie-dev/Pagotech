from typing import Tuple, Optional, Any, Dict, List
from django.db import IntegrityError
from app1.models import Cliente
from django.db.models import Q

def list_pending_clientes() -> List[Cliente]:
    return list(Cliente.objects.filter(aprobado=False))

def list_clientes(filters: Optional[Dict[str, Any]] = None):
    qs = Cliente.objects.all()
    if not filters:
        return qs
    
    # Filtro de búsqueda general (Nombre, Email o Teléfono)
    q = filters.get('q')
    if q:
        qs = qs.filter(
            Q(nombre__icontains=q) | 
            Q(email__icontains=q) | 
            Q(telefono__icontains=q)
        )
    
    # Filtros de estado
    if 'aprobado' in filters:
        qs = qs.filter(aprobado=filters['aprobado'])
    if 'bloqueado' in filters:
        qs = qs.filter(bloqueado=filters['bloqueado'])
        
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

def delete_cliente(pk: Any) -> Tuple[bool, Optional[str]]:
    cliente = get_cliente(pk)
    if not cliente:
        return False, 'Cliente no encontrado.'
    cliente.delete()
    return True, None

def update_cliente(pk: Any, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    cliente = get_cliente(pk)
    if not cliente:
        return False, 'Cliente no encontrado.'
    
    # Actualizamos solo los campos que vengan en el diccionario data
    if 'nombre' in data: cliente.nombre = data['nombre']
    if 'email' in data: cliente.email = data['email']
    if 'telefono' in data: cliente.telefono = data['telefono']
    
    # También permitimos actualizar estados si se pasan
    if 'aprobado' in data: cliente.aprobado = data['aprobado']
    if 'bloqueado' in data: cliente.bloqueado = data['bloqueado']
    
    try:
        cliente.save()
        return True, None
    except Exception as e:
        return False, f'Error al actualizar: {str(e)}'