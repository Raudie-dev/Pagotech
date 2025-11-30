from django.db import models

class Cliente(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=128)
    bloqueado = models.BooleanField(default=False)
    email = models.EmailField(max_length=150, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    aprobado = models.BooleanField(default=False)

    def __str__(self):
        return self.nombre
