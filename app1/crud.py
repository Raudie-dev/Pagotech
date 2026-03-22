import base64
import requests
import uuid
import traceback
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any
from django.conf import settings
from django.db import IntegrityError
from django.contrib.auth.hashers import make_password
from django.template.loader import render_to_string
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import validate_email
from app2.models import ParametroFinanciero, CuotaConfig
from .models import LinkPago, Cliente
import logging

logger = logging.getLogger('app1')

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


# ==============================================================================
# CLIENTES
# ==============================================================================

def create_cliente(nombre: str, password: str, email: Optional[str] = None, telefono: Optional[str] = None) -> Tuple[Optional[Cliente], List[str]]:
    errors: List[str] = []

    nombre = (nombre or '').strip().upper()
    email = (email or '').strip().lower() if email else None

    logger.debug(f"create_cliente — nombre={nombre} email={email} telefono={telefono}")

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
            logger.warning(f"create_cliente — email ya registrado: {email}")
            errors.append('Este correo electrónico ya está registrado.')
    else:
        errors.append('El correo electrónico es obligatorio.')

    if errors:
        logger.warning(f"create_cliente — validación fallida — email={email} errores={errors}")
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
        logger.info(f"create_cliente — cliente creado OK — id={cliente.id} nombre={nombre} email={email}")
        return cliente, []
    except IntegrityError:
        logger.error(f"create_cliente — IntegrityError — email={email}")
        return None, ['Hubo un error de integridad. Es posible que el correo ya esté en uso.']
    except Exception as e:
        logger.exception(f"create_cliente — error inesperado — email={email}: {e}")
        return None, [f'Error inesperado: {str(e)}']


def get_cliente(pk: Any) -> Optional[Cliente]:
    try:
        cliente = Cliente.objects.get(pk=pk)
        logger.debug(f"get_cliente — encontrado id={pk} nombre={cliente.nombre}")
        return cliente
    except Cliente.DoesNotExist:
        logger.debug(f"get_cliente — no encontrado id={pk}")
        return None


def update_cliente(pk: Any, data: Dict[str, Any]) -> List[str]:
    logger.debug(f"update_cliente — id={pk} campos={[k for k, v in data.items() if v]}")

    cliente = get_cliente(pk)
    if not cliente:
        logger.warning(f"update_cliente — cliente no encontrado id={pk}")
        return ['Cliente no encontrado.']

    nombre = data.get('nombre')
    if nombre:
        nombre = nombre.strip()
        if nombre != cliente.nombre and Cliente.objects.filter(nombre=nombre).exclude(pk=pk).exists():
            logger.warning(f"update_cliente — nombre en uso: '{nombre}' — id={pk}")
            return ['El nombre ya está en uso por otro cliente.']
        cliente.nombre = nombre

    email = data.get('email')
    if email is not None:
        email = email.strip().lower() or None
        if email != cliente.email and email and Cliente.objects.filter(email=email).exclude(pk=pk).exists():
            logger.warning(f"update_cliente — email en uso: '{email}' — id={pk}")
            return ['El correo ya está en uso por otro cliente.']
        cliente.email = email

    telefono = data.get('telefono')
    if telefono is not None:
        cliente.telefono = telefono.strip() or None

    password = data.get('password')
    if password:
        cliente.password = make_password(password)
        logger.debug(f"update_cliente — contraseña actualizada — id={pk}")

    if 'aprobado' in data and data['aprobado'] is not None:
        cliente.aprobado = bool(data['aprobado'])

    try:
        cliente.save()
        logger.info(f"update_cliente — actualizado OK — id={pk} nombre={cliente.nombre} email={cliente.email}")
        return []
    except IntegrityError:
        logger.error(f"update_cliente — IntegrityError al guardar — id={pk}")
        return ['Error al actualizar el cliente.']


def delete_cliente(pk: Any) -> bool:
    cliente = get_cliente(pk)
    if not cliente:
        logger.warning(f"delete_cliente — cliente no encontrado id={pk}")
        return False
    cliente.delete()
    logger.info(f"delete_cliente — cliente eliminado id={pk} nombre={cliente.nombre}")
    return True


