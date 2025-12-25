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
from xhtml2pdf import pisa # Importar xhtml2pdf

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
    # 1. Validación de Sesión
    user_id = request.session.get('user_id')
    if not user_id: 
        return redirect('login_cliente')
    
    cliente = crud.get_cliente(user_id)
    if not cliente:
        return redirect('login_cliente')

    # 2. Manejo de POST (Preview y Creación)
    if request.method == 'POST':
        # --- CASO A: AJAX Preview ---
        if 'preview' in request.POST:
            monto = request.POST.get('monto', '0')
            tipo = request.POST.get('tipo_tarjeta', 'credito')
            try:
                m_dec = Decimal(monto)
                perc = Decimal('3.49') if tipo == 'debito' else Decimal('3.99')
                com = (m_dec * perc / 100).quantize(Decimal('0.01'))
                return JsonResponse({
                    'monto': str(m_dec), 
                    'tipo': tipo, 
                    'commission_amount': str(com), 
                    'receiver_amount': str(m_dec - com)
                })
            except: 
                return JsonResponse({'error': 'Monto inválido'}, status=400)

        # --- CASO B: Confirmación Final (Crear el Link) ---
        if 'confirm' in request.POST:
            monto = request.POST.get('monto', '').strip()
            # cuotas = request.POST.get('cuotas', '1')
            tipo = request.POST.get('tipo_tarjeta', 'credito')
            desc = request.POST.get('descripcion', '').strip()

            link_obj, errors = crud.create_link(
                user_id, 
                monto, 
                #int(cuotas),
                1,
                tipo, 
                desc)
            
            if not errors:
                # GUARDAMOS EN SESIÓN para mostrar el modal después del redirect
                request.session['link_recien_creado'] = {
                    'url': link_obj.link,
                    'monto': str(link_obj.monto),
                    'commission_amount': str(link_obj.commission_amount),
                    'receiver_amount': str(link_obj.receiver_amount)
                }
                messages.success(request, "¡Enlace de pago generado con éxito!")
                
                # REDIRECCIÓN CRÍTICA: Esto evita que se re-envíe el formulario al refrescar
                # y fuerza a Django a volver a cargar la lista de links actualizada.
                return redirect('crear_link')
            else:
                for e in errors: 
                    messages.error(request, e)

    # 3. Lógica de descarga PDF (vía GET)
    download_id = request.GET.get('download')
    if download_id:
        filename, pdf_bytes, errors = crud.generate_pdf_for_link(download_id, user_id)
        if not errors:
            resp = HttpResponse(pdf_bytes, content_type='application/pdf')
            resp['Content-Disposition'] = f'attachment; filename="{filename}"'
            return resp
        for e in errors: messages.error(request, e)

    # 4. PREPARACIÓN DE DATOS PARA EL RENDER (GET)
    
    # Recuperamos el link de la sesión si existe (y lo borramos de la sesión con .pop)
    link_creado_context = request.session.pop('link_recien_creado', None)

    # Obtenemos la lista de links (aquí ya aparecerá el nuevo porque es una petición nueva)
    all_links = crud.list_links_for_cliente(user_id)
    paginator = Paginator(all_links, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'creacion_link.html', {
        'user': cliente, 
        'links': page_obj,
        'link_creado': link_creado_context,
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
        template = get_template('ticket_pdf.html') 
        context = {'link': link, 'cliente': link.cliente}
        html = template.render(context)

        response = HttpResponse(content_type='application/pdf')
        # Si quitas el filename, el navegador suele forzar más la vista previa
        response['Content-Disposition'] = 'inline' 
        
        pisa_status = pisa.CreatePDF(html, dest=response)
        
        if pisa_status.err:
            return HttpResponse('Error al generar PDF', status=500)
            
        return response

    except LinkPago.DoesNotExist:
        return HttpResponse("No encontrado", status=404)