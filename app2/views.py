from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from .models import User_admin
from . import crud as admin_crud
from app1 import models as app1_models
from django.core.paginator import Paginator
from decimal import Decimal, ROUND_HALF_UP
from utils.email_utils import mail
from django.urls import reverse
import logging
from app1.models import Cliente

logger = logging.getLogger(__name__)

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
                'password': request.POST.get('edit_password'), 
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
        'clientes': page_obj,        
        'q': q,
        'total_users': total_users_aprobados, 
        'activos_count': activos_count,      
        'blocked_count': blocked_count,
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
                # --- Enviar correo de bienvenida al cliente ---
                try:
                    cliente = Cliente.objects.get(id=approve_id)
                    if cliente.email:
                        # Construir URL de login
                        login_url = request.build_absolute_uri(reverse('login_cliente'))
                        
                        # Enviar correo usando tu función mail
                        resultado = mail(
                            asunto="¡Tu cuenta ha sido aprobada! - PagoTech",
                            destinatarios=[cliente.email],
                            template_html="emails/cuenta_aprobada.html",
                            contexto={
                                "nombre": cliente.nombre,
                                "email": cliente.email,
                                "login_url": login_url,
                            }
                        )
                        if resultado:
                            logger.info(f"Correo de aprobación enviado a {cliente.email}")
                        else:
                            logger.warning(f"No se pudo enviar correo de aprobación a {cliente.email}")
                    else:
                        logger.warning(f"Cliente {approve_id} no tiene email, no se envió notificación")
                except Cliente.DoesNotExist:
                    logger.error(f"No se encontró cliente con id {approve_id} para enviar correo")
                except Exception as e:
                    logger.error(f"Error inesperado al enviar correo de aprobación: {e}")

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

def links_pagos(request):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        return redirect('login')

    user_admin = User_admin.objects.get(id=user_id)

    from app1.models import LinkPago, Cliente
    from django.db.models import Q, Sum
    from django.utils.dateparse import parse_date

    # ── Parámetros de filtrado ────────────────────────────────────────
    q            = request.GET.get('q', '').strip()
    fecha_desde  = request.GET.get('fecha_desde', '').strip()
    fecha_hasta  = request.GET.get('fecha_hasta', '').strip()
    estado       = request.GET.get('estado', '').strip()       # filtra por status_detalle
    tipo_tarjeta = request.GET.get('tipo_tarjeta', '').strip()
    cliente_id   = request.GET.get('cliente_id', '').strip()
    pagado_f     = request.GET.get('pagado', '').strip()       # '1', '0' o ''
    orden        = request.GET.get('orden', '-created_at')

    # ── QuerySet base ─────────────────────────────────────────────────
    links_qs = LinkPago.objects.select_related('cliente').all()

    # ── Filtros ───────────────────────────────────────────────────────
    if q:
        links_qs = links_qs.filter(
            Q(cliente__nombre__icontains=q) |
            Q(cliente__email__icontains=q)  |
            Q(descripcion__icontains=q)     |
            Q(order_id__icontains=q)
        )

    if cliente_id:
        links_qs = links_qs.filter(cliente_id=cliente_id)

    if fecha_desde:
        d = parse_date(fecha_desde)
        if d:
            links_qs = links_qs.filter(created_at__date__gte=d)

    if fecha_hasta:
        d = parse_date(fecha_hasta)
        if d:
            links_qs = links_qs.filter(created_at__date__lte=d)

    if estado:
        links_qs = links_qs.filter(status_detalle=estado)   # ← corregido

    if tipo_tarjeta:
        links_qs = links_qs.filter(tipo_tarjeta=tipo_tarjeta)

    if pagado_f == '1':
        links_qs = links_qs.filter(pagado=True)
    elif pagado_f == '0':
        links_qs = links_qs.filter(pagado=False)

    # ── Ordenamiento (whitelist) ──────────────────────────────────────
    ORDENES_PERMITIDOS = {
        '-created_at', 'created_at',
        '-monto', 'monto',
        'cliente__nombre', '-cliente__nombre',
        'status_detalle',                        # ← corregido
    }
    if orden not in ORDENES_PERMITIDOS:
        orden = '-created_at'
    links_qs = links_qs.order_by(orden)

    # ── Estadísticas ──────────────────────────────────────────────────
    total_links      = links_qs.count()
    total_pagados    = links_qs.filter(pagado=True).count()   # ← usa booleano
    total_pendientes = links_qs.filter(pagado=False).count()
    monto_total      = links_qs.filter(pagado=True).aggregate(
                           total=Sum('monto'))['total'] or 0

    clientes_lista = Cliente.objects.filter(
        aprobado=True
    ).order_by('nombre').only('id', 'nombre')

    # ── Paginación ────────────────────────────────────────────────────
    per_page_options = [10, 25, 50, 100, 500]
    try:
        per_page = int(request.GET.get('per_page', 15))
        if per_page not in per_page_options:
            per_page = 10
    except (ValueError, TypeError):
        per_page = 10

    paginator = Paginator(links_qs, per_page)
    
    page_obj  = paginator.get_page(request.GET.get('page'))

    get_params = request.GET.copy()
    get_params.pop('page', None)

    return render(request, 'links_pagos.html', {
        'user':             user_admin,
        'links':            page_obj,
        'clientes_lista':   clientes_lista,
        'q':                q,
        'fecha_desde':      fecha_desde,
        'fecha_hasta':      fecha_hasta,
        'estado':           estado,
        'tipo_tarjeta':     tipo_tarjeta,
        'cliente_id':       cliente_id,
        'pagado_f':         pagado_f,
        'orden':            orden,
        'total_links':      total_links,
        'total_pagados':    total_pagados,
        'total_pendientes': total_pendientes,
        'monto_total':      monto_total,
        'get_params':       get_params.urlencode(),
        'per_page':         per_page,
        'per_page_options': per_page_options,
    })
    
