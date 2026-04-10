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
]