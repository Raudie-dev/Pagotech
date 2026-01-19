from django.db import models
from decimal import Decimal
import uuid

class Cliente(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=128)
    bloqueado = models.BooleanField(default=False)
    email = models.EmailField(max_length=150, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    aprobado = models.BooleanField(default=False)

    def __str__(self):
        return self.nombre

class LinkPago(models.Model):
    """
    Registro de links de pago y su "factura" / ticket con cálculo de comisiones.
    """
    TIPO_TARJETA_CHOICES = (
        ('debito', 'Débito'),
        ('credito', 'Crédito'),
    )

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='links')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    cuotas = models.PositiveSmallIntegerField(default=1)
    tipo_tarjeta = models.CharField(max_length=10, choices=TIPO_TARJETA_CHOICES, default='credito')
    descripcion = models.TextField(null=True, blank=True)
    order_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    pagado = models.BooleanField(default=False)
    cuotas_elegidas = models.IntegerField(default=1)
    auth_code = models.CharField(max_length=50, blank=True, null=True) # Número de Autorización
    lote_number = models.CharField(max_length=10, blank=True, null=True) # Cierre de Lote
    nro_transaccion = models.CharField(max_length=50, blank=True, null=True) # ID de Transacción PayZen
    
    # comisión y montos calculados
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    receiver_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    # enlace generado (random por ahora)
    link = models.CharField(max_length=255, unique=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    # texto de factura / ticket para descargar
    invoice_text = models.TextField(null=True, blank=True)

    def generate_invoice_text(self):
        """Genera un texto simple de factura/ticket y lo guarda en invoice_text (no reemplaza un PDF)."""
        lines = []
        lines.append(f"Factura / Ticket - LinkPago #{self.id or 'N/A'}")
        lines.append(f"Cliente: {self.cliente.nombre}")
        lines.append(f"Fecha: {self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else 'N/A'}")
        lines.append(f"Descripción: {self.descripcion or '-'}")
        lines.append(f"Monto: {self.monto:.2f}")
        lines.append(f"Tipo de tarjeta: {self.get_tipo_tarjeta_display()}")
        lines.append(f"Cuotas: {self.cuotas}")
        lines.append(f"Porcentaje comisión: {self.commission_percent:.2f}%")
        lines.append(f"Comisión (plataforma): {self.commission_amount:.2f}")
        lines.append(f"Total a recibir (cliente): {self.receiver_amount:.2f}")
        lines.append(f"Link de pago: {self.link}")
        lines.append(f"Estado del pago: {'PAGADO' if self.pagado else 'PENDIENTE'}")
        self.invoice_text = "\n".join(lines)
        return self.invoice_text
