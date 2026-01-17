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

    # Ejecutamos la verificación
    pago_exitoso = crud.verificar_estado_pago(link_id)
    
    # Buscamos el objeto para obtener las cuotas actualizadas
    link = LinkPago.objects.get(pk=link_id)
    
    return JsonResponse({
        'pagado': pago_exitoso,
        'cuotas': link.cuotas_elegidas,  # Enviamos las cuotas al JS
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
        link = LinkPago.objects.get(id=link_id, cliente_id=user_id)
        config = ParametroFinanciero.objects.first() # Traemos la config para el desglose

        # --- CÁLCULO DE DESGLOSE NUMÉRICO ---
        monto_venta = Decimal(str(link.monto))
        iva_f = (config.iva / 100) + 1 # Factor 1.21

        # 1. Arancel Payway con IVA (1.8% * 1.21)
        arancel_monto = (monto_venta * (config.arancel_plataforma * iva_f / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # 2. Comision PagoTech con IVA (Ej: 4% * 1.21)
        pago_tech_monto = (monto_venta * (config.comision_pago_tech * iva_f / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # 3. El resto de la comisión guardada corresponde a la Financiación (Si existe)
        # Esto asegura que la sumatoria siempre sea exacta al commission_amount guardado
        financiacion_monto = Decimal(str(link.commission_amount)) - arancel_monto - pago_tech_monto
        
        # 4. IVA 21%: Sobre el arancel de Payway y el servicio de PagoTech
        iva_21 = ((arancel_monto + pago_tech_monto) / Decimal('1.21') * Decimal('0.21')).quantize(Decimal('0.01'), ROUND_HALF_UP)

        # 5. IVA 10.5%: Sobre la tasa de financiación de cuotas
        iva_105 = (financiacion_monto / Decimal('1.105') * Decimal('0.105')).quantize(Decimal('0.01'), ROUND_HALF_UP)

        # 6. Valor de la cuota individual que paga el cliente
        cuota_valor = (monto_venta / link.cuotas).quantize(Decimal('0.01'), ROUND_HALF_UP)
        
        if financiacion_monto < 0: financiacion_monto = Decimal('0.00')

        # 7. Preparar contexto
        context = {
            'link': link,
            'cliente': link.cliente,
            'desglose': {
                'arancel': arancel_monto,
                'pago_tech': pago_tech_monto,
                'financiacion': financiacion_monto,
                'cuota_valor': cuota_valor, # $ cada cuota
                'iva_21': iva_21,
                'iva_105': iva_105,
            },
            'config': config
        }

        html_string = render_to_string('ticket_pdf.html', context)
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        pdf_file = html.write_pdf()

        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Ticket_#00{link.id}.pdf"'
        return response

    except LinkPago.DoesNotExist:
        return HttpResponse("No encontrado", status=404)
    
def download_ticket(request, link_id):
    user_id = request.session.get('user_id')
    if not user_id: return redirect('login_cliente')
    filename, content, errors = crud.get_invoice_for_link(link_id, user_id)
    if errors: return redirect('creacion_link')
    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response