from typing import Optional, Tuple, List, Dict, Any
from django.db import IntegrityError
from django.contrib.auth.hashers import make_password
from decimal import Decimal, InvalidOperation
import uuid
from django.template.loader import render_to_string
from django.core.exceptions import ObjectDoesNotExist
from .models import Cliente, LinkPago
import base64
import requests
from datetime import datetime, timedelta
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

# Configuración PayZen (Cámbialos por tus datos reales de back-office)
PAYZEN_SHOP_ID = "17684447"
PAYZEN_REST_PASS = "testpassword_CnrSZ0lrDIoW0e9felr9dauGFvoYdxH5gaOurRkXDAtkf"
PAYZEN_URL = "https://api.payzen.lat/api-payment/V4/Charge/CreatePaymentOrder"

def get_payzen_auth_header():
    # El usuario es el Shop ID y la contraseña es el REST API Password
    auth_str = f"{PAYZEN_SHOP_ID}:{PAYZEN_REST_PASS}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return {
        "Authorization": f"Basic {encoded_auth}",
        "Content-Type": "application/json"
    }

def create_cliente(nombre: str, password: str, email: Optional[str]=None, telefono: Optional[str]=None) -> Tuple[Optional[Cliente], List[str]]:
    errors: List[str] = []
    
    # 1. Normalización y Limpieza
    nombre = (nombre or '').strip().upper() # Guardar siempre en MAYÚSCULAS
    email = (email or '').strip().lower() if email else None # Guardar siempre en minúsculas
    
    # 2. Validaciones básicas
    if not nombre:
        errors.append('El nombre es obligatorio.')
    if not password:
        errors.append('La contraseña es obligatoria.')
    elif len(password) < 8:
        errors.append('La contraseña debe tener al menos 8 caracteres.')

    # 3. Validación de Formato de Email (Real)
    if email:
        try:
            validate_email(email)
        except ValidationError:
            errors.append('El formato del correo electrónico no es válido (ejemplo@dominio.com).')
        
        # Verificar si el email ya existe (esto sí debe ser único)
        if Cliente.objects.filter(email=email).exists():
            errors.append('Este correo electrónico ya está registrado.')
    else:
        errors.append('El correo electrónico es obligatorio para crear la cuenta.')

    if errors:
        return None, errors

    try:
        cliente = Cliente(
            nombre=nombre,
            password=make_password(password),
            email=email,
            telefono=telefono or None,
            aprobado=False,
        )
        cliente.save()
        return cliente, []
    except IntegrityError:
        return None, ['Hubo un error de integridad. Es posible que el correo ya esté en uso.']
    except Exception as e:
        return None, [f'Error inesperado: {str(e)}']

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

def get_dashboard_stats(cliente_pk: Any) -> Dict[str, Any]:
    """Obtiene las estadísticas para el dashboard basado en los links del cliente."""
    links = LinkPago.objects.filter(cliente_id=cliente_pk)
    total_links = links.count()
    # Si no tienes campo 'pagado', ambos serán 0 o calculados
    total_payments = links.filter(pagado=True).count() if hasattr(LinkPago, 'pagado') else 0
    pending_payments = total_links - total_payments
    return {
        'total_links': total_links,
        'total_payments': total_payments,
        'pending_payments': pending_payments
    }

