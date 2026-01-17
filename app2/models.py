from django.db import models

class User_admin(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=128)
    bloqueado = models.BooleanField(default=False)
    email = models.EmailField(max_length=150, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return self.nombre

class ParametroFinanciero(models.Model):
    iva = models.DecimalField(max_digits=5, decimal_places=2, default=21.00)
    iva_financiacion = models.DecimalField(max_digits=5, decimal_places=2, default=10.50)
    
    # Comisiones para Crédito (puedes renombrarlas o usarlas por defecto)
    comision_pago_tech = models.DecimalField(max_digits=5, decimal_places=2, default=4.00)
    arancel_plataforma = models.DecimalField(max_digits=5, decimal_places=2, default=1.80)

    # NUEVOS: Comisiones específicas para Débito
    comision_pago_tech_debito = models.DecimalField(max_digits=5, decimal_places=2, default=3.49)
    arancel_plataforma_debito = models.DecimalField(max_digits=5, decimal_places=2, default=0.80)

    class Meta:
        verbose_name = "Parámetros Financieros"

# models.py
class CuotaConfig(models.Model):
    # numero_cuota se mantiene para cálculos, pero nombre es lo que verá el cliente
    numero_cuota = models.IntegerField() 
    nombre = models.CharField(max_length=100, default="Cuotas") 
    tasa_base = models.DecimalField(max_digits=7, decimal_places=4)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['numero_cuota']