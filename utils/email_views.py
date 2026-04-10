# utils/email_views.py
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def enviar_correo_vista(request):
    """
    Vista que recibe datos JSON y envía un correo.
    Formato esperado:
    {
        "asunto": "string",
        "destinatarios": ["email1", "email2"],
        "mensaje_plano": "string opcional",
        "template_html": "ruta/template.html opcional",
        "contexto": {} opcional
    }
    """
    try:
        datos = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    asunto = datos.get("asunto")
    destinatarios = datos.get("destinatarios")
    mensaje_plano = datos.get("mensaje_plano")
    template_html = datos.get("template_html")
    contexto = datos.get("contexto", {})

    if not asunto or not destinatarios:
        return JsonResponse({"error": "Faltan asunto o destinatarios"}, status=400)

    remitente = settings.EMAIL_HOST_USER

    mensaje_html = None
    if template_html and contexto is not None:
        try:
            mensaje_html = render_to_string(template_html, contexto)
        except Exception as e:
            logger.error(f"Error renderizando template: {e}")
            return JsonResponse({"error": f"Error en template: {str(e)}"}, status=500)

    if not mensaje_plano and mensaje_html:
        mensaje_plano = "Mensaje en formato HTML. Usa un cliente que lo soporte."

    try:
        send_mail(
            asunto,
            mensaje_plano,
            remitente,
            destinatarios,
            html_message=mensaje_html,
            fail_silently=False,
        )
        logger.info(f"Correo enviado a {', '.join(destinatarios)}")
        return JsonResponse({"status": "enviado"})
    except Exception as e:
        logger.error(f"Error enviando correo: {e}")
        return JsonResponse({"error": str(e)}, status=500)