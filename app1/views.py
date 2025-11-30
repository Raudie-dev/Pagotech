from pyexpat.errors import messages
from django.shortcuts import render, redirect
from django.urls import reverse
import django.contrib.messages as messages
from django.contrib.auth.hashers import check_password  
from .models import Cliente
from . import crud

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
    Vista para crear links de pago (seleccionar monto, cuotas y tipo de tarjeta).
    Por ahora guarda los datos mínimos y muestra un mensaje de éxito.
    """
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login_cliente')

    try:
        cliente = Cliente.objects.get(id=user_id)
    except Cliente.DoesNotExist:
        return redirect('login_cliente')

    if request.method == 'POST':
        monto = request.POST.get('monto', '').strip()
        cuotas = request.POST.get('cuotas', '1')
        tipo = request.POST.get('tipo_tarjeta', 'credito')
        descripcion = request.POST.get('descripcion', '').strip()

        messages.success(request, 'Link de pago creado (simulado).')
        return redirect('crear_link')

    context = {
        'user': cliente,
    }
    return render(request, 'creacion_link.html', context)