def create_link(cliente_pk, monto, cuotas=1, tipo_tarjeta='credito', descripcion=None):
    errors = []
    cliente = get_cliente(cliente_pk)
    if not cliente:
        return None, ['Cliente no encontrado.']

    try:
        monto_dec = Decimal(str(monto))
    except:
        return None, ['Monto inválido.']

    # Comisiones internas de tu app
    tipo = tipo_tarjeta if tipo_tarjeta in ('debito', 'credito') else 'credito'
    perc_map = {'debito': Decimal('3.49'), 'credito': Decimal('3.99')}
    perc = perc_map[tipo]
    commission_amount = (monto_dec * perc / Decimal('100')).quantize(Decimal('0.01'))
    receiver_amount = (monto_dec - commission_amount).quantize(Decimal('0.01'))

    # Preparar el envío a PayZen (Monto en centavos como entero)
    amount_in_cents = int(monto_dec * 100)
    order_id = f"PAY-{uuid.uuid4().hex[:10].upper()}" 

    payload = {
        "amount": amount_in_cents,
        "currency": "ARS",  # Peso Argentino
        "orderId": order_id,
        "channelOptions": {
            "channelType": "URL"
        },
        "merchantComment": f"Cliente: {cliente.nombre} - {descripcion or ''}"
    }

    # Manejo de cuotas (Solo si es mayor a 1)
    if cuotas > 1:
        schedules = []
        monto_cuota = amount_in_cents // cuotas
        resto = amount_in_cents % cuotas
        
        for i in range(cuotas):
            valor = monto_cuota + (resto if i == 0 else 0)
            # Fecha de cobro: cada 30 días
            fecha = (datetime.now() + timedelta(days=30 * i)).strftime("%Y-%m-%dT23:59:59+00:00")
            schedules.append({
                "date": fecha,
                "amount": valor
            })
        
        payload["transactionOptions"] = {
            "installmentOptions": {
                "schedules": schedules
            }
        }

    try:
        response = requests.post(PAYZEN_URL, json=payload, headers=get_payzen_auth_header())
        res_data = response.json()

        if res_data.get("status") == "SUCCESS":
            payment_url = res_data["answer"]["paymentURL"]
            
            # Guardamos en tu base de datos local
            link_obj = LinkPago.objects.create(
                cliente=cliente,
                order_id=order_id,
                monto=monto_dec,
                cuotas=cuotas,
                tipo_tarjeta=tipo,
                descripcion=descripcion or '',
                commission_percent=perc,
                commission_amount=commission_amount,
                receiver_amount=receiver_amount,
                link=payment_url  # Aquí guardamos la URL de PayZen
            )
            return link_obj, []
        else:
            # Captura de errores específicos de PayZen
            error_detail = res_data.get("answer", {}).get("errorMessage", "Error desconocido")
            return None, [f"Error de Pasarela: {error_detail}"]

    except Exception as e:
        return None, [f"Error de conexión: {str(e)}"]

def list_links_for_cliente(cliente_pk: Any):
    return LinkPago.objects.filter(cliente_id=cliente_pk).order_by('-created_at')

def get_invoice_for_link(link_id: Any, cliente_pk: Any) -> Tuple[Optional[str], Optional[str], List[str]]:
    try:
        link = LinkPago.objects.get(pk=link_id, cliente_id=cliente_pk)
        if not link.invoice_text:
            link.generate_invoice_text()
            link.save()
        return f"ticket_link_{link.id}.txt", link.invoice_text, []
    except ObjectDoesNotExist:
        return None, None, ['Link no encontrado.']

def generate_pdf_for_link(link_id: Any, cliente_pk: Any) -> Tuple[Optional[str], Optional[bytes], List[str]]:
    try:
        link = LinkPago.objects.get(pk=link_id, cliente_id=cliente_pk)
        if not link.invoice_text:
            link.generate_invoice_text()
            link.save()
        context = {'link': link, 'cliente': link.cliente}
        html = render_to_string('ticket_pdf.html', context)
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()
        return f"ticket_link_{link.id}.pdf", pdf_bytes, []
    except Exception as e:
        return None, None, [f'Error: {e}']
    
def verificar_estado_pago(link_id):
    try:
        link = LinkPago.objects.get(pk=link_id)
        if not link.order_id: return False
        if link.pagado: return True

        CHECK_URL = "https://api.payzen.lat/api-payment/V4/Order/Get"
        payload = {"orderId": link.order_id}
        
        response = requests.post(CHECK_URL, json=payload, headers=get_payzen_auth_header())
        res_data = response.json()

        if res_data.get("status") == "SUCCESS":
            answer = res_data.get("answer", {})
            transactions = answer.get("transactions", [])
            
            for tx in transactions:
                if tx.get("status") in ["AUTHORISED", "CAPTURED", "PAID"]:
                    # --- CAPTURA AVANZADA DE CUOTAS ---
                    # Intentamos obtener installmentNumber de la transacción
                    cuotas_api = tx.get("installmentNumber")
                    
                    # Debug para ver en tu consola de Python qué responde PayZen
                    """  
                    print(f"--- DEBUG PAYZEN LINK {link_id} ---")
                    print(f"Status: {tx.get('status')}")
                    print(f"Cuotas recibidas de API: {cuotas_api}")
                    """
                    
                    # Si la API devuelve None o 0, ponemos 1 por defecto
                    link.cuotas_elegidas = int(cuotas_api) if cuotas_api else 1
                    link.pagado = True
                    link.save()
                    return True
                    
    except Exception as e:
        print(f"Error en validación: {e}")
    return False