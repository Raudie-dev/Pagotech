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
from app2.models import ParametroFinanciero, CuotaConfig # Importar de la otra app
import os

def index(request):
    return render(request, 'index.html')

def register(request):
    if request.method == 'POST':
        # 1. Recolección de datos
        nombre = request.POST.get('nombre', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        email = request.POST.get('email', '').strip()
        telefono = request.POST.get('telefono', '').strip()

        # 2. Validación manual de contraseñas (Como respaldo al JS)
        if password != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'register.html', {
                'data': request.POST # Re-enviamos todo el POST para no vaciar los campos
            })

        # 3. Intento de creación en el CRUD
        # Nota: create_cliente ya se encarga de poner MAYÚSCULAS y minúsculas
        cliente, errors = crud.create_cliente(nombre, password, email, telefono)

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'register.html', {
                'data': request.POST, # Mantenemos los datos en los inputs
                'errors': errors      # Por si aún usas la caja roja de errores
            })

        # 4. Éxito: Redirección con el parámetro que detecta tu main.js
        return redirect(f"{reverse('index')}?registered=1")

    # GET: Carga normal de la página
    return render(request, 'register.html')

def login_cliente(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        try:
            user = Cliente.objects.get(email__iexact=email)
            if user.bloqueado:
                messages.error(request, 'Usuario bloqueado')
            elif not user.aprobado:
                messages.error(request, 'Cuenta pendiente de aprobación')
            elif check_password(password, user.password):
                request.session['user_id'] = user.id
                messages.success(request, f"Bienvenido {user.nombre}")
                return redirect('dashboard')
            else:
                messages.error(request, 'Contraseña incorrecta')
        except Cliente.DoesNotExist:
            messages.error(request, 'Correo no encontrado')
    return render(request, 'login.html')

def dashboard(request):
    user_id = request.session.get('user_id')
    if not user_id: return redirect('login_cliente')
    
    cliente = crud.get_cliente(user_id)
    if not cliente: return redirect('login_cliente')

    stats = crud.get_dashboard_stats(user_id)
    context = {
        'user': cliente,
        'total_links': stats['total_links'],
        'total_payments': stats['total_payments'],
        'pending_payments': stats['pending_payments'],
    }
    return render(request, 'dashboard.html', context)

def creacion_link(request):
    user_id = request.session.get('user_id')
    if not user_id: return redirect('login_cliente')
    cliente = crud.get_cliente(user_id)
    
    # 1. Obtener la configuración dinámica del Admin (App2)
    config = ParametroFinanciero.objects.first()
    if not config:
        config = ParametroFinanciero.objects.create() # Fallback de seguridad

    # Obtener planes para el Select (Ordenados para el frontend)
    planes_activos = CuotaConfig.objects.filter(activa=True).order_by('numero_cuota')

    if request.method == 'POST':
        # --- CASO A: AJAX Preview (Cálculo exacto igual al CRUD) ---
        if 'preview' in request.POST:
            try:
                monto_neto = Decimal(request.POST.get('monto', '0'))
                cuotas_num = int(request.POST.get('cuotas', '1'))
                tipo = request.POST.get('tipo_tarjeta', 'credito')
                
                # Factores de IVA
                iva_gen = (Decimal(str(config.iva)) / 100) + 1 # Ej: 1.21
                iva_fin = (Decimal(str(config.iva_financiacion)) / 100) + 1 # Ej: 1.105
                
                if tipo == 'debito':
                    # Valores para DÉBITO de la base de datos (app2)
                    pt_pct = Decimal(str(config.comision_pago_tech_debito))
                    ar_pct = Decimal(str(config.arancel_plataforma_debito))
                    tasa_finan_iva = Decimal('0')
                    cuotas_num = 1 # Forzar 1 pago
                else:
                    # Valores para CRÉDITO de la base de datos (app2)
                    pt_pct = Decimal(str(config.comision_pago_tech))
                    ar_pct = Decimal(str(config.arancel_plataforma))
                    
                    tasa_finan_iva = Decimal('0')
                    if cuotas_num > 1:
                        plan = CuotaConfig.objects.filter(numero_cuota=cuotas_num, activa=True).first()
                        if plan:
                            tasa_finan_iva = Decimal(str(plan.tasa_base)) * iva_fin
                
                # SUMATORIA DE COSTOS TRASLADADOS (Columna Roja)
                pt_iva_pct = pt_pct * iva_gen
                ar_iva_pct = ar_pct * iva_gen
                total_costos_pct = pt_iva_pct + ar_iva_pct + tasa_finan_iva
                
                # DIVISOR PARA COEFICIENTE
                divisor = 1 - (total_costos_pct / 100)
                
                monto_venta = (monto_neto / divisor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                comision_trasladada = monto_venta - monto_neto

                return JsonResponse({
                    'success': True,
                    'monto_venta': float(monto_venta),
                    'comision': float(comision_trasladada),
                    'neto': float(monto_neto)
                })
            except:
                return JsonResponse({'success': False})

        # --- CASO B: Confirmación y Generación Final ---
        if 'confirm' in request.POST:
            monto_contado = request.POST.get('monto', '').strip()
            cuotas = request.POST.get('cuotas', '1')
            tipo = request.POST.get('tipo_tarjeta', 'credito')
            desc = request.POST.get('descripcion', '').strip()

            # El CRUD ya fue actualizado para manejar crédito/débito dinámicamente
            link_obj, errors = crud.create_link(user_id, monto_contado, int(cuotas), tipo, desc)
            
            if not errors:
                # Marcamos para disparar el modal de éxito en la redirección
                request.session['link_recien_creado'] = {'url': link_obj.link}
                messages.success(request, "¡Enlace de pago generado con éxito!")
                return redirect('crear_link')
            else:
                for e in errors: messages.error(request, e)

    # --- LÓGICA DE CARGA DE TABLA ---
    all_links = crud.list_links_for_cliente(user_id)
    paginator = Paginator(all_links, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    # Verificamos si hay un link recién creado para mostrar el modal de éxito
    link_creado = request.session.pop('link_recien_creado', None)

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
        return JsonResponse({'error': 'No autorizado'}, status=401)

    # 1. Obtenemos el diccionario del CRUD
    resultado_crud = crud.verificar_estado_pago(link_id)
    
    # 2. Buscamos el objeto de la base de datos (por las cuotas)
    try:
        link = LinkPago.objects.get(pk=link_id, cliente_id=user_id)
    except LinkPago.DoesNotExist:
        return JsonResponse({'error': 'No existe'}, status=404)
    
    # EXPLICACIÓN DEL FIX:
    # Debemos enviar resultado_crud['pagado'] (que es un Booleano)
    # y no resultado_crud (que es un Objeto/Diccionario).
    return JsonResponse({
        'pagado': resultado_crud['pagado'],   # <--- AHORA SÍ ES TRUE O FALSE
        'anulado': resultado_crud['anulado'],
        'cuotas': resultado_crud['cuotas'],
        'id': link_id
    })

def logout_cliente(request):
    request.session.flush()
    return redirect('login_cliente')

def ticket_pdf(request, link_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_cliente')

    try:
        # 1. Obtener datos del link y configuración global
        link = LinkPago.objects.get(id=link_id, cliente_id=user_id)
        config = ParametroFinanciero.objects.first()
        
        if not config:
            return HttpResponse("Configuración financiera no encontrada.", status=500)

        # 2. Definición de constantes para el cálculo
        monto_pagado_cliente = Decimal(str(link.monto))  # Lo que pagó el cliente (Bruto)
        total_descuentos_pago_tech = Decimal(str(link.commission_amount)) # Lo que se le descontó al vendedor
        neto_para_vendedor = Decimal(str(link.receiver_amount)) # Lo que el vendedor recibe limpio
        
        # Factores de IVA
        iva_general_factor = (Decimal(str(config.iva)) / 100) + 1  # 1.21
        iva_finan_factor = (Decimal(str(config.iva_financiacion)) / 100) + 1  # 1.105

        # --- DESGLOSE DE LA COLUMNA DE DESCUENTOS ---

        # 3. Cálculo de Arancel (Payway/Prisma/Lyra)
        # Seleccionamos arancel crédito o débito según corresponda
        if link.tipo_tarjeta == 'debito':
            arancel_base = Decimal(str(config.arancel_plataforma_debito))
        else:
            arancel_base = Decimal(str(config.arancel_plataforma))
        
        # Arancel final con IVA incluido
        arancel_monto = (monto_pagado_cliente * (arancel_base * iva_general_factor / 100)).quantize(Decimal('0.01'), ROUND_HALF_UP)

        # 4. Cálculo de "Servicio de Gestión Venta" (Ex comisión Pago Tech)
        if link.tipo_tarjeta == 'debito':
            gestion_base = Decimal(str(config.comision_pago_tech_debito))
        else:
            gestion_base = Decimal(str(config.comision_pago_tech))
            
        servicio_gestion_monto = (monto_pagado_cliente * (gestion_base * iva_general_factor / 100)).quantize(Decimal('0.01'), ROUND_HALF_UP)

        # 5. Cálculo de "Costo Financiero Plan Cuotas" (Remainder / Restante)
        # Para que la suma sea perfecta, el costo financiero es la diferencia entre el total descontado
        # y los dos items fijos calculados arriba (arancel y gestión).
        costo_financiero_monto = total_descuentos_pago_tech - arancel_monto - servicio_gestion_monto
        
        # Validación de seguridad para 1 cuota (donde el costo financiero es técnicamente cero o mínimo por redondeo)
        if link.cuotas_elegidas <= 1:
            costo_financiero_monto = Decimal('0.00')

        # 6. Desglose de Impuestos (IVA 21% e IVA 10.5%)
        # El IVA 21 es sobre el Arancel y el Servicio de Gestión
        iva_21 = ((arancel_monto + servicio_gestion_monto) / iva_general_factor * (Decimal(str(config.iva)) / 100)).quantize(Decimal('0.01'), ROUND_HALF_UP)
        
        # El IVA 10.5 es sobre el Costo Financiero (solo si hubo cuotas)
        iva_105 = Decimal('0.00')
        if costo_financiero_monto > 0:
            iva_105 = (costo_financiero_monto / iva_finan_factor * (Decimal(str(config.iva_financiacion)) / 100)).quantize(Decimal('0.01'), ROUND_HALF_UP)

        # 7. Cálculo de valor de cuota individual
        cuota_valor = (monto_pagado_cliente / link.cuotas_elegidas).quantize(Decimal('0.01'), ROUND_HALF_UP)

        # 8. Preparar Contexto para el template
        context = {
            'link': link,
            'cliente': link.cliente,
            'config': config,
            'desglose': {
                'arancel': arancel_monto,                # "Arancel Plásticos"
                'servicio': servicio_gestion_monto,      # "Servicio de Gestión Venta"
                'costo_finan': costo_financiero_monto,   # "Costo Financiero Plan Cuotas"
                'iva_21': iva_21,
                'iva_105': iva_105,
                'cuota_valor': cuota_valor
            },
            # Datos técnicos de PayZen para encabezado
            'liq_nro': link.auth_code if link.auth_code else f"00{link.id}",
            'lote_nro': link.lote_number if link.lote_number else "001",
        }

        # 9. Generación del PDF
        html_string = render_to_string('ticket_pdf.html', context)
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        
        # Configuramos weasyprint para renderizar en memoria
        pdf_file = html.write_pdf()

        # 10. Respuesta HTTP
        response = HttpResponse(pdf_file, content_type='application/pdf')
        filename = f"Liquidacion_{link.auth_code if link.auth_code else link.id}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response

    except LinkPago.DoesNotExist:
        return HttpResponse("El comprobante solicitado no existe.", status=404)
    except Exception as e:
        # En producción sería ideal loguear el error: print(f"Error PDF: {e}")
        return HttpResponse(f"Error interno al generar el PDF: {str(e)}", status=500)
    
def download_ticket(request, link_id):
    user_id = request.session.get('user_id')
    if not user_id: return redirect('login_cliente')
    filename, content, errors = crud.get_invoice_for_link(link_id, user_id)
    if errors: return redirect('creacion_link')
    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response