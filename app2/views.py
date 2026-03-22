from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from .models import User_admin
from . import crud as admin_crud
from app1 import models as app1_models
from django.core.paginator import Paginator
from decimal import Decimal, ROUND_HALF_UP

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
                'password': request.POST.get('edit_password'), # <--- Agregar esta línea
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

# Gestión de administradores
def gestion_admins(request):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        return redirect('login')
    
    current_admin = User_admin.objects.get(id=user_id)

    if request.method == 'POST':
        # 1. ACCIÓN: CREAR
        if 'add_admin' in request.POST:
            data = {
                'nombre': request.POST.get('nombre'),
                'password': request.POST.get('password'),
            }
            ok, err = admin_crud.create_admin(data)
            if ok: messages.success(request, 'Nuevo administrador creado.')
            else: messages.error(request, err)

        # 2. ACCIÓN: EDITAR
        elif 'edit_id' in request.POST:
            edit_id = request.POST.get('edit_id')
            data = {
                'nombre': request.POST.get('edit_nombre'),
                'password': request.POST.get('edit_password'),
                'bloqueado': request.POST.get('edit_bloqueado') == '1',
            }
            # Evitar que un admin se bloquee a sí mismo
            if str(edit_id) == str(user_id) and data['bloqueado']:
                messages.error(request, 'No puedes bloquearte a ti mismo.')
            else:
                ok, err = admin_crud.update_admin(edit_id, data)
                if ok: messages.success(request, 'Administrador actualizado.')
                else: messages.error(request, err)

        # 3. ACCIÓN: ELIMINAR
        elif 'delete_id' in request.POST:
            delete_id = request.POST.get('delete_id')
            if str(delete_id) == str(user_id):
                messages.error(request, 'No puedes eliminar tu propia cuenta.')
            else:
                ok, err = admin_crud.delete_admin(delete_id)
                if ok: messages.success(request, 'Administrador eliminado.')
        
        return redirect('gestion_admins')

    # GET
    q = request.GET.get('q', '').strip()
    admins = admin_crud.list_admins({'q': q})
    
    return render(request, 'gestion_admins.html', {
        'user': current_admin,
        'admins': admins,
        'q': q
    })
    
    
