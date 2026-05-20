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
from django.http import HttpResponse, Http404, JsonResponse
from app1.views import _get_or_create_sesion_activa

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
            usuarios_ids = request.POST.getlist('new_usuarios_asignados')
            data = {
                'numero_cuota':       request.POST.get('new_numero'),
                'nombre':             request.POST.get('new_nombre'),
                'tasa_base':          request.POST.get('new_tasa'),
                'alcance':            request.POST.get('new_alcance', 'global'),
                'usuarios_asignados': usuarios_ids,
                'tarjeta_custom_id':  request.POST.get('new_tarjeta_custom_id') or None,
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
        elif 'add_tarjeta' in request.POST:
            data = {
                'nombre':        request.POST.get('tc_nombre', '').strip(),
                'payzen_code':   request.POST.get('tc_payzen_code', '').strip().upper(),
                'comision':      request.POST.get('tc_comision', 0),
                'arancel':       request.POST.get('tc_arancel', 0),
                'iva':           request.POST.get('tc_iva', 21),
                'aplica_iva':    'tc_aplica_iva' in request.POST,
                'acepta_cuotas': 'tc_acepta_cuotas' in request.POST,
                'icono':         request.POST.get('tc_icono', 'fas fa-credit-card').strip(),
                'orden':         request.POST.get('tc_orden', 0),
            }
            tc, err = admin_crud.create_tarjeta_custom(data)
            if tc:
                messages.success(request, f'Tarjeta "{tc.nombre}" creada correctamente.')
            else:
                messages.error(request, err or 'Error al crear tarjeta.')

        elif 'update_tarjeta' in request.POST:
            tc_id = request.POST.get('tc_id')
            data = {
                'nombre':        request.POST.get('tc_nombre', '').strip(),
                'payzen_code':   request.POST.get('tc_payzen_code', '').strip().upper(),
                'comision':      request.POST.get('tc_comision', 0),
                'arancel':       request.POST.get('tc_arancel', 0),
                'iva':           request.POST.get('tc_iva', 21),
                'aplica_iva':    'tc_aplica_iva' in request.POST,
                'acepta_cuotas': 'tc_acepta_cuotas' in request.POST,
                'activa':        'tc_activa' in request.POST,
                'icono':         request.POST.get('tc_icono', 'fas fa-credit-card').strip(),
                'orden':         request.POST.get('tc_orden', 0),
            }
            ok, err = admin_crud.update_tarjeta_custom(tc_id, data)
            if ok:
                messages.success(request, 'Tarjeta actualizada.')
            else:
                messages.error(request, err)

        elif 'delete_tarjeta' in request.POST:
            ok, err = admin_crud.delete_tarjeta_custom(request.POST.get('tc_delete_id'))
            if ok:
                messages.success(request, 'Tarjeta eliminada.')
            else:
                messages.error(request, err)

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
        
        tarjetas_custom = admin_crud.list_tarjetas_custom()

    context = {
        'user':             user_admin,
        'config':           config,
        'proyecciones':     proyecciones,
        'clientes_todos':   clientes_todos,
        'com_pt_cred_iva':  com_pt_cred_iva,
        'arancel_cred_iva': arancel_cred_iva,
        'com_pt_deb_iva':   com_pt_deb_iva,
        'arancel_deb_iva':  arancel_deb_iva,
        'tarjetas_custom': tarjetas_custom,
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

def liquidaciones(request):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        return redirect('login')

    user_admin = User_admin.objects.get(id=user_id)

    from app1.models import LinkPago, Cliente
    from django.db.models import Q, Sum
    from django.utils.dateparse import parse_date

    # Filtros
    q            = request.GET.get('q', '').strip()
    fecha_desde  = request.GET.get('fecha_desde', '').strip()
    fecha_hasta  = request.GET.get('fecha_hasta', '').strip()
    tipo_tarjeta = request.GET.get('tipo_tarjeta', '').strip()
    cliente_id   = request.GET.get('cliente_id', '').strip()
    orden        = request.GET.get('orden', '-created_at')

    # Solo links pagados
    qs = LinkPago.objects.select_related('cliente').filter(pagado=True)

    if q:
        qs = qs.filter(
            Q(cliente__nombre__icontains=q) |
            Q(cliente__email__icontains=q)  |
            Q(order_id__icontains=q)        |
            Q(descripcion__icontains=q)
        )

    if cliente_id:
        qs = qs.filter(cliente_id=cliente_id)

    if fecha_desde:
        d = parse_date(fecha_desde)
        if d:
            qs = qs.filter(created_at__date__gte=d)

    if fecha_hasta:
        d = parse_date(fecha_hasta)
        if d:
            qs = qs.filter(created_at__date__lte=d)

    if tipo_tarjeta:
        qs = qs.filter(tipo_tarjeta=tipo_tarjeta)

    ORDENES_PERMITIDOS = {
        '-created_at', 'created_at',
        '-monto', 'monto',
        '-receiver_amount', 'receiver_amount',
        'cliente__nombre', '-cliente__nombre',
    }
    if orden not in ORDENES_PERMITIDOS:
        orden = '-created_at'
    qs = qs.order_by(orden)

    # Totalizadores
    totales = qs.aggregate(
        suma_bruto    = Sum('monto'),
        suma_neto     = Sum('receiver_amount'),
        suma_comision = Sum('commission_amount'),
    )
    suma_bruto    = totales['suma_bruto']    or 0
    suma_neto     = totales['suma_neto']     or 0
    suma_comision = totales['suma_comision'] or 0
    total_ops     = qs.count()

    clientes_lista = Cliente.objects.filter(aprobado=True).order_by('nombre').only('id', 'nombre')

    # Exportar CSV
    if request.GET.get('exportar') == 'csv':
        import csv
        from django.http import HttpResponse as HR
        response_csv = HR(content_type='text/csv')
        response_csv['Content-Disposition'] = 'attachment; filename="liquidaciones.csv"'
        writer = csv.writer(response_csv)
        writer.writerow([
            'Fecha', 'Comercio', 'Email', 'Descripcion',
            'Tipo', 'Cuotas', 'Monto bruto', 'Comision',
            'Monto neto', 'Orden ID', 'Cod. autorizacion'
        ])
        for l in qs:
            writer.writerow([
                l.created_at.strftime('%d/%m/%Y %H:%M'),
                l.cliente.nombre,
                l.cliente.email or '',
                l.descripcion or '',
                l.get_tipo_tarjeta_display(),
                l.cuotas_elegidas,
                l.monto,
                l.commission_amount,
                l.receiver_amount,
                l.order_id,
                l.auth_code or '',
            ])
        return response_csv

    # Paginacion
    per_page_options = [10, 25, 50, 100]
    try:
        per_page = int(request.GET.get('per_page', 25))
        if per_page not in per_page_options:
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(request.GET.get('page'))

    get_params = request.GET.copy()
    get_params.pop('page', None)
    get_params.pop('exportar', None)

    return render(request, 'liquidaciones.html', {
        'user':            user_admin,
        'links':           page_obj,
        'clientes_lista':  clientes_lista,
        'q':               q,
        'fecha_desde':     fecha_desde,
        'fecha_hasta':     fecha_hasta,
        'tipo_tarjeta':    tipo_tarjeta,
        'cliente_id':      cliente_id,
        'orden':           orden,
        'suma_bruto':      suma_bruto,
        'suma_neto':       suma_neto,
        'suma_comision':   suma_comision,
        'total_ops':       total_ops,
        'get_params':      get_params.urlencode(),
        'per_page':        per_page,
        'per_page_options': per_page_options,
    })
    
def mensajes_admin(request, cliente_id=None):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        return redirect('login')

    user_admin = User_admin.objects.get(id=user_id)

    from app1.models import MensajeInterno, Cliente, SesionChat

    # Lista de comercios con mensajes — con conteo de no leidos
    from django.db.models import Count, Q
    # Solo comercios con sesion activa (no cerrada)
    clientes_con_sesion_activa = SesionChat.objects.filter(
        cerrada=False
    ).values_list('cliente_id', flat=True)

    comercios = Cliente.objects.filter(
        id__in=clientes_con_sesion_activa
    ).annotate(
        total_mensajes = Count('mensajes', filter=Q(mensajes__sesion__cerrada=False)),
        no_leidos      = Count('mensajes', filter=Q(
            mensajes__es_admin=False,
            mensajes__leido=False,
            mensajes__sesion__cerrada=False
        ))
    ).distinct().order_by('-no_leidos', 'nombre')

    mensajes   = None
    cliente_sel = None

    if cliente_id:
        try:
            cliente_sel = Cliente.objects.get(id=cliente_id)
            # Marcar como leidos los mensajes del comercio
            MensajeInterno.objects.filter(
                cliente=cliente_sel, es_admin=False, leido=False
            ).update(leido=True)
            mensajes = MensajeInterno.objects.filter(
                cliente=cliente_sel
            ).select_related('admin', 'link_pago')
        except Cliente.DoesNotExist:
            return redirect('mensajes_admin')

    total_no_leidos = MensajeInterno.objects.filter(es_admin=False, leido=False).count()
    
    ultimo_id_admin = 0
    if mensajes is not None:
        last = mensajes.last()
        if last:
            ultimo_id_admin = last.id

    return render(request, 'mensajes_admin.html', {
        'user':             user_admin,
        'comercios':        comercios,
        'mensajes':         mensajes,
        'cliente_sel':      cliente_sel,
        'total_no_leidos':  total_no_leidos,
        'ultimo_id_admin': ultimo_id_admin,
    })


def responder_mensaje_admin(request, cliente_id):
    user_id = request.session.get('user_admin_id')
    if not user_id or request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'No autorizado'}, status=401)

    user_admin = User_admin.objects.get(id=user_id)

    from app1.models import MensajeInterno, Cliente
    import threading

    texto = request.POST.get('texto', '').strip()
    if not texto:
        return JsonResponse({'ok': False, 'error': 'La respuesta no puede estar vacia.'})

    try:
        cliente = Cliente.objects.get(id=cliente_id)
    except Cliente.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Cliente no encontrado.'}, status=404)


    sesion = _get_or_create_sesion_activa(cliente)

    msg = MensajeInterno.objects.create(
        cliente  = cliente,
        admin    = user_admin,
        texto    = texto,
        es_admin = True,
        leido    = False,
        sesion   = sesion,
    )
    logger.info(f"Admin id={user_admin.id} respondio a cliente={cliente_id} msg_id={msg.id}")

    def enviar_email_con_delay():
        import time
        from django.utils import timezone
        from datetime import timedelta

        time.sleep(300)

        # Verificar si el cliente estuvo activo en los ultimos 5 minutos
        try:
            from app1.models import Cliente as C
            cliente_fresco = C.objects.get(id=cliente_id)
            UMBRAL = timezone.now() - timedelta(minutes=5)

            if (cliente_fresco.ultima_actividad_mensajes and
                    cliente_fresco.ultima_actividad_mensajes >= UMBRAL):
                logger.info(f"Email respuesta admin omitido — cliente activo en pagina — msg_id={msg.id}")
                return
        except Exception:
            pass

        try:
            from utils.email_utils import mail
            from django.conf import settings
            if cliente.email:
                mail(
                    asunto="Tienes una respuesta de Pago Tech",
                    destinatarios=[cliente.email],
                    template_html='emails/respuesta_admin.html',
                    contexto={
                        'cliente_nombre': cliente.nombre.title(),
                        'texto':          texto,
                        'fecha':          msg.fecha.strftime('%d/%m/%Y %H:%M'),
                        'panel_url':      f'{settings.SITE_URL}/mensajes/' if hasattr(settings, 'SITE_URL') else '/mensajes/',
                    },
                )
        except Exception as e:
            logger.error(f"Error enviando email respuesta admin cliente={cliente_id}: {e}")

    threading.Thread(target=enviar_email_con_delay, daemon=True).start()

    return JsonResponse({
        'ok': True,
        'msg': {
            'id':    msg.id,           # ← asegurarse que está
            'texto': texto,
            'fecha': msg.fecha.strftime('%d/%m/%Y %H:%M'),
        }
    })
    
