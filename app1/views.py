from django.shortcuts import render, redirect
from django.urls import reverse
import django.contrib.messages as messages
from django.contrib.auth.hashers import check_password  
from .models import Cliente, LinkPago
from . import crud
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.http import HttpResponse, Http404, JsonResponse
from django.core.paginator import Paginator
from django.template.loader import get_template
from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import HTML
import tempfile
from app2.models import ParametroFinanciero, CuotaConfig
import os
import logging
from app2 import crud as app2_crud
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from utils.email_utils import mail
from django.urls import reverse
from django.utils import timezone
import re
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

logger = logging.getLogger('app1')


def index(request):
    logger.debug("Vista index cargada")
    return render(request, 'index.html')


def register(request):
    if request.method == 'POST':
        # --- 1. OBTENER Y SANITIZAR DATOS ---
        nombre_raw = request.POST.get('nombre', '').strip()
        # Eliminar espacios múltiples y capitalizar cada palabra
        nombre = re.sub(r'\s+', ' ', nombre_raw).title()
        
        email_raw = request.POST.get('email', '').strip()
        email = email_raw.lower()
        
        telefono_raw = request.POST.get('telefono', '').strip()
        telefono = re.sub(r'\s+', '', telefono_raw) if telefono_raw else ''
        
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        logger.debug(f"Intento de registro — email={email} nombre={nombre}")

        # --- 2. VALIDACIONES ---
        errors = []

        # Nombre
        if not nombre:
            errors.append('El nombre completo es obligatorio.')
        elif len(nombre) < 3:
            errors.append('El nombre debe tener al menos 3 caracteres.')
        elif len(nombre) > 100:
            errors.append('El nombre no puede exceder 100 caracteres.')
        elif not re.match(r'^[a-zA-ZÀ-ÿ\s]+$', nombre):
            errors.append('El nombre solo puede contener letras y espacios.')

        # Email
        if not email:
            errors.append('El correo electrónico es obligatorio.')
        else:
            try:
                validate_email(email)
            except ValidationError:
                errors.append('Ingresa un correo electrónico válido.')

        # Teléfono (opcional pero con formato)
        if not telefono:
            errors.append('El teléfono es obligatorio.')
        elif not re.match(r'^\+?[0-9]{8,15}$', telefono):
            errors.append('Debe comenzar con + y solo números (8-15 dígitos).')

        # Contraseña
        if not password:
            errors.append('La contraseña es obligatoria.')
        else:
            if len(password) < 8:
                errors.append('La contraseña debe tener al menos 8 caracteres.')
            if not re.search(r'[A-Z]', password):
                errors.append('La contraseña debe contener al menos una mayúscula.')
            if not re.search(r'[!@#$%^&*()_\-+=\[\]{}|:;"\'<>,.?/~`]', password):
                errors.append('La contraseña debe contener al menos un símbolo.')

        # Confirmación de contraseña
        if password != password2:
            errors.append('Las contraseñas no coinciden.')

        # Si hay errores, mostrar y retornar
        if errors:
            logger.warning(f"Registro rechazado — email={email} — errores={errors}")
            for e in errors:
                messages.error(request, e)
            return render(request, 'register.html', {
                'data': request.POST,
                'errors': errors
            })

        # --- 3. CREAR CLIENTE (CRUD) ---
        cliente, creation_errors = crud.create_cliente(nombre, password, email, telefono)

        if creation_errors:
            logger.warning(f"Registro rechazado — email={email} — errores={creation_errors}")
            for e in creation_errors:
                messages.error(request, e)
            return render(request, 'register.html', {
                'data': request.POST,
                'errors': creation_errors
            })

        # --- 4. ENVIAR NOTIFICACIÓN POR CORREO ---
        try:
            admin_url = request.build_absolute_uri(reverse('aprobacion'))
            
            logger.info(f"Intentando enviar correo de notificación para {email}")
            
            # Usar EMAIL_RECEPTORES (lista) o EMAIL_RECEPTOR (string) según tu settings
            destinatarios = getattr(settings, 'EMAIL_RECEPTORES', None)
            if not destinatarios:
                destinatarios = [getattr(settings, 'EMAIL_RECEPTOR', 'pagotechnotificaciones@gmail.com')]
            
            resultado = mail(
                asunto="Nuevo usuario registrado - Pendiente de aprobación",
                destinatarios=destinatarios,
                template_html="emails/notificacion_registro.html",
                contexto={
                    "nombre": nombre,
                    "email": email,
                    "telefono": telefono or "No especificado",
                    "fecha": timezone.now().strftime("%d/%m/%Y %H:%M"),
                    "admin_url": admin_url,
                },
            )
            
            if resultado:
                logger.info(f"Correo de notificación enviado correctamente para {email}")
            else:
                logger.warning(f"Falló el envío del correo de notificación para {email}")
                
        except Exception as e:
            logger.error(f"Error enviando correo de notificación para {email}: {e}")

        # --- 5. REDIRIGIR AL INDEX CON MENSAJE DE ÉXITO ---
        logger.info(f"Registro exitoso — email={email} nombre={nombre} id={cliente.id}")
        return redirect(f"{reverse('index')}?registered=1")

    # --- GET: mostrar formulario vacío ---
    logger.debug("GET register — formulario cargado")
    return render(request, 'register.html')