def configuracion_financiera(request):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        return redirect('login')

    user_admin = User_admin.objects.get(id=user_id)

    if request.method == 'POST':

        if 'update_general' in request.POST:
            # — sin cambios —
            data = {
                'iva':                       request.POST.get('iva'),
                'iva_financiacion':          request.POST.get('iva_financiacion'),
                'comision_pago_tech':        request.POST.get('comision_pago_tech'),
                'arancel_plataforma':        request.POST.get('arancel_plataforma'),
                'comision_pago_tech_debito': request.POST.get('comision_pago_tech_debito'),
                'arancel_plataforma_debito': request.POST.get('arancel_plataforma_debito'),
            }
            admin_crud.update_financiero(data)
            messages.success(request, 'Parámetros base actualizados correctamente.')

        elif 'add_cuota' in request.POST:
            # Recibe lista de IDs (puede estar vacía)
            usuarios_ids = request.POST.getlist('new_usuarios_asignados')
            data = {
                'numero_cuota':      request.POST.get('new_numero'),
                'nombre':            request.POST.get('new_nombre'),
                'tasa_base':         request.POST.get('new_tasa'),
                'alcance':           request.POST.get('new_alcance', 'global'),
                'usuarios_asignados': usuarios_ids,
            }
            admin_crud.create_cuota_plan(data)
            messages.success(request, 'Nuevo plan añadido.')

        elif 'update_cuota' in request.POST:
            cuota_id     = request.POST.get('cuota_id')
            
            data = {
                'nombre':            request.POST.get('edit_nombre'),
                'numero_cuota':      request.POST.get('edit_numero'),
                'tasa_base':         request.POST.get('edit_tasa'),
                'activa':            request.POST.get('activa'),
                'alcance':           request.POST.get('edit_alcance', 'global'),
                
            }
            admin_crud.update_cuota_plan(cuota_id, data)
            messages.success(request, 'Plan actualizado.')

        elif 'update_cuota_override' in request.POST:
            cuota_id = request.POST.get('cuota_id')
            iva_general_aplica = 'iva_general_aplica' in request.POST
            usuarios_ids = request.POST.getlist('usuarios_asignados')  # ← AGREGAR

            data = {
                'iva_override':              request.POST.get('iva_override', '').strip() or None,
                'iva_financiacion_override': request.POST.get('iva_financiacion_override', '').strip() or None,
                'com_credito_override':      request.POST.get('com_credito_override', '').strip() or None,
                'com_debito_override':       request.POST.get('com_debito_override', '').strip() or None,
                'arancel_credito_override':  request.POST.get('arancel_credito_override', '').strip() or None,
                'arancel_debito_override':   request.POST.get('arancel_debito_override', '').strip() or None,
                'comision_aplica_iva':       iva_general_aplica,
                'arancel_aplica_iva':        iva_general_aplica,
                'tasa_aplica_iva_fin':       'tasa_aplica_iva_fin' in request.POST,
                'alcance':                   request.POST.get('alcance', 'global'),   # ← AGREGAR
                'usuarios_asignados':        usuarios_ids,                             # ← AGREGAR
            }
            ok, err = admin_crud.update_cuota_override(cuota_id, data)
            if ok:
                messages.success(request, 'Configuración personalizada guardada.')
            else:
                messages.error(request, err or 'Error al guardar.')

        elif 'delete_cuota' in request.POST:
            admin_crud.delete_cuota_plan(request.POST.get('delete_id'))
            messages.warning(request, 'Plan financiero eliminado.')

        return redirect('configuracion_financiera')

    # ── GET ────────────────────────────────────────────────────────────
    from app1.models import Cliente
    config  = admin_crud.get_or_create_config()
    cuotas  = admin_crud.list_cuotas_config()
    clientes_todos = Cliente.objects.filter(aprobado=True, bloqueado=False).order_by('nombre')

    iva_global_f     = Decimal(str(config.iva)) / 100
    com_pt_cred_iva  = Decimal(str(config.comision_pago_tech))        * (1 + iva_global_f)
    arancel_cred_iva = Decimal(str(config.arancel_plataforma))        * (1 + iva_global_f)
    com_pt_deb_iva   = Decimal(str(config.comision_pago_tech_debito)) * (1 + iva_global_f)
    arancel_deb_iva  = Decimal(str(config.arancel_plataforma_debito)) * (1 + iva_global_f)

    proyecciones = []
    for c in cuotas:
        iva_val     = c.iva_override              if c.iva_override is not None              else config.iva
        iva_fin_val = c.iva_financiacion_override if c.iva_financiacion_override is not None else config.iva_financiacion
        com_cred    = c.com_credito_override      if c.com_credito_override is not None      else config.comision_pago_tech
        ar_cred     = c.arancel_credito_override  if c.arancel_credito_override is not None  else config.arancel_plataforma

        iva_f     = Decimal(str(iva_val))     / 100
        iva_fin_f = Decimal(str(iva_fin_val)) / 100

        tasa_eff = Decimal(str(c.tasa_base)) * (1 + iva_fin_f) if c.tasa_aplica_iva_fin else Decimal(str(c.tasa_base))
        com_eff  = Decimal(str(com_cred))    * (1 + iva_f)     if c.comision_aplica_iva  else Decimal(str(com_cred))
        ar_eff   = Decimal(str(ar_cred))     * (1 + iva_f)     if c.comision_aplica_iva  else Decimal(str(ar_cred))

        total_descuentos      = tasa_eff + com_eff + ar_eff
        divisor_transaccional = 1 - (total_descuentos / 100)

        try:
            coeficiente = Decimal('1') / divisor_transaccional if divisor_transaccional > 0 else Decimal('0')
        except Exception:
            coeficiente = Decimal('0')

        # IDs ya asignados (para pre-marcar checkboxes en el template)
        asignados_ids = list(c.usuarios_asignados.values_list('id', flat=True))

        proyecciones.append({
            'obj':              c,
            'total_descuentos': total_descuentos.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP),
            'coeficiente':      coeficiente.quantize(Decimal('0.000000'),    rounding=ROUND_HALF_UP),
            'asignados_ids':    asignados_ids,
        })

    context = {
        'user':             user_admin,
        'config':           config,
        'proyecciones':     proyecciones,
        'clientes_todos':   clientes_todos,
        'com_pt_cred_iva':  com_pt_cred_iva,
        'arancel_cred_iva': arancel_cred_iva,
        'com_pt_deb_iva':   com_pt_deb_iva,
        'arancel_deb_iva':  arancel_deb_iva,
    }
    return render(request, 'configuracion_financiera.html', context)

def login_as_cliente(request, cliente_id):
    user_admin_id = request.session.get('user_admin_id')
    if not user_admin_id:
        return redirect('login')

    from app1.models import Cliente
    try:
        cliente = Cliente.objects.get(id=cliente_id, aprobado=True, bloqueado=False)
    except Cliente.DoesNotExist:
        messages.error(request, 'Cliente no encontrado o no disponible.')
        return redirect('links_pagos')

    # Guardamos el admin_id para poder volver después
    request.session['user_id'] = cliente.id
    request.session['impersonando'] = True
    request.session['admin_origen_id'] = user_admin_id

    logger.info(f"Admin id={user_admin_id} ingresó como cliente id={cliente.id} nombre={cliente.nombre}")
    messages.success(request, f'Estás viendo el sistema como {cliente.nombre}')
    return redirect('dashboard')

def volver_a_admin(request):
    admin_id = request.session.get('admin_origen_id')
    if not admin_id:
        return redirect('login')

    # Limpiamos la sesión de cliente y restauramos la de admin
    request.session.flush()
    request.session['user_admin_id'] = admin_id
    request.session['impersonando'] = False

    messages.success(request, 'Volviste al panel de administración.')
    return redirect('links_pagos')