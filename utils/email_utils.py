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