def login_cliente(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        logger.debug(f"Intento de login — email={email}")

        try:
            user = Cliente.objects.get(email__iexact=email)

            if user.bloqueado:
                logger.warning(f"Login bloqueado — email={email} id={user.id}")
                messages.error(request, 'Usuario bloqueado')

            elif not user.aprobado:
                logger.info(f"Login pendiente de aprobación — email={email} id={user.id}")
                messages.error(request, 'Cuenta pendiente de aprobación')

            elif check_password(password, user.password):
                logger.info(f"Login exitoso — email={email} id={user.id} nombre={user.nombre}")
                request.session['user_id'] = user.id
                messages.success(request, f"Bienvenido {user.nombre}")
                return redirect('dashboard')

            else:
                logger.warning(f"Login fallido — contraseña incorrecta — email={email} id={user.id}")
                messages.error(request, 'Contraseña incorrecta')

        except Cliente.DoesNotExist:
            logger.warning(f"Login fallido — correo no registrado — email={email}")
            messages.error(request, 'Correo no encontrado')

    return render(request, 'login.html')


def dashboard(request):
    user_id = request.session.get('user_id')
    if not user_id:
        logger.debug("Dashboard — sesión no encontrada, redirigiendo a login")
        return redirect('login_cliente')

    cliente = crud.get_cliente(user_id)
    if not cliente:
        logger.warning(f"Dashboard — cliente id={user_id} no encontrado en DB, redirigiendo")
        return redirect('login_cliente')

    stats = crud.get_dashboard_stats(user_id)
    logger.debug(
        f"Dashboard cargado — usuario={cliente.nombre} id={user_id} "
        f"links={stats['total_links']} pagados={stats['total_payments']} pendientes={stats['pending_payments']}"
    )

    context = {
        'user': cliente,
        'total_links': stats['total_links'],
        'total_payments': stats['total_payments'],
        'pending_payments': stats['pending_payments'],
    }
    return render(request, 'dashboard.html', context)


def creacion_link(request):
    user_id = request.session.get('user_id')
    if not user_id:
        logger.debug("Creación link — sesión no encontrada, redirigiendo a login")
        return redirect('login_cliente')

    cliente = crud.get_cliente(user_id)

    config = ParametroFinanciero.objects.first()
    if not config:
        logger.warning("Creación link — ParametroFinanciero no configurado, usando fallback")
        config = ParametroFinanciero.objects.create()

    planes_activos = app2_crud.list_cuotas_para_usuario(user_id)
    logger.debug(f"Creación link — usuario={cliente.nombre} id={user_id} planes_activos={planes_activos.count()}")

    if request.method == 'POST':

        # --- CASO A: AJAX Preview ---
        if 'preview' in request.POST:
            try:
                # Modelo ABSORBE: monto ingresado = lo que cobra al cliente
                monto_cobrado = Decimal(request.POST.get('monto', '0'))
                cuotas_num    = int(request.POST.get('cuotas', '1'))
                tipo          = request.POST.get('tipo_tarjeta', 'credito')

                if tipo == 'debito':
                    cuotas_num = 1
                    iva_f    = Decimal(str(config.iva)) / 100
                    pt_eff   = Decimal(str(config.comision_pago_tech_debito)) * (1 + iva_f)
                    ar_eff   = Decimal(str(config.arancel_plataforma_debito)) * (1 + iva_f)
                    tasa_eff = Decimal('0')
                else:
                    plan = app2_crud.list_cuotas_para_usuario(user_id).filter(numero_cuota=cuotas_num).first()
                    if plan and cuotas_num > 1:
                        iva_val     = plan.iva_override              if plan.iva_override is not None              else config.iva
                        iva_fin_val = plan.iva_financiacion_override if plan.iva_financiacion_override is not None else config.iva_financiacion
                        com_val     = plan.com_credito_override      if plan.com_credito_override is not None      else config.comision_pago_tech
                        ar_val      = plan.arancel_credito_override  if plan.arancel_credito_override is not None  else config.arancel_plataforma

                        iva_f     = Decimal(str(iva_val))     / 100
                        iva_fin_f = Decimal(str(iva_fin_val)) / 100

                        tasa_eff = Decimal(str(plan.tasa_base)) * (1 + iva_fin_f) if plan.tasa_aplica_iva_fin else Decimal(str(plan.tasa_base))
                        pt_eff   = Decimal(str(com_val))        * (1 + iva_f)     if plan.comision_aplica_iva  else Decimal(str(com_val))
                        ar_eff   = Decimal(str(ar_val))         * (1 + iva_f)     if plan.comision_aplica_iva  else Decimal(str(ar_val))
                    else:
                        # Contado o fallback global
                        iva_f    = Decimal(str(config.iva)) / 100
                        pt_eff   = Decimal(str(config.comision_pago_tech)) * (1 + iva_f)
                        ar_eff   = Decimal(str(config.arancel_plataforma)) * (1 + iva_f)
                        tasa_eff = Decimal('0')

                total_desc    = tasa_eff + pt_eff + ar_eff
                descuento_pesos = (monto_cobrado * (total_desc / 100)).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                neto_vendedor = (monto_cobrado - descuento_pesos).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )

                return JsonResponse({
                    'success':     True,
                    'monto_venta': float(monto_cobrado),    # lo que paga el cliente
                    'comision':    float(descuento_pesos),  # descuento Payway
                    'neto':        float(neto_vendedor)     # lo que recibe el vendedor
                })
            except Exception as e:
                logger.error(f"Error en preview — usuario={user_id}: {e}")
                return JsonResponse({'success': False})
        # --- CASO B: Confirmación y Generación Final ---
        if 'confirm' in request.POST:
            monto_contado = request.POST.get('monto', '').strip()
            cuotas = request.POST.get('cuotas', '1')
            tipo = request.POST.get('tipo_tarjeta', 'credito')
            desc = request.POST.get('descripcion', '').strip()

            logger.info(
                f"Generando link — usuario={user_id} monto={monto_contado} "
                f"tipo={tipo} cuotas={cuotas} descripcion='{desc}'"
            )

            link_obj, errors = crud.create_link(user_id, monto_contado, int(cuotas), tipo, desc)

            if not errors:
                logger.info(
                    f"Link generado OK — usuario={user_id} order_id={link_obj.order_id} "
                    f"monto_bruto={link_obj.monto} neto={link_obj.receiver_amount} "
                    f"comision={link_obj.commission_amount}"
                )
                request.session['link_recien_creado'] = {'url': link_obj.link}
                messages.success(request, "¡Enlace de pago generado con éxito!")
                return redirect('crear_link')
            else:
                logger.error(f"Error generando link — usuario={user_id} errores={errors}")
                for e in errors:
                    messages.error(request, e)

    # GET — Carga de tabla
    all_links = crud.list_links_for_cliente(user_id)
    paginator = Paginator(all_links, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    link_creado = request.session.pop('link_recien_creado', None)

    logger.debug(f"Creación link GET — usuario={user_id} total_links={all_links.count()}")

    return render(request, 'creacion_link.html', {
        'user': cliente,
        'links': page_obj,
        'planes': planes_activos,
        'link_creado': link_creado,
        'config': config
    })


def verificar_estado_pago_ajax(request, link_id):
    user_id = request.session.get('user_id')
    if not user_id:
        logger.warning(f"Verificación de pago sin sesión — link_id={link_id}")
        return JsonResponse({'error': 'No autorizado'}, status=401)

    logger.debug(f"Verificando estado de pago — link_id={link_id} usuario={user_id}")

    resultado_crud = crud.verificar_estado_pago(link_id)

    logger.debug(
        f"Resultado verificación — link_id={link_id} "
        f"pagado={resultado_crud['pagado']} anulado={resultado_crud['anulado']} "
        f"status={resultado_crud['status']}"
    )

    if resultado_crud['pagado']:
        logger.info(f"Pago confirmado — link_id={link_id} usuario={user_id} cuotas={resultado_crud['cuotas']}")
    elif resultado_crud['anulado']:
        logger.warning(f"Pago anulado/rechazado — link_id={link_id} usuario={user_id} status={resultado_crud['status']}")

    mensajes = {
        'AUTHORISED': 'Pago Autorizado',
        'CAPTURED': 'Pago Exitoso',
        'REFUSED': 'Pago Rechazado por el Banco',
        'CANCELLED': 'Pago Cancelado por el Usuario',
        'EXPIRED': 'El link ha expirado',
        'PENDING': 'Esperando pago...',
        'ABANDONED': 'El cliente abandonó el pago'
    }

    estado_texto = mensajes.get(resultado_crud['status'], resultado_crud['status'])

    return JsonResponse({
        'pagado': resultado_crud['pagado'],
        'anulado': resultado_crud['anulado'],
        'status_raw': resultado_crud['status'],
        'status_txt': estado_texto,
        'cuotas': resultado_crud['cuotas'],
        'id': link_id
    })


def logout_cliente(request):
    user_id = request.session.get('user_id')
    logger.info(f"Logout — usuario id={user_id}")
    request.session.flush()
    return redirect('login_cliente')


def ticket_pdf(request, link_id):
    user_id       = request.session.get('user_id')
    user_admin_id = request.session.get('user_admin_id')

    # Permite acceso si es cliente autenticado O si es admin
    if not user_id and not user_admin_id:
        return redirect('login_cliente')

    logger.info(f"Generando PDF — link_id={link_id} usuario={user_id} admin={user_admin_id}")

    try:
        # Admin puede ver el PDF de cualquier cliente
        # Cliente solo puede ver sus propios PDFs
        if user_admin_id:
            link = LinkPago.objects.get(id=link_id)
        else:
            link = LinkPago.objects.get(id=link_id, cliente_id=user_id)
            
        config = ParametroFinanciero.objects.first()

        if not config:
            return HttpResponse("Configuración financiera no encontrada.", status=500)

        monto = Decimal(str(link.monto))

        # ── Leer desglose congelado directamente de la DB ──────────────
        # Si el link fue creado antes de esta migración, los campos
        # tendrán valor 0 — en ese caso recalculamos como fallback
        tiene_desglose = link.desglose_arancel + link.desglose_comision + link.desglose_tasa > 0

        if tiene_desglose:
            ar_monto    = link.desglose_arancel
            com_monto   = link.desglose_comision
            tasa_monto  = link.desglose_tasa
            iva_21      = link.desglose_iva_21
            iva_105     = link.desglose_iva_105
            cuota_valor = link.desglose_cuota_valor
            logger.debug(f"PDF — usando desglose congelado de DB — link_id={link_id}")
        else:
            # Fallback para links anteriores a la migración
            logger.warning(f"PDF — desglose no guardado, recalculando — link_id={link_id}")
            total_commission = Decimal(str(link.commission_amount))
            cuota_valor = (monto / link.cuotas_elegidas).quantize(Decimal('0.01'), ROUND_HALF_UP)
            ar_monto    = (total_commission / 3).quantize(Decimal('0.01'), ROUND_HALF_UP)
            tasa_monto  = (total_commission / 3).quantize(Decimal('0.01'), ROUND_HALF_UP)
            com_monto   = total_commission - ar_monto - tasa_monto
            iva_21      = Decimal('0.00')
            iva_105     = Decimal('0.00')

        logger.debug(
            f"PDF — ar={ar_monto} com={com_monto} tasa={tasa_monto} "
            f"iva_21={iva_21} iva_105={iva_105}"
        )

        context = {
            'link':     link,
            'cliente':  link.cliente,
            'config':   config,
            'desglose': {
                'arancel':     ar_monto,
                'servicio':    com_monto,
                'costo_finan': tasa_monto,
                'iva_21':      iva_21,
                'iva_105':     iva_105,
                'cuota_valor': cuota_valor,
            },
            'liq_nro':  link.auth_code if link.auth_code else f"00{link.id}",
            'lote_nro': link.lote_number if link.lote_number else "001",
        }

        html_string = render_to_string('ticket_pdf.html', context)
        html        = HTML(string=html_string, base_url=request.build_absolute_uri())
        pdf_file    = html.write_pdf()

        response = HttpResponse(pdf_file, content_type='application/pdf')
        filename  = f"Liquidacion_{link.auth_code if link.auth_code else link.id}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except LinkPago.DoesNotExist:
        return HttpResponse("El comprobante solicitado no existe.", status=404)
    except Exception as e:
        logger.exception(f"PDF — error inesperado — link_id={link_id}: {e}")
        return HttpResponse(f"Error interno: {str(e)}", status=500)

def download_ticket(request, link_id):
    user_id = request.session.get('user_id')
    if not user_id:
        logger.debug(f"Download ticket sin sesión — link_id={link_id}")
        return redirect('login_cliente')

    logger.debug(f"Descargando ticket TXT — link_id={link_id} usuario={user_id}")

    filename, content, errors = crud.get_invoice_for_link(link_id, user_id)

    if errors:
        logger.warning(f"Download ticket — error obteniendo invoice — link_id={link_id} errores={errors}")
        return redirect('creacion_link')

    logger.info(f"Ticket TXT descargado — link_id={link_id} usuario={user_id} filename={filename}")

    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def gestion_perfil(request):
    user_id = request.session.get('user_id')
    if not user_id:
        logger.debug("Perfil — sesión no encontrada, redirigiendo a login")
        return redirect('login_cliente')

    cliente = crud.get_cliente(user_id)
    if not cliente:
        logger.warning(f"Perfil — cliente id={user_id} no encontrado en DB")
        return redirect('login_cliente')

    logger.debug(f"Perfil cargado — usuario={cliente.nombre} id={user_id}")

    if request.method == 'POST':
        data = {
            'nombre': request.POST.get('nombre'),
            'email': request.POST.get('email'),
            'telefono': request.POST.get('telefono'),
            'password': request.POST.get('password') if request.POST.get('password') else None
        }

        logger.debug(f"Actualización de perfil — usuario={user_id} campos={[k for k, v in data.items() if v]}")

        confirm_password = request.POST.get('confirm_password')
        if data['password'] and data['password'] != confirm_password:
            logger.warning(f"Perfil — contraseñas no coinciden — usuario={user_id}")
            messages.error(request, "Las contraseñas no coinciden.")
        else:
            errors = crud.update_cliente(user_id, data)
            if not errors:
                logger.info(f"Perfil actualizado OK — usuario={user_id} nombre={data.get('nombre')} email={data.get('email')}")
                messages.success(request, "Perfil actualizado correctamente.")
                return redirect('perfil')
            else:
                logger.warning(f"Perfil — errores al actualizar — usuario={user_id} errores={errors}")
                for error in errors:
                    messages.error(request, error)

    return render(request, 'perfil.html', {'user': cliente})