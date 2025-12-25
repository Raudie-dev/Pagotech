from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from .models import User_admin
from . import crud as admin_crud
from app1 import models as app1_models
from django.core.paginator import Paginator

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
            return render(request, 'login_admin.html')
        except User_admin.DoesNotExist:
            messages.error(request, 'Usuario no encontrado')
            return render(request, 'login_admin.html')

    return render(request, 'login_admin.html')

# Nueva lógica: control = vista de GESTIÓN de usuarios (solo usuarios aprobados)
def gestion_usuarios(request):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        return redirect('login')
    
    user_admin = User_admin.objects.get(id=user_id)

    if request.method == 'POST':
        # --- ACCIÓN: EDITAR ---
        edit_id = request.POST.get('edit_id')
        if edit_id:
            data = {
                'nombre': request.POST.get('edit_nombre'),
                'email': request.POST.get('edit_email'),
                'telefono': request.POST.get('edit_telefono'),
                'aprobado': request.POST.get('edit_aprobado') == '1',
                'bloqueado': request.POST.get('edit_bloqueado') == '1',
            }
            ok, err = admin_crud.update_cliente(edit_id, data)
            if ok:
                messages.success(request, 'Usuario actualizado correctamente.')
            else:
                messages.error(request, err)
            return redirect('gestion_usuarios')

        # --- ACCIÓN: BLOQUEAR / DESBLOQUEAR ---
        bloquear_id = request.POST.get('bloquear_id')
        desbloquear_id = request.POST.get('desbloquear_id')
        if bloquear_id or desbloquear_id:
            target_id = bloquear_id if bloquear_id else desbloquear_id
            estado = True if bloquear_id else False
            ok, err = admin_crud.set_bloqueo(target_id, estado)
            if ok:
                msg = "Usuario bloqueado." if estado else "Usuario desbloqueado."
                messages.success(request, msg)
            else:
                messages.error(request, err)
            return redirect('gestion_usuarios')

        # --- ACCIÓN: ELIMINAR ---
        delete_id = request.POST.get('delete_id')
        if delete_id:
            ok, err = admin_crud.delete_cliente(delete_id)
            if ok:
                messages.success(request, 'Usuario eliminado definitivamente.')
            else:
                messages.error(request, err)
            return redirect('gestion_usuarios')

    # --- LÓGICA GET (Búsqueda y Estadísticas) ---
    q = request.GET.get('q', '').strip()
    
    # 1. Obtener todos los clientes que ya están aprobados (base para las estadísticas)
    # Filtramos por aprobado=True desde el inicio
    aprobados_base = admin_crud.list_clientes({'aprobado': True})
    
    # 2. Usuarios Totales (Solo Aprobados)
    total_users_aprobados = aprobados_base.count()
    
    # 3. Usuarios Bloqueados (Que estén aprobados pero tengan la marca de bloqueo)
    blocked_count = aprobados_base.filter(bloqueado=True).count()
    
    # 4. Usuarios Activos (Aprobados que NO están bloqueados)
    activos_count = aprobados_base.filter(bloqueado=False).count()

    # 5. Lista para la tabla (Aprobados + filtro de búsqueda si existe)
    clientes_qs = admin_crud.list_clientes({'aprobado': True, 'q': q})

    # --- LÓGICA DE PAGINACIÓN ---
    paginator = Paginator(clientes_qs, 10) # 10 registros por página
    page_number = request.GET.get('page')  # Obtener el número de página de la URL (?page=2)
    page_obj = paginator.get_page(page_number)
    context = {
        'user': user_admin,
        'clientes': page_obj,             # Los que se ven en la tabla
        'q': q,
        'total_users': total_users_aprobados, # Tarjeta 1
        'activos_count': activos_count,      # Tarjeta 2
        'blocked_count': blocked_count,      # Tarjeta 3
    }
    return render(request, 'gestion_usuarios.html', context)

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
        # 1. Acción: Editar Información (desde el modal)
        edit_id = request.POST.get('edit_id')
        if edit_id:
            data = {
                'nombre': request.POST.get('edit_nombre'),
                'email': request.POST.get('edit_email'),
                'telefono': request.POST.get('edit_telefono'),
                'aprobado': request.POST.get('edit_aprobado') == '1',
                'bloqueado': request.POST.get('edit_bloqueado') == '1',
            }
            ok, err = admin_crud.update_cliente(edit_id, data)
            if ok:
                messages.success(request, 'Usuario actualizado correctamente.')
            else:
                messages.error(request, err)
            return redirect('aprobacion')

        # 2. Acción: Aprobar (botón check)
        approve_id = request.POST.get('approve_id')
        if approve_id:
            ok, err = admin_crud.approve_cliente(approve_id)
            if ok:
                messages.success(request, 'Usuario aprobado y movido a la gestión principal.')
            else:
                messages.error(request, err)
            return redirect('aprobacion')

        # 3. Acción: Bloquear (botón ban)
        bloquear_id = request.POST.get('bloquear_id')
        if bloquear_id:
            ok, err = admin_crud.set_bloqueo(bloquear_id, True)
            if ok:
                messages.warning(request, 'El registro ha sido bloqueado.')
            else:
                messages.error(request, err)
            return redirect('aprobacion')

    # GET
    pending_clients = admin_crud.list_pending_clientes()
    return render(request, 'aprobacion.html', {
        'user': user, 
        'pending_clients': pending_clients
    })

def logout(request):
    request.session.flush()
    return redirect('login')