def poll_mensajes_admin(request, cliente_id):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        return JsonResponse({'mensajes': []})

    from app1.models import MensajeInterno, Cliente

    ultimo_id = int(request.GET.get('ultimo_id', 0))

    try:
        cliente = Cliente.objects.get(id=cliente_id)
    except Cliente.DoesNotExist:
        return JsonResponse({'mensajes': []})

    nuevos = MensajeInterno.objects.filter(
        cliente=cliente,
        id__gt=ultimo_id
    ).select_related('link_pago').order_by('id')

    # Marcar mensajes del comercio como leidos
    nuevos.filter(es_admin=False, leido=False).update(leido=True)

    total_no_leidos = MensajeInterno.objects.filter(
        es_admin=False, leido=False
    ).count()

    return JsonResponse({
        'mensajes': [
            {
                'id':       m.id,
                'texto':    m.texto,
                'fecha':    m.fecha.strftime('%d/%m/%Y %H:%M'),
                'es_admin': m.es_admin,
                'order_id': m.link_pago.order_id if m.link_pago else None,
                'link_id':  m.link_pago.id if m.link_pago else None,
            }
            for m in nuevos
        ],
        'total_no_leidos': total_no_leidos,
    })
    
def finalizar_chat_admin(request, cliente_id):
    user_id = request.session.get('user_admin_id')
    if not user_id or request.method != 'POST':
        return JsonResponse({'ok': False}, status=400)

    from app1.models import MensajeInterno, Cliente, SesionChat
    from django.utils import timezone
    import threading

    try:
        cliente = Cliente.objects.get(id=cliente_id)
    except Cliente.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Cliente no encontrado.'}, status=404)

    sesion = SesionChat.objects.filter(cliente=cliente, cerrada=False).first()
    if not sesion:
        return JsonResponse({'ok': False, 'error': 'No hay conversacion activa para finalizar.'})

    mensajes_qs = MensajeInterno.objects.filter(sesion=sesion).order_by('fecha')
    if not mensajes_qs.exists():
        return JsonResponse({'ok': False, 'error': 'La sesion no tiene mensajes.'})

    sesion.cerrada      = True
    sesion.fecha_cierre = timezone.now()
    sesion.save()

    # Marcar como cerrada
    mensajes_qs.update(conversacion_cerrada=True)

    # Evaluar antes del thread
    mensajes_lista = [
        {
            'texto':    m.texto,
            'fecha':    m.fecha.strftime('%d/%m/%Y %H:%M'),
            'es_admin': m.es_admin,
        }
        for m in mensajes_qs
    ]
    total          = len(mensajes_lista)
    fecha_cierre   = timezone.now().strftime('%d/%m/%Y %H:%M')
    cliente_nombre = cliente.nombre.title()
    cliente_email  = cliente.email

    def enviar_resumenes():
        try:
            from utils.email_utils import mail_con_pdf
            from django.template.loader import render_to_string
            from weasyprint import HTML

            # Generar PDF
            html_pdf = render_to_string('emails/resumen_chat_pdf.html', {
                'cliente_nombre': cliente_nombre,
                'fecha_cierre':   fecha_cierre,
                'total_mensajes': total,
                'mensajes':       mensajes_lista,
            })
            pdf_bytes = HTML(string=html_pdf).write_pdf()
            pdf_nombre = f"resumen_chat_{cliente_nombre.replace(' ', '_')}_{fecha_cierre[:10].replace('/', '-')}.pdf"

            # Contexto para el email
            ctx_cliente = {
                'cliente_nombre': cliente_nombre,
                'fecha_cierre':   fecha_cierre,
                'total_mensajes': total,
                'es_admin':       False,
            }
            ctx_admin = {
                'cliente_nombre': cliente_nombre,
                'fecha_cierre':   fecha_cierre,
                'total_mensajes': total,
                'es_admin':       True,
            }

            # Email al comercio
            if cliente_email:
                mail_con_pdf(
                    asunto=f"Resumen de tu conversacion con Pago Tech — {fecha_cierre[:10]}",
                    destinatarios=[cliente_email],
                    template_html='emails/resumen_chat_email.html',
                    contexto=ctx_cliente,
                    pdf_bytes=pdf_bytes,
                    pdf_nombre=pdf_nombre,
                )

            # Email al admin
            from django.conf import settings
            destinatarios_admin = getattr(settings, 'EMAIL_RECEPTORES', None)
            if not destinatarios_admin:
                destinatarios_admin = [getattr(settings, 'EMAIL_RECEPTOR', 'pagotechnotificaciones@gmail.com')]

            mail_con_pdf(
                asunto=f"Chat finalizado con {cliente_nombre} — {fecha_cierre[:10]}",
                destinatarios=destinatarios_admin,
                template_html='emails/resumen_chat_email.html',
                contexto=ctx_admin,
                pdf_bytes=pdf_bytes,
                pdf_nombre=pdf_nombre,
            )

        except Exception as e:
            logger.error(f"Error enviando resumen con PDF: {e}")

    threading.Thread(target=enviar_resumenes, daemon=True).start()

    return JsonResponse({
        'ok': True,
        'mensaje': 'Resumen enviado por email.',
        'fecha_cierre': fecha_cierre,
    })

