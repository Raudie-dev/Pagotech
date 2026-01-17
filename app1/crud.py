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
        # MEJORA: Mantener consistencia de MAYÚSCULAS al actualizar
        nombre = nombre.strip().upper()
        if nombre != cliente.nombre and Cliente.objects.filter(nombre=nombre).exclude(pk=pk).exists():
            return ['El nombre ya está en uso por otro cliente.']
        cliente.nombre = nombre

    email = data.get('email')
    if email is not None:
        # MEJORA: Mantener consistencia de minúsculas al actualizar
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
    """
    cliente = get_cliente(cliente_pk)
    if not cliente:
        return None, ['Cliente no encontrado.']

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
            tasa_finan_iva = Decimal('0')  # Débito no financia
            cuotas = 1                     # Forzamos cuotas a 1 por seguridad
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
                # Aplicamos IVA 10.5% a la tasa base del banco (Payway)
                tasa_finan_iva = Decimal(str(plan.tasa_base)) * iva_finan_factor

        # 3. Sumatoria de descuentos con IVA (Columna Roja del Excel)
        desc_pt_iva = Decimal(str(pt_base)) * iva_gen_factor       # Comisión PT + IVA
        desc_aran_iva = Decimal(str(arancel_base)) * iva_gen_factor # Arancel Payway + IVA
        
        # TOTAL DESCUENTOS %
        total_desc_pct = desc_pt_iva + desc_aran_iva + tasa_finan_iva

        # 4. Cálculo del Coeficiente (Columna Amarilla)
        # Fórmula: 1 / (1 - (Total_Descuento_Porcentual / 100))
        divisor = 1 - (total_desc_pct / 100)
        if divisor <= 0:
            return None, ["Error crítico: La configuración de tasas supera el 100%. Verifique admin."]
        
        coeficiente = 1 / divisor
        
        # 5. MONTO FINAL (Precio de Venta al Público)
        monto_final_venta = (monto_original * coeficiente).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Auditoría interna: Calculamos el monto exacto de la retención
        commission_amount = (monto_final_venta * (total_desc_pct / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        receiver_amount = (monto_final_venta - commission_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    except Exception as e:
        return None, [f'Error en cálculo financiero: {str(e)}']

    # 6. Preparación del Pago en Cents para PayZen
    amount_in_cents = int(monto_final_venta * 100)
    order_id = f"PAY-{uuid.uuid4().hex[:10].upper()}" 

    payload = {
        "amount": amount_in_cents,
        "currency": "ARS",
        "orderId": order_id,
        "channelOptions": {"channelType": "URL"},
        "merchantComment": f"Vendedor: {cliente.nombre} | Plan: {cuotas} pagos | {descripcion or ''}"
    }

    # Configuración de Cuotas para PayZen (Solo Crédito > 1)
    if tipo_tarjeta == 'credito' and cuotas > 1:
        schedules = []
        monto_cuota_cents = amount_in_cents // cuotas
        resto_cents = amount_in_cents % cuotas
        for i in range(cuotas):
            valor = monto_cuota_cents + (resto_cents if i == 0 else 0)
            fecha = (datetime.now() + timedelta(days=30 * i)).strftime("%Y-%m-%dT23:59:59+00:00")
            schedules.append({"date": fecha, "amount": valor})
        payload["transactionOptions"] = {"installmentOptions": {"schedules": schedules}}

    # 7. Ejecutar llamada a API PayZen
    try:
        response = requests.post(settings.PAYZEN_URL, json=payload, headers=get_payzen_auth_header())
        res_data = response.json()

        if res_data.get("status") == "SUCCESS":
            payment_url = res_data["answer"]["paymentURL"]
            
            # Guardamos el link con la discriminación correcta de montos
            link_obj = LinkPago.objects.create(
                cliente=cliente,
                order_id=order_id,
                monto=monto_final_venta,    # El precio inflado para que al descontar le llegue el neto
                cuotas=cuotas,
                tipo_tarjeta=tipo_tarjeta,
                descripcion=descripcion or '',
                commission_percent=total_desc_pct, # % exacto trasladado
                commission_amount=commission_amount, # Pesos que PagoTech+Payway descuentan
                receiver_amount=receiver_amount,     # Debería coincidir con el monto_contado ingresado
                link=payment_url
            )
            return link_obj, []
        else:
            error_msg = res_data.get("answer", {}).get("errorMessage", "Error desconocido")
            return None, [f"Error de Pasarela: {error_msg}"]
            
    except Exception as e:
        return None, [f"Falla de comunicación con PayZen: {str(e)}"]

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

        payload = {"orderId": link.order_id}
        response = requests.post(PAYZEN_CHECK_URL, json=payload, headers=get_payzen_auth_header())
        res_data = response.json()

        if res_data.get("status") == "SUCCESS":
            answer = res_data.get("answer", {})
            transactions = answer.get("transactions", [])
            
            for tx in transactions:
                if tx.get("status") in ["AUTHORISED", "CAPTURED", "PAID"]:
                    # --- CAMBIO AQUÍ: Buscar en múltiples lugares del JSON ---
                    # 1. Intentar en la raíz de la transacción
                    cuotas_api = tx.get("installmentNumber")
                    
                    # 2. Intentar en paymentMethodDetails (Común en REST API)
                    if not cuotas_api:
                        card_details = tx.get("paymentMethodDetails", {}).get("card", {})
                        cuotas_api = card_details.get("installmentNumber")
                    
                    # 3. Intentar en los detalles del medio de pago
                    if not cuotas_api:
                        cuotas_api = tx.get("transactionDetails", {}).get("cardDetails", {}).get("installmentNumber")

                    link.cuotas_elegidas = int(cuotas_api) if cuotas_api else 1
                    link.pagado = True
                    link.save()
                    return True
    except Exception as e:
        print(f"Error en validación PayZen: {e}")
    return False