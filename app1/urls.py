from django.urls import path
from . import views
from utils.email_views import enviar_correo_vista

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('login/cliente', views.login_cliente, name='login_cliente'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('crear-link/', views.creacion_link, name='crear_link'),
    path('logout/cliente', views.logout_cliente, name='logout_cliente'),
    path('descargar-ticket/<int:link_id>/', views.download_ticket, name='download_ticket'),
    path('ticket_pdf/<int:link_id>/', views.ticket_pdf, name='ticket_pdf'),
    path('verificar-pago-ajax/<int:link_id>/', views.verificar_estado_pago_ajax, name='verificar_pago_ajax'),
    path('perfil/', views.gestion_perfil, name='perfil'),
    path('api/enviar-correo/', enviar_correo_vista, name='enviar_correo'),
    path('tyc/', views.tyc, name='tyc'),
    path('mensajes/', views.mensajes_cliente, name='mensajes_cliente'),
    path('mensajes/enviar/', views.enviar_mensaje_cliente, name='enviar_mensaje_cliente'),
    path('mensajes/poll/', views.poll_mensajes, name='poll_mensajes'),
    path('mensajes/finalizar/', views.finalizar_chat_cliente, name='finalizar_chat_cliente'),
    path('mensajes/ping/', views.ping_mensajes, name='ping_mensajes'),
]