def ping_mensajes_admin(request):
    user_id = request.session.get('user_admin_id')
    if not user_id or request.method != 'POST':
        return JsonResponse({'ok': False})
    from django.utils import timezone
    User_admin.objects.filter(id=user_id).update(
        ultima_actividad_mensajes=timezone.now()
    )
    return JsonResponse({'ok': True})

def iniciar_chat_admin(request, cliente_id):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        return redirect('login')

    from app1.models import Cliente
    try:
        Cliente.objects.get(id=cliente_id, aprobado=True)
    except Cliente.DoesNotExist:
        messages.error(request, 'Comercio no encontrado.')
        return redirect('gestion_usuarios')

    return redirect('mensajes_admin_cliente', cliente_id=cliente_id)

def terminos_condiciones(request):
    user_id = request.session.get('user_admin_id')
    if not user_id:
        return redirect('login')

    user_admin = User_admin.objects.get(id=user_id)
    from .models import TerminosCondiciones

    tyc_activo = TerminosCondiciones.objects.filter(activa=True).first()
    historial  = TerminosCondiciones.objects.all()[:10]

    if request.method == 'POST':
        accion   = request.POST.get('accion')
        contenido = request.POST.get('contenido', '').strip()
        version  = request.POST.get('version', '').strip()

        if accion == 'guardar' and contenido and version:
            # Verificar si la versión ya existe
            if TerminosCondiciones.objects.filter(version=version).exclude(
                pk=TerminosCondiciones.objects.filter(version=version).values_list('pk', flat=True).first()
            ).exists():
                messages.error(request, f'La versión {version} ya existe.')
            else:
                tyc, created = TerminosCondiciones.objects.update_or_create(
                    version=version,
                    defaults={'contenido': contenido, 'activa': True}
                )
                # Forzar re-aceptación si la versión cambió
                from app1.models import Cliente
                Cliente.objects.exclude(version_tyc=version).update(
                    acepto_tyc=False, version_tyc=None
                )
                messages.success(
                    request,
                    f'T&C v{version} guardados y activados. '
                    f'Todos los comercios deberán re-aceptar.'
                )
                return redirect('terminos_admin')

        elif accion == 'activar':
            tyc_id = request.POST.get('tyc_id')
            try:
                tyc = TerminosCondiciones.objects.get(id=tyc_id)
                tyc.activa = True
                tyc.save()
                from app1.models import Cliente
                Cliente.objects.exclude(version_tyc=tyc.version).update(
                    acepto_tyc=False, version_tyc=None
                )
                messages.success(request, f'T&C v{tyc.version} activados.')
            except TerminosCondiciones.DoesNotExist:
                messages.error(request, 'Versión no encontrada.')
            return redirect('terminos_admin')

    # Generar próxima versión sugerida
    if tyc_activo:
        try:
            partes  = tyc_activo.version.split('.')
            nueva_v = f"{partes[0]}.{int(partes[1]) + 1}" if len(partes) == 2 else f"{tyc_activo.version}.1"
        except Exception:
            nueva_v = "2.0"
    else:
        nueva_v = "1.0"

    return render(request, 'terminos_admin.html', {
        'user':      user_admin,
        'tyc_activo': tyc_activo,
        'historial':  historial,
        'nueva_v':    nueva_v,
    })