def configuracion_financiera(request):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        return redirect('login')

    user_admin = User_admin.objects.get(id=user_id)

    if request.method == 'POST':

        if 'update_general' in request.POST:
            data = {
                'iva':                          request.POST.get('iva'),
                'iva_financiacion':             request.POST.get('iva_financiacion'),
                'comision_pago_tech':           request.POST.get('comision_pago_tech'),
                'arancel_plataforma':           request.POST.get('arancel_plataforma'),
                'comision_pago_tech_debito':    request.POST.get('comision_pago_tech_debito'),
                'arancel_plataforma_debito':    request.POST.get('arancel_plataforma_debito'),
            }
            admin_crud.update_financiero(data)
            messages.success(request, 'Parámetros base actualizados correctamente.')

        elif 'add_cuota' in request.POST:
            data = {
                'numero_cuota': request.POST.get('new_numero'),
                'nombre':       request.POST.get('new_nombre'),
                'tasa_base':    request.POST.get('new_tasa'),
            }
            admin_crud.create_cuota_plan(data)
            messages.success(request, 'Nuevo plan de cuotas añadido.')

        elif 'update_cuota' in request.POST:
            cuota_id = request.POST.get('cuota_id')
            data = {
                'nombre':       request.POST.get('edit_nombre'),
                'numero_cuota': request.POST.get('edit_numero'),
                'tasa_base':    request.POST.get('edit_tasa'),
                'activa':       request.POST.get('activa'),
            }
            admin_crud.update_cuota_plan(cuota_id, data)
            messages.success(request, 'Plan actualizado.')

        elif 'update_cuota_override' in request.POST:
            cuota_id = request.POST.get('cuota_id')
            
            # UN solo checkbox controla AMBOS (comisión y arancel)
            iva_general_aplica = 'iva_general_aplica' in request.POST
            
            data = {
                'iva_override':              request.POST.get('iva_override', '').strip() or None,
                'iva_financiacion_override': request.POST.get('iva_financiacion_override', '').strip() or None,
                'com_credito_override':      request.POST.get('com_credito_override', '').strip() or None,
                'com_debito_override':       request.POST.get('com_debito_override', '').strip() or None,
                'arancel_credito_override':  request.POST.get('arancel_credito_override', '').strip() or None,
                'arancel_debito_override':   request.POST.get('arancel_debito_override', '').strip() or None,
                # El toggle único IVA 21% controla ambos campos del modelo
                'comision_aplica_iva': iva_general_aplica,
                'arancel_aplica_iva':  iva_general_aplica,
                'tasa_aplica_iva_fin': 'tasa_aplica_iva_fin' in request.POST,
            }
            ok, err = admin_crud.update_cuota_override(cuota_id, data)
            if ok:
                messages.success(request, 'Configuración personalizada guardada correctamente.')
            else:
                messages.error(request, err or 'Error al guardar la configuración.')

        elif 'delete_cuota' in request.POST:
            admin_crud.delete_cuota_plan(request.POST.get('delete_id'))
            messages.warning(request, 'Plan financiero eliminado.')

        return redirect('configuracion_financiera')

    # ── GET: Carga ─────────────────────────────────────────────────────
    config = admin_crud.get_or_create_config()
    cuotas = admin_crud.list_cuotas_config()

    # Valores globales para las tarjetas de resumen (usan config global + IVA 21%)
    iva_global_f = Decimal(str(config.iva)) / 100
    com_pt_cred_iva  = Decimal(str(config.comision_pago_tech))           * (1 + iva_global_f)
    arancel_cred_iva = Decimal(str(config.arancel_plataforma))           * (1 + iva_global_f)
    com_pt_deb_iva   = Decimal(str(config.comision_pago_tech_debito))    * (1 + iva_global_f)
    arancel_deb_iva  = Decimal(str(config.arancel_plataforma_debito))    * (1 + iva_global_f)

    # ── Proyecciones con valores efectivos por plan ────────────────────
    proyecciones = []
    for c in cuotas:
        iva_val     = c.iva_override              if c.iva_override is not None              else config.iva
        iva_fin_val = c.iva_financiacion_override if c.iva_financiacion_override is not None else config.iva_financiacion
        com_cred    = c.com_credito_override      if c.com_credito_override is not None      else config.comision_pago_tech
        ar_cred     = c.arancel_credito_override  if c.arancel_credito_override is not None  else config.arancel_plataforma

        iva_f     = Decimal(str(iva_val))     / 100
        iva_fin_f = Decimal(str(iva_fin_val)) / 100

        # Cada toggle es independiente
        tasa_eff = Decimal(str(c.tasa_base)) * (1 + iva_fin_f) if c.tasa_aplica_iva_fin  else Decimal(str(c.tasa_base))
        com_eff  = Decimal(str(com_cred))    * (1 + iva_f)     if c.comision_aplica_iva  else Decimal(str(com_cred))
        ar_eff   = Decimal(str(ar_cred))     * (1 + iva_f)     if c.comision_aplica_iva  else Decimal(str(ar_cred))

        total_descuentos      = tasa_eff + com_eff + ar_eff
        divisor_transaccional = 1 - (total_descuentos / 100)

        try:
            coeficiente = Decimal('1') / divisor_transaccional if divisor_transaccional > 0 else Decimal('0')
        except Exception:
            coeficiente = Decimal('0')

        proyecciones.append({
            'obj':              c,
            'total_descuentos': total_descuentos.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP),
            'coeficiente':      coeficiente.quantize(Decimal('0.000000'),    rounding=ROUND_HALF_UP),
        })

    context = {
        'user':             user_admin,
        'config':           config,
        'proyecciones':     proyecciones,
        'com_pt_cred_iva':  com_pt_cred_iva,
        'arancel_cred_iva': arancel_cred_iva,
        'com_pt_deb_iva':   com_pt_deb_iva,
        'arancel_deb_iva':  arancel_deb_iva,
    }
    return render(request, 'configuracion_financiera.html', context)