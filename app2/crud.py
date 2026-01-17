from typing import Tuple, Optional, Any, Dict, List
from django.db import IntegrityError
from app1.models import Cliente
from django.db.models import Q
from django.contrib.auth.hashers import make_password
from .models import User_admin
from .models import ParametroFinanciero, CuotaConfig

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
    
    if 'nombre' in data: cliente.nombre = data['nombre']
    if 'email' in data: cliente.email = data['email']
    if 'telefono' in data: cliente.telefono = data['telefono']
    
    # NUEVA LÓGICA PARA LA CONTRASEÑA
    if 'password' in data and data['password']: # Si la contraseña viene en el dict y no está vacía
        cliente.password = make_password(data['password'])
    
    if 'aprobado' in data: cliente.aprobado = data['aprobado']
    if 'bloqueado' in data: cliente.bloqueado = data['bloqueado']
    
    try:
        cliente.save()
        return True, None
    except Exception as e:
        return False, f'Error al actualizar: {str(e)}'
    
def list_admins(filters: Optional[Dict[str, Any]] = None):
    qs = User_admin.objects.all()
    if filters and filters.get('q'):
        q = filters.get('q')
        qs = qs.filter(Q(nombre__icontains=q))
    return qs

def create_admin(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    try:
        # Verificar si el nombre ya existe
        if User_admin.objects.filter(nombre=data['nombre']).exists():
            return False, 'El nombre de administrador ya existe.'
        
        nuevo_admin = User_admin(
            nombre=data['nombre'],
            password=make_password(data['password']),
            bloqueado=False
        )
        nuevo_admin.save()
        return True, None
    except Exception as e:
        return False, f'Error al crear: {str(e)}'

def update_admin(pk: Any, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    try:
        admin = User_admin.objects.get(pk=pk)
        if 'nombre' in data: admin.nombre = data['nombre']
        
        if 'password' in data and data['password']:
            admin.password = make_password(data['password'])
            
        if 'bloqueado' in data: 
            admin.bloqueado = data['bloqueado']
            
        admin.save()
        return True, None
    except User_admin.DoesNotExist:
        return False, 'Administrador no encontrado.'
    except Exception as e:
        return False, f'Error: {str(e)}'

def delete_admin(pk: Any) -> Tuple[bool, Optional[str]]:
    try:
        admin = User_admin.objects.get(pk=pk)
        admin.delete()
        return True, None
    except:
        return False, 'Error al eliminar.'
    
    from .models import ParametroFinanciero, CuotaConfig

def get_or_create_config():
    config = ParametroFinanciero.objects.first()
    if not config:
        config = ParametroFinanciero.objects.create()
    return config

def list_cuotas_config():
    return CuotaConfig.objects.all()

def update_financiero(data):
    config = get_or_create_config()
    config.iva = data.get('iva', config.iva)
    config.iva_financiacion = data.get('iva_financiacion', config.iva_financiacion)
    
    # Valores Crédito
    config.comision_pago_tech = data.get('comision_pago_tech', config.comision_pago_tech)
    config.arancel_plataforma = data.get('arancel_plataforma', config.arancel_plataforma)
    
    # Valores Débito
    config.comision_pago_tech_debito = data.get('comision_pago_tech_debito', config.comision_pago_tech_debito)
    config.arancel_plataforma_debito = data.get('arancel_plataforma_debito', config.arancel_plataforma_debito)
    
    config.save()
    return True, None

def update_cuota_tasa(cuota_id, tasa, activa):
    try:
        cuota = CuotaConfig.objects.get(id=cuota_id)
        cuota.tasa_base = tasa
        cuota.activa = (activa == 'on' or activa == True)
        cuota.save()
        return True, None
    except Exception as e:
        return False, str(e)
    
def create_cuota_plan(data):
    try:
        nueva = CuotaConfig.objects.create(
            numero_cuota=data['numero_cuota'],
            nombre=data['nombre'],
            tasa_base=data['tasa_base'],
            activa=True
        )
        return True, None
    except Exception as e:
        return False, str(e)

def update_cuota_plan(cuota_id, data):
    try:
        cuota = CuotaConfig.objects.get(id=cuota_id)
        cuota.nombre = data.get('nombre', cuota.nombre)
        cuota.numero_cuota = data.get('numero_cuota', cuota.numero_cuota)
        cuota.tasa_base = data.get('tasa_base', cuota.tasa_base)
        cuota.activa = data.get('activa') == 'on'
        cuota.save()
        return True, None
    except Exception as e:
        return False, str(e)

def delete_cuota_plan(cuota_id):
    try:
        CuotaConfig.objects.get(id=cuota_id).delete()
        return True, None
    except:
        return False, "Error al eliminar el plan."