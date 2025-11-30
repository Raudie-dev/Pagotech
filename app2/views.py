from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from .models import User_admin
from . import crud as admin_crud
from app1 import models as app1_models

def login(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        password = request.POST.get('password', '')

        try:
            user = User_admin.objects.get(nombre=nombre)
            if user.bloqueado:
                messages.error(request, 'Usuario bloqueado')
            elif user.password == password or check_password(password, user.password):
                request.session['user_admin_id'] = user.id
                return redirect('gestion_usuarios')
            else:
                messages.error(request, 'Contraseña incorrecta')
            return render(request, 'login.html')
        except User_admin.DoesNotExist:
            messages.error(request, 'Usuario no encontrado')
            return render(request, 'login.html')

    return render(request, 'login_admin.html')

# Nueva lógica: control = vista de GESTIÓN de usuarios (solo usuarios aprobados)
def gestion_usuarios(request):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        messages.error(request, 'Debe iniciar sesión primero')
        return redirect('login')
    try:
        user = User_admin.objects.get(id=user_id)
    except User_admin.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('login')

    if request.method == 'POST':
        # Edición enviada desde modal
        edit_id = request.POST.get('edit_id')
        if edit_id:
            nombre = request.POST.get('edit_nombre', '').strip()
            email = request.POST.get('edit_email', '').strip() or None
            telefono = request.POST.get('edit_telefono', '').strip() or None
            aprobado = request.POST.get('edit_aprobado') == 'on'
            ok, err = admin_crud.update_cliente(edit_id, {
                'nombre': nombre,
                'email': email,
                'telefono': telefono,
                'aprobado': aprobado,
            })
            if ok:
                messages.success(request, 'Cliente actualizado.')
            else:
                messages.error(request, err or 'No se pudo actualizar el cliente.')
            return redirect('gestion_usuarios')

        # Bloquear
        bloquear_id = request.POST.get('bloquear_id')
        if bloquear_id:
            ok, err = admin_crud.set_bloqueo(bloquear_id, True)
            if ok:
                messages.success(request, 'Cliente bloqueado.')
            else:
                messages.error(request, err or 'No se pudo bloquear el cliente.')
            return redirect('gestion_usuarios')

        # Desbloquear
        desbloquear_id = request.POST.get('desbloquear_id')
        if desbloquear_id:
            ok, err = admin_crud.set_bloqueo(desbloquear_id, False)
            if ok:
                messages.success(request, 'Cliente desbloqueado.')
            else:
                messages.error(request, err or 'No se pudo desbloquear el cliente.')
            return redirect('gestion_usuarios')

    # GET: buscar y mostrar solo clientes aprobados
    q = request.GET.get('q', '').strip()
    filters = {'aprobado': True}
    if q:
        filters['nombre'] = q
    clientes_qs = admin_crud.list_clientes(filters)
    total_users = admin_crud.list_clientes({'aprobado': True}).count()
    return render(request, 'gestion_usuarios.html', {'user': user, 'clientes': clientes_qs, 'q': q, 'total_users': total_users})

# Nueva vista: aprobacion = listar solicitudes pendientes y permitir aprobar/bloquear/eliminar
def aprobacion(request):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        messages.error(request, 'Debe iniciar sesión primero')
        return redirect('login')
    try:
        user = User_admin.objects.get(id=user_id)
    except User_admin.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('login')

    if request.method == 'POST':
        # Edición enviada desde modal (permitir editar antes de aprobar/bloquear)
        edit_id = request.POST.get('edit_id')
        if edit_id:
            nombre = request.POST.get('edit_nombre', '').strip()
            email = request.POST.get('edit_email', '').strip() or None
            telefono = request.POST.get('edit_telefono', '').strip() or None
            aprobado = request.POST.get('edit_aprobado') == 'on'
            ok, err = admin_crud.update_cliente(edit_id, {
                'nombre': nombre,
                'email': email,
                'telefono': telefono,
                'aprobado': aprobado,
            })
            if ok:
                messages.success(request, 'Cliente actualizado.')
            else:
                messages.error(request, err or 'No se pudo actualizar el cliente.')
            return redirect('aprobacion')

        # Aprobar
        approve_id = request.POST.get('approve_id')
        if approve_id:
            ok, err = admin_crud.approve_cliente(approve_id)
            if ok:
                messages.success(request, 'Cliente aprobado correctamente.')
            else:
                messages.error(request, err or 'No se pudo aprobar el cliente.')
            return redirect('aprobacion')

        # Bloquear (desde pendientes)
        bloquear_id = request.POST.get('bloquear_id')
        if bloquear_id:
            ok, err = admin_crud.set_bloqueo(bloquear_id, True)
            if ok:
                messages.success(request, 'Cliente bloqueado.')
            else:
                messages.error(request, err or 'No se pudo bloquear el cliente.')
            return redirect('aprobacion')

    pending_clients = admin_crud.list_pending_clientes()
    return render(request, 'aprobacion.html', {'user': user, 'pending_clients': pending_clients})