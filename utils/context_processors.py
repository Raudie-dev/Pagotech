from django.conf import settings

def whatsapp(request):
    return {
        'WHATSAPP_NUMBER':  getattr(settings, 'WHATSAPP_NUMBER', ''),
        'WHATSAPP_MESSAGE': getattr(settings, 'WHATSAPP_MESSAGE', ''),
    }