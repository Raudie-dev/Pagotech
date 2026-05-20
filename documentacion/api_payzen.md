# Integración con Payzen — Pago Tech

## Descripción general

Payzen es la pasarela de pago utilizada para procesar cobros con tarjeta de crédito y débito. La integración es REST sobre HTTPS con autenticación Basic (Shop ID + contraseña).

## Variables de entorno relevantes

| Variable | Descripción |
|---|---|
| `PAYZEN_SHOP_ID` | ID del comercio en Payzen |
| `PAYZEN_REST_PASS` | Contraseña REST (test o producción) |
| `PAYZEN_URL` | Endpoint de creación de cargo |
| `PAYZEN_CHECK_URL` | Endpoint de consulta de estado |

## Endpoints utilizados

### Crear orden de pago

```
POST {PAYZEN_URL}
Authorization: Basic base64(SHOP_ID:REST_PASS)
Content-Type: application/json

{
  "amount": 10000,          // centavos
  "currency": "ARS",
  "orderId": "PT-<uuid>",
  "customer": { "email": "..." },
  "installmentNumber": 3
}
```

**Respuesta:**
```json
{
  "answer": {
    "orderId": "PT-xxx",
    "paymentUrl": "https://secure.payzen.com.ar/..."
  }
}
```

### Consultar estado de orden

```
GET {PAYZEN_CHECK_URL}/<order_id>
Authorization: Basic base64(SHOP_ID:REST_PASS)
```

**Respuesta:**
```json
{
  "answer": {
    "orderStatus": "PAID",
    "transactions": [{
      "authorizationResponse": { "authorizationNumber": "..." },
      "captureResponse": { "bankReconciliationIdentifier": "..." },
      "transactionDetails": { "sequenceNumber": "..." }
    }]
  }
}
```

## Flujo de pago

1. Sistema crea la orden en Payzen → recibe `paymentUrl` y `orderId`
2. Comercio/cliente final es redirigido a `paymentUrl`
3. Cliente ingresa datos de tarjeta en el formulario seguro de Payzen
4. El frontend de Pago Tech hace polling a `/verificar-pago-ajax/<id>/`
5. Cuando el estado es `PAID`, el sistema guarda los datos de la transacción en `LinkPago`

## Campos mapeados en LinkPago

| Campo Payzen | Campo LinkPago | Descripción |
|---|---|---|
| `orderId` | `order_id` | ID de orden |
| `authorizationNumber` | `auth_code` | Código de autorización bancaria |
| `bankReconciliationIdentifier` | `lote_number` | Número de lote |
| `sequenceNumber` | `nro_transaccion` | Número de transacción |

## Consideraciones de seguridad

- Las credenciales de producción NO deben subirse al repositorio
- Usar variables de entorno exclusivamente
- El endpoint de verificación AJAX (`/verificar-pago-ajax/`) valida que el `LinkPago` pertenezca al cliente en sesión antes de consultar Payzen
