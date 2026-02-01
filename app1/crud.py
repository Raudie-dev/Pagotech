import base64
import requests
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any
from django.conf import settings 
from django.db import IntegrityError
from django.contrib.auth.hashers import make_password
from django.template.loader import render_to_string
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import validate_email
from app2.models import ParametroFinanciero, CuotaConfig # Importante para los cálculos
from .models import LinkPago, Cliente

# Configuraciones de Payzen desde settings.py
PAYZEN_SHOP_ID = settings.PAYZEN_SHOP_ID
PAYZEN_REST_PASS = settings.PAYZEN_REST_PASS
PAYZEN_URL = settings.PAYZEN_URL
PAYZEN_CHECK_URL = settings.PAYZEN_CHECK_URL

def get_payzen_auth_header():
    auth_str = f"{PAYZEN_SHOP_ID}:{PAYZEN_REST_PASS}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return {
        "Authorization": f"Basic {encoded_auth}",
        "Content-Type": "application/json"
    }

def create_cliente(nombre: str, password: str, email: Optional[str]=None, telefono: Optional[str]=None) -> Tuple[Optional[Cliente], List[str]]:
    errors: List[str] = []
    
    nombre = (nombre or '').strip().upper() 
    email = (email or '').strip().lower() if email else None 
    
    if not nombre:
        errors.append('El nombre es obligatorio.')
    if not password:
        errors.append('La contraseña es obligatoria.')
    elif len(password) < 8:
        errors.append('La contraseña debe tener al menos 8 caracteres.')

    if email:
        try:
            validate_email(email)
        except ValidationError:
            errors.append('El formato del correo electrónico no es válido.')
        
        if Cliente.objects.filter(email=email).exists():
            errors.append('Este correo electrónico ya está registrado.')
    else:
        errors.append('El correo electrónico es obligatorio.')

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
        # Mantener consistencia de MAYÚSCULAS al actualizar
        # nombre = nombre.strip().upper()
        nombre = nombre.strip()
        if nombre != cliente.nombre and Cliente.objects.filter(nombre=nombre).exclude(pk=pk).exists():
            return ['El nombre ya está en uso por otro cliente.']
        cliente.nombre = nombre

    email = data.get('email')
    if email is not None:
        # Mantener consistencia de minúsculas al actualizar
        email = email.strip().lower() or None
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
    links = LinkPago.objects.filter(cliente_id=cliente_pk)
    total_links = links.count()
    total_payments = links.filter(pagado=True).count()
    pending_payments = total_links - total_payments
    return {
        'total_links': total_links,
        'total_payments': total_payments,
        'pending_payments': pending_payments
    }

