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

logger = logging.getLogger('app1')


def index(request):
    logger.debug("Vista index cargada")
    return render(request, 'index.html')


def register(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        email = request.POST.get('email', '').strip()
        telefono = request.POST.get('telefono', '').strip()

        logger.debug(f"Intento de registro — email={email} nombre={nombre}")

        if password != password2:
            logger.warning(f"Registro fallido — contraseñas no coinciden — email={email}")
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'register.html', {'data': request.POST})

        cliente, errors = crud.create_cliente(nombre, password, email, telefono)

        if errors:
            logger.warning(f"Registro rechazado — email={email} — errores={errors}")
            for e in errors:
                messages.error(request, e)
            return render(request, 'register.html', {
                'data': request.POST,
                'errors': errors
            })

        logger.info(f"Registro exitoso — email={email} nombre={nombre} id={cliente.id}")
        return redirect(f"{reverse('index')}?registered=1")

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

    planes_activos = CuotaConfig.objects.filter(activa=True).order_by('numero_cuota')
    logger.debug(f"Creación link — usuario={cliente.nombre} id={user_id} planes_activos={planes_activos.count()}")

    if request.method == 'POST':

        # --- CASO A: AJAX Preview ---
        if 'preview' in request.POST:
            try:
                monto_neto = Decimal(request.POST.get('monto', '0'))
                cuotas_num = int(request.POST.get('cuotas', '1'))
                tipo = request.POST.get('tipo_tarjeta', 'credito')

                logger.debug(f"Preview solicitado — usuario={user_id} monto={monto_neto} tipo={tipo} cuotas={cuotas_num}")

                iva_gen = (Decimal(str(config.iva)) / 100) + 1
                iva_fin = (Decimal(str(config.iva_financiacion)) / 100) + 1

                if tipo == 'debito':
                    pt_pct = Decimal(str(config.comision_pago_tech_debito))
                    ar_pct = Decimal(str(config.arancel_plataforma_debito))
                    tasa_finan_iva = Decimal('0')
                    cuotas_num = 1
                else:
                    pt_pct = Decimal(str(config.comision_pago_tech))
                    ar_pct = Decimal(str(config.arancel_plataforma))
                    tasa_finan_iva = Decimal('0')
                    if cuotas_num > 1:
                        plan = CuotaConfig.objects.filter(numero_cuota=cuotas_num, activa=True).first()
                        if plan:
                            tasa_finan_iva = Decimal(str(plan.tasa_base)) * iva_fin
                            logger.debug(f"Preview — plan encontrado: {plan.nombre} tasa_base={plan.tasa_base} tasa_con_iva={tasa_finan_iva}")
                        else:
                            logger.warning(f"Preview — plan de {cuotas_num} cuotas no encontrado o inactivo")

                pt_iva_pct = pt_pct * iva_gen
                ar_iva_pct = ar_pct * iva_gen
                total_costos_pct = pt_iva_pct + ar_iva_pct + tasa_finan_iva

                divisor = 1 - (total_costos_pct / 100)
                monto_venta = (monto_neto / divisor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                comision_trasladada = monto_venta - monto_neto

                logger.debug(
                    f"Preview calculado — usuario={user_id} "
                    f"total_costos={total_costos_pct:.4f}% divisor={divisor:.6f} "
                    f"neto={monto_neto} → bruto={monto_venta} comision={comision_trasladada}"
                )

                return JsonResponse({
                    'success': True,
                    'monto_venta': float(monto_venta),
                    'comision': float(comision_trasladada),
                    'neto': float(monto_neto)
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
    user_id = request.session.get('user_id')
    if not user_id:
        logger.debug(f"PDF solicitado sin sesión — link_id={link_id}")
        return redirect('login_cliente')

    logger.info(f"Generando PDF — link_id={link_id} usuario={user_id}")

    try:
        link = LinkPago.objects.get(id=link_id, cliente_id=user_id)
        config = ParametroFinanciero.objects.first()

        if not config:
            logger.error(f"PDF — ParametroFinanciero no encontrado — link_id={link_id}")
            return HttpResponse("Configuración financiera no encontrada.", status=500)

        # 2. Constantes base
        monto_pagado_cliente = Decimal(str(link.monto))
        total_descuentos_pago_tech = Decimal(str(link.commission_amount))
        neto_para_vendedor = Decimal(str(link.receiver_amount))

        logger.debug(
            f"PDF desglose base — link_id={link_id} "
            f"bruto={monto_pagado_cliente} commission={total_descuentos_pago_tech} neto={neto_para_vendedor} "
            f"tipo={link.tipo_tarjeta} cuotas={link.cuotas_elegidas}"
        )

        iva_general_factor = (Decimal(str(config.iva)) / 100) + 1
        iva_finan_factor = (Decimal(str(config.iva_financiacion)) / 100) + 1

        # 3. Arancel
        if link.tipo_tarjeta == 'debito':
            arancel_base = Decimal(str(config.arancel_plataforma_debito))
        else:
            arancel_base = Decimal(str(config.arancel_plataforma))

        arancel_monto = (monto_pagado_cliente * (arancel_base * iva_general_factor / 100)).quantize(Decimal('0.01'), ROUND_HALF_UP)
        logger.debug(f"PDF — arancel_base={arancel_base}% arancel_con_iva={arancel_monto}")

        # 4. Servicio de Gestión
        if link.tipo_tarjeta == 'debito':
            gestion_base = Decimal(str(config.comision_pago_tech_debito))
        else:
            gestion_base = Decimal(str(config.comision_pago_tech))

        servicio_gestion_monto = (monto_pagado_cliente * (gestion_base * iva_general_factor / 100)).quantize(Decimal('0.01'), ROUND_HALF_UP)
        logger.debug(f"PDF — gestion_base={gestion_base}% servicio_con_iva={servicio_gestion_monto}")

        # 5. Costo Financiero (resto para que la suma cierre perfecta)
        costo_financiero_monto = max(
            Decimal('0.00'),
            total_descuentos_pago_tech - arancel_monto - servicio_gestion_monto
        )
        if link.cuotas_elegidas <= 1:
            logger.debug(f"PDF — 1 cuota: absorbiendo centavo de redondeo ({costo_financiero_monto}) en servicio_gestion")
            servicio_gestion_monto += costo_financiero_monto
            costo_financiero_monto = Decimal('0.00')

        logger.debug(f"PDF — costo_financiero={costo_financiero_monto}")

        # 6. IVA desglosado
        iva_21 = ((arancel_monto + servicio_gestion_monto) / iva_general_factor * (Decimal(str(config.iva)) / 100)).quantize(Decimal('0.01'), ROUND_HALF_UP)
        iva_105 = Decimal('0.00')
        if costo_financiero_monto > 0:
            iva_105 = (costo_financiero_monto / iva_finan_factor * (Decimal(str(config.iva_financiacion)) / 100)).quantize(Decimal('0.01'), ROUND_HALF_UP)

        logger.debug(f"PDF — iva_21={iva_21} iva_105={iva_105}")

        # 7. Cuota individual
        cuota_valor = (monto_pagado_cliente / link.cuotas_elegidas).quantize(Decimal('0.01'), ROUND_HALF_UP)

        # Validación final de cuadre
        suma_desglose = arancel_monto + servicio_gestion_monto + costo_financiero_monto
        diferencia = abs(suma_desglose - total_descuentos_pago_tech)
        if diferencia > Decimal('0.02'):
            logger.warning(
                f"PDF — desglose no cuadra exactamente — link_id={link_id} "
                f"suma_items={suma_desglose} total_commission={total_descuentos_pago_tech} diff={diferencia}"
            )
        else:
            logger.debug(f"PDF — desglose cuadrado OK — diferencia={diferencia}")

        context = {
            'link': link,
            'cliente': link.cliente,
            'config': config,
            'desglose': {
                'arancel': arancel_monto,
                'servicio': servicio_gestion_monto,
                'costo_finan': costo_financiero_monto,
                'iva_21': iva_21,
                'iva_105': iva_105,
                'cuota_valor': cuota_valor
            },
            'liq_nro': link.auth_code if link.auth_code else f"00{link.id}",
            'lote_nro': link.lote_number if link.lote_number else "001",
        }

        html_string = render_to_string('ticket_pdf.html', context)
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        pdf_file = html.write_pdf()

        logger.info(f"PDF generado exitosamente — link_id={link_id} usuario={user_id} filename=Liquidacion_{link.auth_code if link.auth_code else link.id}.pdf")

        response = HttpResponse(pdf_file, content_type='application/pdf')
        filename = f"Liquidacion_{link.auth_code if link.auth_code else link.id}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except LinkPago.DoesNotExist:
        logger.warning(f"PDF — link no encontrado o no pertenece al usuario — link_id={link_id} usuario={user_id}")
        return HttpResponse("El comprobante solicitado no existe.", status=404)
    except Exception as e:
        logger.exception(f"PDF — error inesperado — link_id={link_id} usuario={user_id}: {e}")
        return HttpResponse(f"Error interno al generar el PDF: {str(e)}", status=500)


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