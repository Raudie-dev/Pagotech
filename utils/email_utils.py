# utils/email_utils.py
from django.test import RequestFactory
from utils.email_views import enviar_correo_vista
import json
import logging

logger = logging.getLogger(__name__)

def mail(asunto, destinatarios, mensaje_plano=None, template_html=None, contexto=None):
    logger.info(f"mail — intentando enviar correo — asunto={asunto} destinatarios={destinatarios}")
    
    factory = RequestFactory()
    payload = {
        "asunto": asunto,
        "destinatarios": destinatarios,
        "mensaje_plano": mensaje_plano,
        "template_html": template_html,
        "contexto": contexto or {},
    }
    
    logger.debug(f"mail — payload={payload}")
    
    request = factory.post('/fake-path', data=json.dumps(payload), content_type='application/json')
    
    try:
        response = enviar_correo_vista(request)
        
        if response.status_code == 200:
            response_data = json.loads(response.content)
            if response_data.get("status") == "enviado":
                logger.info(f"mail — correo enviado exitosamente a {destinatarios}")
                return True
            else:
                logger.warning(f"mail — respuesta inesperada: {response_data}")
                return False
        else:
            logger.error(f"mail — error HTTP {response.status_code}: {response.content}")
            return False
            
    except Exception as e:
        logger.error(f"mail — excepción: {e}")
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