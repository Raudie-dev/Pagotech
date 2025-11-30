from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('login/cliente', views.login_cliente, name='login_cliente'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('crear-link/', views.creacion_link, name='crear_link'),
]