from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login, name='login'),
    path('gestion_usuarios/', views.gestion_usuarios, name='gestion_usuarios'),
    path('aprobacion/', views.aprobacion, name='aprobacion'),
    path('logout/', views.logout, name='logout'),
    path('gestion_admins/', views.gestion_admins, name='gestion_admins'),
    path('configuracion_financiera/', views.configuracion_financiera, name='configuracion_financiera'),
    path('links_pagos/', views.links_pagos, name='links_pagos'),
    path('login-as/<int:cliente_id>/', views.login_as_cliente, name='login_as_cliente'),
    path('volver-admin/', views.volver_a_admin, name='volver_a_admin'),
    path('liquidaciones/', views.liquidaciones, name='liquidaciones'),
    path('mensajes/', views.mensajes_admin, name='mensajes_admin'),
    path('mensajes/<int:cliente_id>/', views.mensajes_admin, name='mensajes_admin_cliente'),
    path('mensajes/<int:cliente_id>/responder/', views.responder_mensaje_admin, name='responder_mensaje_admin'),
    path('mensajes/<int:cliente_id>/poll/', views.poll_mensajes_admin, name='poll_mensajes_admin'),
    path('mensajes/<int:cliente_id>/finalizar/', views.finalizar_chat_admin, name='finalizar_chat_admin'),
    path('mensajes/ping/', views.ping_mensajes_admin, name='ping_mensajes_admin'),
    path('mensajes/iniciar/<int:cliente_id>/', views.iniciar_chat_admin, name='iniciar_chat_admin'),
    path('terminos/', views.terminos_condiciones, name='terminos_admin'),
]