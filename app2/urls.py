from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login, name='login'),
    path('gestion_usuarios/', views.gestion_usuarios, name='gestion_usuarios'),
    path('aprobacion/', views.aprobacion, name='aprobacion'),
    path('logout/', views.logout, name='logout'),
    path('gestion_admins/', views.gestion_admins, name='gestion_admins'),
    path('configuracion_financiera/', views.configuracion_financiera, name='configuracion_financiera'),
]