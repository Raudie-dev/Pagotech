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
    comision_pago_tech = models.DecimalField(max_digits=5, decimal_places=2, default=4.00)
    arancel_plataforma = models.DecimalField(max_digits=5, decimal_places=2, default=1.80)
    comision_pago_tech_debito = models.DecimalField(max_digits=5, decimal_places=2, default=3.49)
    arancel_plataforma_debito = models.DecimalField(max_digits=5, decimal_places=2, default=0.80)
    class Meta:
        verbose_name = "Parámetros Financieros"

class CuotaConfig(models.Model):
    numero_cuota = models.IntegerField()
    nombre = models.CharField(max_length=100, default="Cuotas")
    tasa_base = models.DecimalField(max_digits=7, decimal_places=4)
    activa = models.BooleanField(default=True)

    # ── Overrides por plan (None = usar config global) ──────────────────
    iva_override              = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    iva_financiacion_override = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    com_credito_override      = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    com_debito_override       = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    arancel_credito_override  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    arancel_debito_override   = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # ── Toggles IVA (aplican sobre Comisión PT y Arancel Payway) ────────
    comision_aplica_iva = models.BooleanField(default=True)
    arancel_aplica_iva  = models.BooleanField(default=True)
    tasa_aplica_iva_fin     = models.BooleanField(default=True)

    @property
    def tiene_overrides(self):
        return any([
            self.iva_override is not None,
            self.iva_financiacion_override is not None,
            self.com_credito_override is not None,
            self.com_debito_override is not None,
            self.arancel_credito_override is not None,
            self.arancel_debito_override is not None,
            not self.comision_aplica_iva,
            not self.arancel_aplica_iva,
            not self.tasa_aplica_iva_fin,
        ])

    class Meta:
        ordering = ['numero_cuota']