from django.db import models

class User_admin(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=128)
    bloqueado = models.BooleanField(default=False)
    email = models.EmailField(max_length=150, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    ultima_actividad_mensajes = models.DateTimeField(null=True, blank=True)
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

    # ── Alcance del plan ────────────────────────────────────────────────
    ALCANCE_GLOBAL   = 'global'
    ALCANCE_USUARIOS = 'usuarios'
    ALCANCE_CHOICES  = [
        (ALCANCE_GLOBAL,   'Global — visible para todos'),
        (ALCANCE_USUARIOS, 'Personalizado — solo usuarios asignados'),
    ]
    alcance = models.CharField(
        max_length=20,
        choices=ALCANCE_CHOICES,
        default=ALCANCE_GLOBAL,
    )
    # Relación M2M: usuarios que pueden ver este plan (solo si alcance='usuarios')
    usuarios_asignados = models.ManyToManyField(
        'app1.Cliente',
        blank=True,
        related_name='planes_personalizados',
    )

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

    # ── Toggles IVA ─────────────────────────────────────────────────────
    comision_aplica_iva = models.BooleanField(default=True)
    arancel_aplica_iva  = models.BooleanField(default=True)
    tasa_aplica_iva_fin = models.BooleanField(default=True)
    
    # ── Tarjeta asociada (None = crédito genérico) ───────────────────────
    tarjeta_custom = models.ForeignKey(
        'TarjetaCustom',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='planes_cuotas',
        help_text="Si se asigna, este plan solo aparece para esta tarjeta. Vacío = crédito genérico."
    )
    
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

    @property
    def es_personalizado(self):
        return self.alcance == self.ALCANCE_USUARIOS

    class Meta:
        ordering = ['numero_cuota']
        
class TarjetaCustom(models.Model):
    nombre              = models.CharField(max_length=100)
    slug                = models.SlugField(max_length=50, unique=True, help_text="Identificador interno ej: naranja_x")
    comision            = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    arancel             = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    iva                 = models.DecimalField(max_digits=5, decimal_places=2, default=21)
    aplica_iva          = models.BooleanField(default=True)
    acepta_cuotas       = models.BooleanField(default=False, help_text="Si permite financiacion en cuotas")
    activa              = models.BooleanField(default=True)
    icono               = models.CharField(max_length=100, blank=True, default='fas fa-credit-card',
                                           help_text="Clase Font Awesome ej: fas fa-credit-card")
    orden               = models.PositiveSmallIntegerField(default=0, help_text="Orden en el formulario")
    payzen_code         = models.CharField(
        max_length=50, blank=True, default='',
        help_text="Codigo Payzen ej: NARANJA, CABAL, CABAL_DEBIT, TUYA"
    )

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = "Tarjeta Custom"
        verbose_name_plural = "Tarjetas Custom"

    def __str__(self):
        return self.nombre

    @property
    def comision_efectiva(self):
        from decimal import Decimal
        if self.aplica_iva:
            return self.comision * (1 + self.iva / 100)
        return self.comision

    @property
    def arancel_efectivo(self):
        from decimal import Decimal
        if self.aplica_iva:
            return self.arancel * (1 + self.iva / 100)
        return self.arancel
    
class TerminosCondiciones(models.Model):
    version    = models.CharField(max_length=10, unique=True)
    contenido  = models.TextField(help_text="Formato Markdown")
    activa     = models.BooleanField(default=False)
    creado_en  = models.DateTimeField(auto_now_add=True)
    updated_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Términos y Condiciones"
        ordering = ['-creado_en']

    def __str__(self):
        return f"T&C v{self.version} {'✓' if self.activa else ''}"

    def save(self, *args, **kwargs):
        # Solo una versión activa a la vez
        if self.activa:
            TerminosCondiciones.objects.exclude(pk=self.pk).update(activa=False)
        super().save(*args, **kwargs)