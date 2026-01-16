from django.shortcuts import render, redirect
from django.urls import reverse
import django.contrib.messages as messages
from django.contrib.auth.hashers import check_password  
from .models import Cliente, LinkPago
from . import crud
from decimal import Decimal, InvalidOperation
from django.http import HttpResponse, Http404, JsonResponse
from django.core.paginator import Paginator
from django.template.loader import get_template
from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import HTML
import tempfile
from app2.models import ParametroFinanciero, CuotaConfig # Importar de la otra app

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
    
    # --- NUEVO: Obtener planes para el Select ---
    planes_activos = CuotaConfig.objects.filter(activa=True).order_by('numero_cuota')

    if request.method == 'POST':
        # --- CASO A: AJAX Preview (Cálculo exacto del Excel) ---
        if 'preview' in request.POST:
            monto_contado = Decimal(request.POST.get('monto', '0'))
            cuotas_num = int(request.POST.get('cuotas', '1'))
            tipo = request.POST.get('tipo_tarjeta', 'credito')
            
            # Buscamos la configuración y el plan
            config = ParametroFinanciero.objects.first()
            plan = CuotaConfig.objects.filter(numero_cuota=cuotas_num).first()
            
            # Calculamos Coeficiente (Lógica Excel)
            iva_f = (1 + config.iva / 100)
            com_pt_iva = (config.comision_pago_tech * iva_f)
            arancel_iva = (config.arancel_plataforma * iva_f)
            tasa_iva = (plan.tasa_base * (1 + config.iva_financiacion / 100)) if (plan and tipo == 'credito' and cuotas_num > 1) else Decimal('0')
            
            total_desc_pct = com_pt_iva + arancel_iva + tasa_iva
            coeficiente = 1 / (1 - (total_desc_pct / 100))
            
            monto_final_venta = monto_contado * coeficiente
            comision_monto = monto_final_venta * (total_desc_pct / 100)

            return JsonResponse({
                'monto_venta': round(float(monto_final_venta), 2), 
                'comision': round(float(comision_monto), 2), 
                'neto': round(float(monto_contado), 2) # Lo que recibe es el monto ingresado
            })

        # --- CASO B: Confirmación Final ---
        if 'confirm' in request.POST:
            monto_contado = request.POST.get('monto', '').strip()
            cuotas = request.POST.get('cuotas', '1')
            tipo = request.POST.get('tipo_tarjeta', 'credito')
            desc = request.POST.get('descripcion', '').strip()

            # Enviamos al CRUD para que procese con las nuevas tasas
            link_obj, errors = crud.create_link(user_id, monto_contado, int(cuotas), tipo, desc)
            
            if not errors:
                request.session['link_recien_creado'] = {'url': link_obj.link}
                messages.success(request, "¡Enlace de pago generado con éxito!")
                return redirect('crear_link')
            else:
                for e in errors: messages.error(request, e)

    # Render normal
    all_links = crud.list_links_for_cliente(user_id)
    paginator = Paginator(all_links, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'creacion_link.html', {
        'user': cliente, 
        'links': page_obj,
        'planes': planes_activos, # Pasamos los planes reales al HTML
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

def download_ticket(request, link_id):
    user_id = request.session.get('user_id')
    if not user_id: return redirect('login_cliente')
    filename, content, errors = crud.get_invoice_for_link(link_id, user_id)
    if errors: return redirect('creacion_link')
    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def logout_cliente(request):
    request.session.flush()
    return redirect('login_cliente')

def ticket_pdf(request, link_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_cliente')

    try:
        link = LinkPago.objects.get(id=link_id, cliente_id=user_id)
        
        # 1. Preparar contexto
        context = {
            'link': link, 
            'cliente': link.cliente,
            'current_year': 2024 # O usa django.utils.timezone
        }

        # 2. Renderizar HTML a string
        html_string = render_to_string('ticket_pdf.html', context)

        # 3. Crear el PDF
        # base_url permite que WeasyPrint encuentre imágenes o CSS locales si los hubiera
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        pdf_file = html.write_pdf()

        # 4. Enviar respuesta
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="comprobante.pdf"'
        return response

    except LinkPago.DoesNotExist:
        return HttpResponse("No encontrado", status=404)