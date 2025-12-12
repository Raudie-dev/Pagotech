from pyexpat.errors import messages
from django.shortcuts import render, redirect
from django.urls import reverse
import django.contrib.messages as messages
from django.contrib.auth.hashers import check_password  
from .models import Cliente
from . import crud
from decimal import Decimal, InvalidOperation
from django.http import HttpResponse, Http404, JsonResponse
from django.template.loader import render_to_string

# Create your views here.
def index(request):
    return render(request, 'index.html')

# Reescribir register para usar crud.create_cliente
def register(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        email = request.POST.get('email', '').strip() or None
        telefono = request.POST.get('telefono', '').strip() or None

        if password != password2:
            errors = ['Las contraseñas no coinciden.']
            return render(request, 'register.html', {'errors': errors, 'data': {'nombre': nombre, 'email': email, 'telefono': telefono}})

        cliente, errors = crud.create_cliente(nombre, password, email, telefono)
        if errors:
            return render(request, 'register.html', {'errors': errors, 'data': {'nombre': nombre, 'email': email, 'telefono': telefono}})
        return redirect(f"{reverse('index')}?registered=1")

    return render(request, 'register.html')

def login_cliente(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        try:
            # búsqueda por email (insensible a mayúsculas)
            user = Cliente.objects.get(email__iexact=email)
            # Verificar estado del usuario antes de comprobar contraseña
            if user.bloqueado:
                messages.error(request, 'Usuario bloqueado')
            elif not user.aprobado:
                messages.error(request, 'Cuenta pendiente de aprobación por el administrador')
            elif user.password == password or check_password(password, user.password):
                request.session['user_id'] = user.id
                return redirect('dashboard')
            else:
                messages.error(request, 'Contraseña incorrecta')
            return render(request, 'login.html')
        except Cliente.DoesNotExist:
            messages.error(request, 'Correo no encontrado')
            return render(request, 'login.html')

    return render(request, 'login.html')

def dashboard(request):

    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_cliente')

    try:
        cliente = Cliente.objects.get(id=user_id)
    except Cliente.DoesNotExist:
        return redirect('login_cliente')

    context = {
        'user': cliente,
        'total_links': 0,       # reemplazar con datos reales si existen
        'total_payments': 0,
        'pending_payments': 0,
    }
    return render(request, 'dashboard.html', context)

def creacion_link(request):
	"""
	Vista para crear links de pago y mostrar los registrados del usuario,
	preview del ticket (modal) y descarga del ticket en PDF con WeasyPrint.
	"""
	user_id = request.session.get('user_id')
	if not user_id:
		return redirect('login_cliente')

	try:
		cliente = Cliente.objects.get(id=user_id)
	except Cliente.DoesNotExist:
		return redirect('login_cliente')

	# Si viene ?download=<id> -> generar PDF y descargar
	download_id = request.GET.get('download')
	if download_id:
		filename, pdf_bytes, errors = crud.generate_pdf_for_link(download_id, user_id)
		if errors:
			for e in errors:
				messages.error(request, e)
			# seguir a mostrar la página con errores
		else:
			resp = HttpResponse(pdf_bytes, content_type='application/pdf')
			resp['Content-Disposition'] = f'attachment; filename="{filename}"'
			return resp

	if request.method == 'POST':
		# PREVIEW: no crea el link, devuelve JSON con los datos para el modal
		if 'preview' in request.POST:
			monto = request.POST.get('monto', '').strip()
			cuotas = request.POST.get('cuotas', '1')
			tipo = request.POST.get('tipo_tarjeta', 'credito')
			descripcion = request.POST.get('descripcion', '').strip()

			# calcular valores sin persistir
			try:
				monto_dec = Decimal(monto)
			except (InvalidOperation, ValueError):
				return JsonResponse({'error': 'Monto inválido.'}, status=400)

			tipo = tipo if tipo in ('debito', 'credito') else 'credito'
			perc_map = {'debito': Decimal('3.49'), 'credito': Decimal('3.99')}
			perc = perc_map[tipo]
			commission_amount = (monto_dec * perc / Decimal('100')).quantize(Decimal('0.01'))
			receiver_amount = (monto_dec - commission_amount).quantize(Decimal('0.01'))

			payload = {
				'monto': f"{monto_dec:.2f}",
				'cuotas': int(cuotas),
				'tipo': 'Débito' if tipo == 'debito' else 'Crédito',
				'commission_percent': f"{perc:.2f}",
				'commission_amount': f"{commission_amount:.2f}",
				'receiver_amount': f"{receiver_amount:.2f}",
				'descripcion': descripcion or '-',
			}
			return JsonResponse(payload)

		# CONFIRM: crear link definitivamente (solo cuando explicitamente se envía confirm)
		if 'confirm' in request.POST:
			monto = request.POST.get('monto', '').strip()
			cuotas = request.POST.get('cuotas', '1')
			tipo_tarjeta = request.POST.get('tipo_tarjeta', 'credito')
			descripcion = request.POST.get('descripcion', '').strip()

			try:
				monto_dec = Decimal(monto)
			except (InvalidOperation, ValueError):
				messages.error(request, 'Monto inválido.')
				links = crud.list_links_for_cliente(user_id)
				return render(request, 'creacion_link.html', {'user': cliente, 'links': links})

			try:
				cuotas_int = int(cuotas)
				if cuotas_int <= 0:
					cuotas_int = 1
			except (ValueError, TypeError):
				cuotas_int = 1

			link_obj, errors = crud.create_link(user_id, monto_dec, cuotas=cuotas_int, tipo_tarjeta=tipo_tarjeta, descripcion=descripcion)
			if errors:
				for e in errors:
					messages.error(request, e)
				links = crud.list_links_for_cliente(user_id)
				return render(request, 'creacion_link.html', {'user': cliente, 'links': links})

			# Construir la URL absoluta del link de pago
			try:
				link_url = request.build_absolute_uri(reverse('pago_link', args=[link_obj.link]))
			except Exception:
				link_url = request.build_absolute_uri('/pago/' + link_obj.link + '/')

			# Pasar todos los datos al modal de éxito
			links = crud.list_links_for_cliente(user_id)
			context = {
				'user': cliente,
				'links': links,
				'link_creado': {
					'url': link_url,
					'monto': link_obj.monto,
					'cuotas': link_obj.cuotas,
					'tipo_tarjeta': link_obj.tipo_tarjeta,
					'descripcion': link_obj.descripcion,
					'commission_percent': link_obj.commission_percent,
					'commission_amount': link_obj.commission_amount,
					'receiver_amount': link_obj.receiver_amount,
				}
			}
			return render(request, 'creacion_link.html', context)
		# Si POST sin preview ni confirm -> no crear, pedir usar la vista previa
		messages.error(request, 'Por favor use "Vista previa y confirmar" para crear el link.')
		links = crud.list_links_for_cliente(user_id)
		return render(request, 'creacion_link.html', {'user': cliente, 'links': links})

	# GET -> mostrar formulario y lista de links del usuario
	links = crud.list_links_for_cliente(user_id)
	context = {
		'user': cliente,
		'links': links,
	}
	return render(request, 'creacion_link.html', context)

def download_ticket(request, link_id):
	"""
	Descarga el ticket/factura en texto plano para el link indicado (solo propietario).
	"""
	user_id = request.session.get('user_id')
	if not user_id:
		return redirect('login_cliente')

	from .models import LinkPago
	try:
		link = LinkPago.objects.get(id=link_id)
	except LinkPago.DoesNotExist:
		raise Http404("Link no encontrado")

	if link.cliente.id != user_id:
		return HttpResponse("No autorizado", status=403)

	# asegurar que invoice_text exista
	if not link.invoice_text:
		link.generate_invoice_text()
		link.save()

	response = HttpResponse(link.invoice_text, content_type='text/plain; charset=utf-8')
	filename = f"ticket_link_{link.id}.txt"
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	return response

def logout_cliente(request):
    request.session.flush()
    return redirect('index')