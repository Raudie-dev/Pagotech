# utils/email_utils.py
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)


def mail(asunto, destinatarios, mensaje_plano=None, template_html=None, contexto=None):
    logger.info(f"mail — intentando enviar correo — asunto={asunto} destinatarios={destinatarios}")

    if not asunto or not destinatarios:
        logger.warning("mail — faltan asunto o destinatarios")
        return False

    remitente = settings.EMAIL_HOST_USER
    if not remitente:
        logger.error("mail — EMAIL_HOST_USER no configurado")
        return False

    mensaje_html = None
    if template_html and contexto is not None:
        try:
            mensaje_html = render_to_string(template_html, contexto)
        except Exception as e:
            logger.error(f"mail — error renderizando template {template_html}: {e}")
            return False

    if not mensaje_plano and mensaje_html:
        mensaje_plano = "Mensaje en formato HTML. Usa un cliente que lo soporte."

    try:
        send_mail(
            asunto,
            mensaje_plano or "",
            remitente,
            destinatarios,
            html_message=mensaje_html,
            fail_silently=False,
        )
        logger.info(f"mail — correo enviado exitosamente a {destinatarios}")
        return True
    except Exception as e:
        logger.error(f"mail — excepción enviando correo: {e}")
        return False
    
def mail_con_pdf(asunto, destinatarios, template_html, contexto, pdf_bytes, pdf_nombre):
    """
    Envia email con PDF adjunto usando EmailMessage.
    """
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.conf import settings
    import logging

    logger = logging.getLogger(__name__)

    try:
        mensaje_html = render_to_string(template_html, contexto)
        email = EmailMessage(
            subject=asunto,
            body=mensaje_html,
            from_email=settings.EMAIL_HOST_USER,
            to=destinatarios,
        )
        email.content_subtype = 'html'
        email.attach(pdf_nombre, pdf_bytes, 'application/pdf')
        email.send(fail_silently=False)
        logger.info(f"Email con PDF enviado a {', '.join(destinatarios)}")
        return True
    except Exception as e:
        logger.error(f"Error enviando email con PDF: {e}")
        return False