def list_clientes(filters: Optional[Dict[str, Any]] = None):
    qs = Cliente.objects.all()
    if not filters:
        logger.debug("list_clientes — sin filtros")
        return qs
    if 'aprobado' in filters and filters['aprobado'] is not None:
        qs = qs.filter(aprobado=filters['aprobado'])
    if 'nombre' in filters and filters['nombre']:
        qs = qs.filter(nombre__icontains=filters['nombre'])
    logger.debug(f"list_clientes — filtros={filters} resultados={qs.count()}")
    return qs


def get_dashboard_stats(cliente_pk: Any) -> Dict[str, Any]:
    links = LinkPago.objects.filter(cliente_id=cliente_pk)
    total_links = links.count()
    total_payments = links.filter(pagado=True).count()
    pending_payments = total_links - total_payments

    logger.debug(
        f"get_dashboard_stats — cliente={cliente_pk} "
        f"total={total_links} pagados={total_payments} pendientes={pending_payments}"
    )

    return {
        'total_links': total_links,
        'total_payments': total_payments,
        'pending_payments': pending_payments
    }


# ==============================================================================
# LINKS DE PAGO
# ==============================================================================

def create_link(cliente_pk, monto_contado, cuotas=1, tipo_tarjeta='credito', descripcion=None):
    """
    Modelo ABSORBE: el vendedor ingresa el precio que cobra al cliente.
    Payway descuenta sobre ese precio y el vendedor recibe el neto resultante.
    """
    logger.info(
        f"create_link — cliente={cliente_pk} monto_cobrado={monto_contado} "
        f"tipo={tipo_tarjeta} cuotas={cuotas} descripcion='{descripcion}'"
    )
    cliente = get_cliente(cliente_pk)
    if not cliente:
        logger.error(f"create_link — cliente no encontrado id={cliente_pk}")
        return None, ['Cliente no encontrado.']

    # Débito siempre 1 cuota
    if tipo_tarjeta == 'debito' and cuotas != 1:
        logger.debug(f"create_link — débito detectado, forzando cuotas a 1")
        cuotas = 1

    # 1. Configuración financiera
    config = ParametroFinanciero.objects.first()
    if not config:
        logger.warning("create_link — ParametroFinanciero no encontrado, creando fallback")
        config = ParametroFinanciero.objects.create(
            iva=21, iva_financiacion=10.5,
            comision_pago_tech=4, arancel_plataforma=1.8,
            comision_pago_tech_debito=3.49, arancel_plataforma_debito=0.8
        )

    try:
        # El monto ingresado ES lo que cobra al cliente (precio bruto)
        monto_cobrado = Decimal(str(monto_contado))

        if tipo_tarjeta == 'debito':
            # Débito: siempre usa config global, sin tasa de financiación
            iva_f   = Decimal(str(config.iva)) / 100
            pt_eff  = Decimal(str(config.comision_pago_tech_debito)) * (1 + iva_f)
            ar_eff  = Decimal(str(config.arancel_plataforma_debito)) * (1 + iva_f)
            tasa_eff = Decimal('0')
            logger.debug(
                f"create_link — DÉBITO: pt_eff={pt_eff:.4f}% "
                f"ar_eff={ar_eff:.4f}% tasa=0%"
            )
        else:
            # Crédito: leer plan con sus overrides
            if cuotas > 1:
                plan = CuotaConfig.objects.filter(numero_cuota=cuotas, activa=True).first()
                if not plan:
                    logger.error(f"create_link — plan de {cuotas} cuotas no encontrado o inactivo")
                    return None, [f'El plan de {cuotas} cuotas no está habilitado actualmente.']

                # Valores efectivos del plan (override o global)
                iva_val     = plan.iva_override              if plan.iva_override is not None              else config.iva
                iva_fin_val = plan.iva_financiacion_override if plan.iva_financiacion_override is not None else config.iva_financiacion
                com_val     = plan.com_credito_override      if plan.com_credito_override is not None      else config.comision_pago_tech
                ar_val      = plan.arancel_credito_override  if plan.arancel_credito_override is not None  else config.arancel_plataforma

                iva_f     = Decimal(str(iva_val))     / 100
                iva_fin_f = Decimal(str(iva_fin_val)) / 100

                # Cada toggle es independiente
                tasa_eff = Decimal(str(plan.tasa_base)) * (1 + iva_fin_f) if plan.tasa_aplica_iva_fin else Decimal(str(plan.tasa_base))
                pt_eff   = Decimal(str(com_val))        * (1 + iva_f)     if plan.comision_aplica_iva  else Decimal(str(com_val))
                ar_eff   = Decimal(str(ar_val))         * (1 + iva_f)     if plan.comision_aplica_iva  else Decimal(str(ar_val))

                logger.debug(
                    f"create_link — CRÉDITO {cuotas}c plan='{plan.nombre}' "
                    f"tasa_base={plan.tasa_base}% iva_factor={iva_f} "
                    
                    f"tasa_eff={tasa_eff:.4f}% pt_eff={pt_eff:.4f}% ar_eff={ar_eff:.4f}%"
                )
            else:
                # Crédito contado (1 cuota): sin tasa de financiación
                iva_f   = Decimal(str(config.iva)) / 100
                pt_eff  = Decimal(str(config.comision_pago_tech)) * (1 + iva_f)
                ar_eff  = Decimal(str(config.arancel_plataforma)) * (1 + iva_f)
                tasa_eff = Decimal('0')
                logger.debug(
                    f"create_link — CRÉDITO contado: pt_eff={pt_eff:.4f}% ar_eff={ar_eff:.4f}%"
                )

        # 2. Total de descuentos y validación
        total_desc_pct = tasa_eff + pt_eff + ar_eff
        logger.debug(
            f"create_link — total_desc={total_desc_pct:.4f}% "
            f"(tasa={tasa_eff:.4f}% + pt={pt_eff:.4f}% + ar={ar_eff:.4f}%)"
        )

        if total_desc_pct >= 100:
            logger.error(f"create_link — tasas superan el 100%: {total_desc_pct}%")
            return None, ["Error crítico: La sumatoria de tasas supera el 100%. Verifique la configuración."]

        # 3. Cálculo modelo ABSORBE
        # El vendedor cobra monto_cobrado al cliente
        # Payway descuenta el porcentaje y le liquida el neto
        commission_amount = (monto_cobrado * (total_desc_pct / 100)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        receiver_amount = (monto_cobrado - commission_amount).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        logger.debug(
            f"create_link — ABSORBE: cobrado={monto_cobrado} "
            f"descuento={commission_amount} neto_vendedor={receiver_amount}"
        )
        
        # ── Desglose proporcional para guardar en DB ───────────────────
        tasa_pct_val = tasa_eff
        com_pct_val  = pt_eff
        ar_pct_val   = ar_eff

        if total_desc_pct > 0:
            d_ar   = (commission_amount * (ar_pct_val   / total_desc_pct)).quantize(Decimal('0.01'), ROUND_HALF_UP)
            d_tasa = (commission_amount * (tasa_pct_val / total_desc_pct)).quantize(Decimal('0.01'), ROUND_HALF_UP)
            d_com  = commission_amount - d_ar - d_tasa
        else:
            d_ar   = Decimal('0.00')
            d_tasa = Decimal('0.00')
            d_com  = commission_amount

        # IVA desglosado
        d_iva_21  = Decimal('0.00')
        d_iva_105 = Decimal('0.00')

        if tipo_tarjeta == 'debito':
            # Débito siempre IVA 21% sobre todo
            base_sin_iva = commission_amount / (1 + Decimal(str(config.iva)) / 100)
            d_iva_21 = (commission_amount - base_sin_iva).quantize(Decimal('0.01'), ROUND_HALF_UP)

        elif cuotas > 1 and plan:
            iva_fin_val = plan.iva_financiacion_override if plan.iva_financiacion_override is not None else config.iva_financiacion
            iva_fin_f_local = Decimal(str(iva_fin_val)) / 100

            if plan.comision_aplica_iva and (d_ar + d_com) > 0:
                base_com_ar = (d_ar + d_com) / (1 + iva_f)
                d_iva_21 = (d_ar + d_com - base_com_ar).quantize(Decimal('0.01'), ROUND_HALF_UP)

            if plan.tasa_aplica_iva_fin and d_tasa > 0:
                base_tasa = d_tasa / (1 + iva_fin_f_local)
                d_iva_105 = (d_tasa - base_tasa).quantize(Decimal('0.01'), ROUND_HALF_UP)
        else:
            # Crédito contado 1 cuota
            if (d_ar + d_com) > 0:
                base_sin_iva = (d_ar + d_com) / (1 + iva_f)
                d_iva_21 = (d_ar + d_com - base_sin_iva).quantize(Decimal('0.01'), ROUND_HALF_UP)

        d_cuota_valor = (monto_cobrado / cuotas).quantize(Decimal('0.01'), ROUND_HALF_UP)

        logger.debug(
            f"create_link — desglose: ar={d_ar} com={d_com} tasa={d_tasa} "
            f"iva_21={d_iva_21} iva_105={d_iva_105}"
        )

    except Exception as e:
        logger.exception(f"create_link — error en cálculo financiero — cliente={cliente_pk}: {e}")
        return None, [f'Error en el cálculo financiero: {str(e)}']

    # 4. Payload PayZen — el amount es lo que paga el cliente
    amount_in_cents = int(monto_cobrado * 100)
    order_id = f"PAY-{uuid.uuid4().hex[:10].upper()}"

    payload = {
        "amount": amount_in_cents,
        "currency": "ARS",
        "orderId": order_id,
        "channelOptions": {"channelType": "URL"},
        "merchantComment": (
            f"Vendedor: {cliente.nombre} | "
            f"Red: {tipo_tarjeta.upper()} | "
            f"Plan: {cuotas} pag."
        )
    }

    if tipo_tarjeta == 'credito':
        payload["transactionOptions"] = {
            "cardOptions": {
                "installmentNumber": int(cuotas),
                "installmentOptionsEditability": "FORBIDDEN"
            }
        }

    logger.debug(
        f"create_link — payload PayZen: order_id={order_id} "
        f"amount={amount_in_cents} cents ({monto_cobrado} ARS)"
    )

    # 5. Llamada a PayZen
    try:
        headers = get_payzen_auth_header()
        response = requests.post(settings.PAYZEN_URL, json=payload, headers=headers, timeout=20)
        res_data = response.json()
        logger.debug(
            f"create_link — respuesta PayZen status={res_data.get('status')} "
            f"order_id={order_id}"
        )

        if res_data.get("status") == "SUCCESS":
            payment_url = res_data["answer"]["paymentURL"]
            link_obj = LinkPago.objects.create(
                cliente=cliente,
                order_id=order_id,
                monto=monto_cobrado,          # lo que paga el cliente
                cuotas=cuotas,
                tipo_tarjeta=tipo_tarjeta,
                descripcion=descripcion or '',
                commission_percent=total_desc_pct,
                commission_amount=commission_amount,
                receiver_amount=receiver_amount,  # lo que recibe el vendedor
                link=payment_url,
                desglose_arancel=d_ar,
                desglose_comision=d_com,
                desglose_tasa=d_tasa,
                desglose_iva_21=d_iva_21,
                desglose_iva_105=d_iva_105,
                desglose_cuota_valor=d_cuota_valor
            )
            logger.info(
                f"create_link — link creado OK — id={link_obj.id} order_id={order_id} "
                f"cliente={cliente.nombre} cobrado={monto_cobrado} "
                f"descuento={commission_amount} neto={receiver_amount} "
                f"tipo={tipo_tarjeta} cuotas={cuotas}"
            )
            return link_obj, []

        else:
            answer    = res_data.get("answer", {})
            error_msg = answer.get("errorMessage", "Respuesta fallida del gateway.")
            logger.error(
                f"create_link — PayZen rechazó — order_id={order_id} "
                f"error='{error_msg}'"
            )
            return None, [f"Pasarela PayZen indica: {error_msg}"]

    except requests.exceptions.Timeout:
        logger.error(f"create_link — Timeout con PayZen — order_id={order_id}")
        return None, ["La pasarela de pago tardó demasiado. Reintente."]
    except Exception as e:
        logger.exception(f"create_link — falla crítica con PayZen — order_id={order_id}: {e}")
        return None, [f"Falla crítica con PayZen: {str(e)}"]

def list_links_for_cliente(cliente_pk: Any):
    qs = LinkPago.objects.filter(cliente_id=cliente_pk).order_by('-created_at')
    logger.debug(f"list_links_for_cliente — cliente={cliente_pk} total={qs.count()}")
    return qs


def get_invoice_for_link(link_id: Any, cliente_pk: Any) -> Tuple[Optional[str], Optional[str], List[str]]:
    logger.debug(f"get_invoice_for_link — link_id={link_id} cliente={cliente_pk}")
    try:
        link = LinkPago.objects.get(pk=link_id, cliente_id=cliente_pk)
        if not link.invoice_text:
            logger.debug(f"get_invoice_for_link — generando invoice_text para link_id={link_id}")
            link.generate_invoice_text()
            link.save()
        logger.info(f"get_invoice_for_link — invoice OK — link_id={link_id}")
        return f"ticket_link_{link.id}.txt", link.invoice_text, []
    except ObjectDoesNotExist:
        logger.warning(f"get_invoice_for_link — link no encontrado — link_id={link_id} cliente={cliente_pk}")
        return None, None, ['Link no encontrado.']


def generate_pdf_for_link(link_id: Any, cliente_pk: Any) -> Tuple[Optional[str], Optional[bytes], List[str]]:
    logger.debug(f"generate_pdf_for_link — link_id={link_id} cliente={cliente_pk}")
    try:
        link = LinkPago.objects.get(pk=link_id, cliente_id=cliente_pk)
        if not link.invoice_text:
            logger.debug(f"generate_pdf_for_link — generando invoice_text para link_id={link_id}")
            link.generate_invoice_text()
            link.save()
        context = {'link': link, 'cliente': link.cliente}
        html = render_to_string('ticket_pdf.html', context)
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()
        logger.info(f"generate_pdf_for_link — PDF generado OK — link_id={link_id}")
        return f"ticket_link_{link.id}.pdf", pdf_bytes, []
    except Exception as e:
        logger.exception(f"generate_pdf_for_link — error — link_id={link_id}: {e}")
        return None, None, [f'Error: {e}']


# ==============================================================================
# VERIFICACIÓN DE PAGOS (PayZen)
# ==============================================================================

def verificar_estado_pago(link_id):
    logger.debug(f"verificar_estado_pago — link_id={link_id}")

    try:
        link = LinkPago.objects.get(pk=link_id)

        # 1. Si ya está pagado en DB, no consultamos la API
        if link.pagado:
            logger.debug(f"verificar_estado_pago — ya pagado en DB, omitiendo API — link_id={link_id} order_id={link.order_id}")
            return {'status': 'CAPTURED', 'pagado': True, 'anulado': False, 'cuotas': link.cuotas_elegidas}

        logger.debug(f"verificar_estado_pago — consultando PayZen — order_id={link.order_id}")

        payload = {"orderId": link.order_id}
        response = requests.post(PAYZEN_CHECK_URL, json=payload, headers=get_payzen_auth_header())
        res_data = response.json()

        payzen_status = res_data.get("status")
        logger.debug(f"verificar_estado_pago — respuesta PayZen status={payzen_status} order_id={link.order_id}")

        # --- ERROR PSP_010: orden sin actividad aún ---
        if payzen_status == "ERROR":
            answer = res_data.get("answer", {})
            error_code = answer.get("errorCode")

            if error_code == "PSP_010":
                logger.debug(f"verificar_estado_pago — PSP_010: link aún no abierto por el cliente — order_id={link.order_id}")
                return {
                    'status': 'Esperando Pago...',
                    'pagado': False,
                    'anulado': False,
                    'cuotas': link.cuotas,
                    'mensaje': 'Esperando que el cliente abra el link'
                }

            logger.warning(
                f"verificar_estado_pago — error PayZen desconocido — "
                f"order_id={link.order_id} errorCode={error_code} answer={answer}"
            )
            return {'status': 'Error de Api', 'pagado': False, 'anulado': False, 'cuotas': 1}

        # --- SUCCESS: hay actividad de transacciones ---
        if payzen_status == "SUCCESS":
            answer = res_data.get("answer", {})
            transactions = answer.get("transactions", [])

            if not transactions:
                logger.debug(f"verificar_estado_pago — SUCCESS pero sin transacciones — order_id={link.order_id}")
                return {'status': 'PENDING', 'pagado': False, 'anulado': False, 'cuotas': link.cuotas}

            tx = transactions[0]
            status_payzen = tx.get("status")
            detailed_status = tx.get("detailedStatus")

            logger.debug(
                f"verificar_estado_pago — transacción encontrada — order_id={link.order_id} "
                f"status={status_payzen} detailed={detailed_status}"
            )

            link.status_detalle = detailed_status

            # A) Pago exitoso
            if status_payzen == "PAID" or detailed_status in ["AUTHORISED", "CAPTURED"]:
                t_details = tx.get("transactionDetails", {})
                card_details = t_details.get("cardDetails", {})
                auth_response = card_details.get("authorizationResponse", {})

                link.nro_transaccion = tx.get("uuid")
                link.auth_code = (
                    auth_response.get("authorizationNumber")
                    or tx.get("uuid", "")[:8].upper()
                )
                link.lote_number = (
                    t_details.get("sequenceNumber")
                    or t_details.get("batchNumber")
                    or "001"
                )
                cuotas_api = card_details.get("installmentNumber")
                link.cuotas_elegidas = int(cuotas_api) if cuotas_api else 1
                link.pagado = True
                link.save()

                logger.info(
                    f"verificar_estado_pago — PAGO EXITOSO — order_id={link.order_id} "
                    f"auth_code={link.auth_code} lote={link.lote_number} "
                    f"cuotas={link.cuotas_elegidas} nro_tx={link.nro_transaccion}"
                )

                return {
                    'status': detailed_status,
                    'pagado': True,
                    'anulado': False,
                    'cuotas': link.cuotas_elegidas
                }

            # B) Pago rechazado / cancelado
            if status_payzen == "UNPAID" or detailed_status in ["REFUSED", "CANCELLED", "ERROR", "EXPIRED"]:
                link.pagado = False
                link.save()
                logger.warning(
                    f"verificar_estado_pago — PAGO FALLIDO — order_id={link.order_id} "
                    f"detailed_status={detailed_status}"
                )
                return {
                    'status': detailed_status,
                    'pagado': False,
                    'anulado': True,
                    'cuotas': link.cuotas_elegidas
                }

            # C) Estado intermedio (en proceso)
            logger.debug(
                f"verificar_estado_pago — estado intermedio — order_id={link.order_id} "
                f"detailed_status={detailed_status}"
            )
            return {
                'status': detailed_status,
                'pagado': False,
                'anulado': False,
                'cuotas': link.cuotas_elegidas
            }

    except Exception as e:
        logger.exception(f"verificar_estado_pago — error técnico — link_id={link_id}: {e}")

    return {'status': 'Error Tecnico', 'pagado': False, 'anulado': False, 'cuotas': 1}