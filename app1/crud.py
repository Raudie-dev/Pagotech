from typing import Optional, Tuple, List, Dict, Any
from django.db import IntegrityError
from django.contrib.auth.hashers import make_password
from decimal import Decimal, InvalidOperation
import uuid
from django.template.loader import render_to_string

from .models import Cliente, LinkPago

def create_cliente(nombre: str, password: str, email: Optional[str]=None, telefono: Optional[str]=None) -> Tuple[Optional[Cliente], List[str]]:
    errors: List[str] = []
    nombre = (nombre or '').strip()
    if not nombre:
        errors.append('El nombre es obligatorio.')
    if not password:
        errors.append('La contraseña es obligatoria.')
    if Cliente.objects.filter(nombre=nombre).exists():
        errors.append('Ya existe un cliente con ese nombre.')
    if email and Cliente.objects.filter(email=email).exists():
        errors.append('El correo ya está en uso.')
    if errors:
        return None, errors
    try:
        cliente = Cliente(
            nombre=nombre,
            password=make_password(password),
            email=email or None,
            telefono=telefono or None,
            aprobado=False,
        )
        cliente.save()
        return cliente, []
    except IntegrityError:
        return None, ['Error al crear el cliente.']

def get_cliente(pk: Any) -> Optional[Cliente]:
    try:
        return Cliente.objects.get(pk=pk)
    except Cliente.DoesNotExist:
        return None

def update_cliente(pk: Any, data: Dict[str, Any]) -> List[str]:
    cliente = get_cliente(pk)
    if not cliente:
        return ['Cliente no encontrado.']

    nombre = data.get('nombre')
    if nombre:
        nombre = nombre.strip()
        if nombre != cliente.nombre and Cliente.objects.filter(nombre=nombre).exclude(pk=pk).exists():
            return ['El nombre ya está en uso por otro cliente.']
        cliente.nombre = nombre

    email = data.get('email')
    if email is not None:
        email = email.strip() or None
        if email != cliente.email and email and Cliente.objects.filter(email=email).exclude(pk=pk).exists():
            return ['El correo ya está en uso por otro cliente.']
        cliente.email = email

    telefono = data.get('telefono')
    if telefono is not None:
        cliente.telefono = telefono.strip() or None

    password = data.get('password')
    if password:
        cliente.password = make_password(password)

    if 'aprobado' in data and data['aprobado'] is not None:
        cliente.aprobado = bool(data['aprobado'])

    try:
        cliente.save()
        return []
    except IntegrityError:
        return ['Error al actualizar el cliente.']

def delete_cliente(pk: Any) -> bool:
    cliente = get_cliente(pk)
    if not cliente:
        return False
    cliente.delete()
    return True

def list_clientes(filters: Optional[Dict[str, Any]] = None):
    qs = Cliente.objects.all()
    if not filters:
        return qs
    if 'aprobado' in filters and filters['aprobado'] is not None:
        qs = qs.filter(aprobado=filters['aprobado'])
    if 'nombre' in filters and filters['nombre']:
        qs = qs.filter(nombre__icontains=filters['nombre'])
    return qs

def create_link(cliente_pk: Any, monto: Any, cuotas: int = 1, tipo_tarjeta: str = 'credito', descripcion: Optional[str] = None) -> Tuple[Optional[LinkPago], List[str]]:
	"""
	Crea un LinkPago calculando comisiones (random link por ahora).
	Devuelve (link_obj, errors)
	"""
	errors: List[str] = []
	cliente = get_cliente(cliente_pk)
	if not cliente:
		return None, ['Cliente no encontrado.']

	# Validaciones básicas y conversión de monto
	try:
		monto_dec = Decimal(str(monto))
	except (InvalidOperation, ValueError):
		return None, ['Monto inválido.']

	if monto_dec <= 0:
		return None, ['El monto debe ser mayor a cero.']

	try:
		cuotas_int = int(cuotas)
	except (ValueError, TypeError):
		cuotas_int = 1
	if cuotas_int <= 0:
		cuotas_int = 1

	tipo = tipo_tarjeta if tipo_tarjeta in ('debito', 'credito') else 'credito'
	# porcentajes
	perc_map = {
		'debito': Decimal('3.49'),
		'credito': Decimal('3.99'),
	}
	perc = perc_map[tipo]

	commission_amount = (monto_dec * perc / Decimal('100')).quantize(Decimal('0.01'))
	receiver_amount = (monto_dec - commission_amount).quantize(Decimal('0.01'))

	# generar link único simple
	link_str = uuid.uuid4().hex

	try:
		link_obj = LinkPago.objects.create(
			cliente=cliente,
			monto=monto_dec,
			cuotas=cuotas_int,
			tipo_tarjeta=tipo,
			descripcion=descripcion or '',
			commission_percent=perc,
			commission_amount=commission_amount,
			receiver_amount=receiver_amount,
			link=link_str,
		)
		link_obj.generate_invoice_text()
		link_obj.save()
		return link_obj, []
	except IntegrityError as e:
		return None, [f'Error al crear el link: {str(e)}']

def list_links_for_cliente(cliente_pk: Any):
	cliente = get_cliente(cliente_pk)
	if not cliente:
		return LinkPago.objects.none()
	return LinkPago.objects.filter(cliente=cliente).order_by('-created_at')

from typing import Tuple, Optional
from django.core.exceptions import ObjectDoesNotExist

def get_invoice_for_link(link_id: Any, cliente_pk: Any) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Recupera el texto de la factura (invoice_text) para el LinkPago indicado
    y valida que pertenezca al cliente (cliente_pk).
    Devuelve (filename, content, errors).
    """
    errors: List[str] = []
    try:
        link = LinkPago.objects.get(pk=link_id)
    except ObjectDoesNotExist:
        return None, None, ['Link no encontrado.']

    if link.cliente_id != cliente_pk:
        return None, None, ['No autorizado para descargar este ticket.']

    if not link.invoice_text:
        link.generate_invoice_text()
        link.save()

    filename = f"ticket_link_{link.id}.txt"
    content = link.invoice_text or ''
    return filename, content, []

def generate_pdf_for_link(link_id: Any, cliente_pk: Any) -> Tuple[Optional[str], Optional[bytes], List[str]]:
    """
    Genera un PDF (bytes) del ticket usando WeasyPrint a partir del LinkPago indicado,
    validando que pertenezca al cliente cliente_pk.
    Devuelve (filename, pdf_bytes, errors).
    """
    errors: List[str] = []
    try:
        link = LinkPago.objects.get(pk=link_id)
    except LinkPago.DoesNotExist:
        return None, None, ['Link no encontrado.']

    if link.cliente_id != cliente_pk:
        return None, None, ['No autorizado para descargar este ticket.']

    # Asegurar invoice_text y contexto
    if not link.invoice_text:
        link.generate_invoice_text()
        link.save()

    context = {
        'link': link,
        'cliente': link.cliente,
    }

    try:
        # render HTML desde plantilla
        html = render_to_string('ticket_pdf.html', context)
        # generar PDF con WeasyPrint
        try:
            from weasyprint import HTML
        except Exception as e:
            return None, None, [f'WeasyPrint no disponible: {e}']
        pdf_bytes = HTML(string=html).write_pdf()
        filename = f"ticket_link_{link.id}.pdf"
        return filename, pdf_bytes, []
    except Exception as e:
        return None, None, [f'Error generando PDF: {e}']