def create_link(cliente_pk, monto_contado, cuotas=1, tipo_tarjeta='credito', descripcion=None):
    """
    Crea un link de pago trasladando el costo financiero al cliente final.
    Utiliza parámetros dinámicos de App2 (Débito vs Crédito).
    Garantiza que el Débito sea siempre en 1 pago para evitar errores de pasarela.
    """
    cliente = get_cliente(cliente_pk)
    if not cliente:
        return None, ['Cliente no encontrado.']

    # --- PASO 0: VALIDACIÓN DE SEGURIDAD PARA DÉBITO ---
    # Si es tarjeta de débito, forzamos el valor a 1 cuota sin importar lo que venga del frontend
    if tipo_tarjeta == 'debito':
        cuotas = 1

    # 1. Obtener Configuración Financiera Real desde la base de datos (App2)
    config = ParametroFinanciero.objects.first()
    if not config:
        # Fallback de emergencia si el admin no configuró nada
        config = ParametroFinanciero.objects.create(
            iva=21, iva_financiacion=10.5, 
            comision_pago_tech=4, arancel_plataforma=1.8,
            comision_pago_tech_debito=3.49, arancel_plataforma_debito=0.8
        )

    try:
        monto_original = Decimal(str(monto_contado))
        iva_gen_factor = (Decimal(str(config.iva)) / 100) + 1          # Ejemplo: 1.21
        iva_finan_factor = (Decimal(str(config.iva_financiacion)) / 100) + 1 # Ejemplo: 1.105

        # 2. Selección de Tasas dinámicas según el medio de pago
        if tipo_tarjeta == 'debito':
            # --- Lógica para DÉBITO ---
            pt_base = config.comision_pago_tech_debito
            arancel_base = config.arancel_plataforma_debito
            tasa_finan_iva = Decimal('0')  # Débito no tiene costo financiero
        else:
            # --- Lógica para CRÉDITO ---
            pt_base = config.comision_pago_tech
            arancel_base = config.arancel_plataforma
            
            # Tasa de Financiación (Si el plan está activo y son más de 1 pago)
            tasa_finan_iva = Decimal('0')
            if cuotas > 1:
                plan = CuotaConfig.objects.filter(numero_cuota=cuotas, activa=True).first()
                if not plan:
                    return None, [f'El plan de {cuotas} cuotas no está habilitado actualmente.']
                # Aplicamos IVA 10.5% a la tasa base de financiación
                tasa_finan_iva = Decimal(str(plan.tasa_base)) * iva_finan_factor

        # 3. Sumatoria de descuentos con IVA (Basado en el cálculo del Excel)
        desc_pt_iva = Decimal(str(pt_base)) * iva_gen_factor       # Comisión Pago Tech + IVA
        desc_aran_iva = Decimal(str(arancel_base)) * iva_gen_factor # Arancel Red + IVA
        
        # TOTAL DESCUENTOS PORCENTUALES TRASLADADOS
        total_desc_pct = desc_pt_iva + desc_aran_iva + tasa_finan_iva

        # 4. Cálculo del Coeficiente de Inflado
        divisor = 1 - (total_desc_pct / 100)
        if divisor <= 0:
            return None, ["Error crítico: La sumatoria de tasas supera el 100%. Verifique el Admin."]
        
        coeficiente = 1 / divisor
        
        # 5. MONTO FINAL (Monto Bruto a procesar por PayZen)
        monto_final_venta = (monto_original * coeficiente).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Desglose para auditoría interna
        commission_amount = (monto_final_venta * (total_desc_pct / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        receiver_amount = (monto_final_venta - commission_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    except Exception as e:
        return None, [f'Error en el cálculo financiero: {str(e)}']

    # 6. Preparación del JSON para PayZen
    # Convertimos a centavos (Integer)
    amount_in_cents = int(monto_final_venta * 100)
    order_id = f"PAY-{uuid.uuid4().hex[:10].upper()}" 

    payload = {
        "amount": amount_in_cents,
        "currency": "ARS",
        "orderId": order_id,
        "channelOptions": {"channelType": "URL"},
        "merchantComment": f"Vendedor: {cliente.nombre} | Red: {tipo_tarjeta.upper()} | Plan: {cuotas} pag."
    }

    # --- LÓGICA DE CUOTAS PARA LA REST API DE PAYZEN ---
    # Solo enviamos el objeto cardOptions si es CRÉDITO y tiene más de 1 cuota.
    # Esto evita el error "REST API option not enabled".
    if tipo_tarjeta == 'credito' and cuotas > 1:
        payload["transactionOptions"] = {
            "cardOptions": {
                "installmentNumber": int(cuotas)
            }
        }

    # 7. Ejecutar llamada a la API de PayZen
    try:
        # get_payzen_auth_header() es tu función que gestiona el Basic Auth de Lyra
        headers = get_payzen_auth_header()
        response = requests.post(settings.PAYZEN_URL, json=payload, headers=headers, timeout=20)
        res_data = response.json()

        if res_data.get("status") == "SUCCESS":
            # Extraemos la URL generada por PayZen
            payment_url = res_data["answer"]["paymentURL"]
            
            # Guardamos el objeto en la base de datos
            link_obj = LinkPago.objects.create(
                cliente=cliente,
                order_id=order_id,
                monto=monto_final_venta,          # El monto total que el cliente verá en PayZen
                cuotas=cuotas,                    # Cantidad de cuotas elegida (Débito siempre será 1)
                tipo_tarjeta=tipo_tarjeta,
                descripcion=descripcion or '',
                commission_percent=total_desc_pct, 
                commission_amount=commission_amount, # Pesos que el sistema retendrá
                receiver_amount=receiver_amount,     # El dinero limpio para el vendedor
                link=payment_url
            )
            return link_obj, []
        else:
            # Capturamos el error detallado de la pasarela Lyra/PayZen
            answer = res_data.get("answer", {})
            error_msg = answer.get("errorMessage", "Respuesta fallida del gateway.")
            return None, [f"Pasarela PayZen indica: {error_msg}"]
            
    except requests.exceptions.Timeout:
        return None, ["La pasarela de pago tardó demasiado en responder. Reintente."]
    except Exception as e:
        return None, [f"Falla crítica en la comunicación con PayZen: {str(e)}"]

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
    
import traceback # Importante para ver el error detallado

def verificar_estado_pago(link_id):
    try:
        link = LinkPago.objects.get(pk=link_id)
        
        # 1. Si ya sabemos que está pagado en nuestra DB, no molestamos a la API
        if link.pagado:
            return {'status': 'CAPTURED', 'pagado': True, 'anulado': False, 'cuotas': link.cuotas_elegidas}

        payload = {"orderId": link.order_id}
        response = requests.post(PAYZEN_CHECK_URL, json=payload, headers=get_payzen_auth_header())
        res_data = response.json()

        # --- MANEJO DEL ERROR PSP_010 (EL "HUEVO DE COLÓN") ---
        if res_data.get("status") == "ERROR":
            answer = res_data.get("answer", {})
            if answer.get("errorCode") == "PSP_010":
                # Esto significa: El link existe, pero el cliente aún no lo usó.
                # Lo tratamos como PENDIENTE.
                return {
                    'status': 'Esperando Pago...', 
                    'pagado': False, 
                    'anulado': False, 
                    'cuotas': link.cuotas,
                    'mensaje': 'Esperando que el cliente abra el link'
                }
            
            # Si es otro tipo de error de API
            return {'status': 'Error de Api', 'pagado': False, 'anulado': False, 'cuotas': 1}

        # --- CASO DE ÉXITO (Ya hay intentos de pago) ---
        if res_data.get("status") == "SUCCESS":
            answer = res_data.get("answer", {})
            transactions = answer.get("transactions", [])
            
            if not transactions:
                return {'status': 'PENDING', 'pagado': False, 'anulado': False, 'cuotas': link.cuotas}

            tx = transactions[0]
            status_payzen = tx.get("status") 
            detailed_status = tx.get("detailedStatus") 

            # Guardamos el estado detallado para tener más info
            link.status_detalle = detailed_status

            # A) Pago Exitoso
            if status_payzen == "PAID" or detailed_status in ["AUTHORISED", "CAPTURED"]:
                t_details = tx.get("transactionDetails", {})
                card_details = t_details.get("cardDetails", {})
                link.auth_code = tx.get("authorizationResult")
                link.nro_transaccion = tx.get("uuid")
                cuotas_api = card_details.get("installmentNumber")
                link.cuotas_elegidas = int(cuotas_api) if cuotas_api else 1
                link.pagado = True
                link.save()
                return {'status': detailed_status, 'pagado': True, 'anulado': False, 'cuotas': link.cuotas_elegidas}
            
            # B) Pago Fallido/Rechazado (UNPAID + REFUSED)
            # Si el status es UNPAID y el detalle es REFUSED, ya es un fallo definitivo
            if status_payzen == "UNPAID" or detailed_status in ["REFUSED", "CANCELLED", "ERROR", "EXPIRED"]:
                link.pagado = False
                link.save()
                return {'status': detailed_status, 'pagado': False, 'anulado': True, 'cuotas': link.cuotas_elegidas}
            
            # C) Otros estados (En proceso, etc.)
            return {'status': detailed_status, 'pagado': False, 'anulado': False, 'cuotas': link.cuotas_elegidas}

    except Exception as e:
        print(f"Error técnico en CRUD: {e}")
        
    return {'status': 'Error Tecnico', 'pagado': False, 'anulado': False, 'cuotas': 1}