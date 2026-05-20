# Flujos del Sistema — Pago Tech

## 1. Registro y activación de un comercio

```
Comercio                  Sistema                     Admin
   │                         │                           │
   │── POST /register/ ──────►│                           │
   │                         │ Crea Cliente               │
   │                         │ aprobado=False             │
   │                         │ Envía email bienvenida     │
   │◄── Mensaje "en revisión"─│                           │
   │                         │                           │
   │                         │◄─── GET /admin/aprobacion/─│
   │                         │─── Muestra cola ──────────►│
   │                         │◄─── POST aprobar(id) ──────│
   │                         │ aprobado=True              │
   │                         │ Envía email activación    │
   │◄── Email "cuenta activa"─│                           │
```

## 2. Autenticación del comercio

```
POST /login/
  │
  ├─ Busca Cliente por email
  ├─ check_password(password, hash)
  ├─ Verifica aprobado=True y bloqueado=False
  ├─ Guarda en session: cliente_id, cliente_nombre
  └─ Redirect → /dashboard/
```

## 3. Creación de un link de pago

```
Comercio                  Sistema                    Payzen
   │                         │                         │
   │── GET /crear-link/ ──────►│                         │
   │◄── Formulario (monto,    │                         │
   │    cuotas, descripción)──│                         │
   │                         │                         │
   │── POST /crear-link/ ─────►│                         │
   │                         │ Calcula comisiones       │
   │                         │ (ParametroFinanciero +   │
   │                         │  CuotaConfig override)   │
   │                         │                         │
   │                         │── POST /api/charge ─────►│
   │                         │◄── {orderId, paymentURL}─│
   │                         │                         │
   │                         │ Crea LinkPago            │
   │                         │ (monto, cuotas, order_id)│
   │◄── Redirect a URL pago ──│                         │
   │                         │                         │
   │    (cliente final paga)  │                         │
   │                         │◄── Webhook / polling ────│
   │                         │ Actualiza pagado=True    │
   │                         │ Guarda auth_code, lote,  │
   │                         │ nro_transaccion          │
   │                         │ Genera liquidacion_texto │
```

## 4. Verificación de pago (polling AJAX)

```
Browser
   │
   ├─ Cada N segundos: GET /verificar-pago-ajax/<link_id>/
   │
   │   Sistema consulta Payzen GET /api/order/<order_id>/
   │   Si pagado:
   │     ├─ Actualiza LinkPago.pagado = True
   │     └─ Devuelve JSON {pagado: true, redirect: /dashboard/}
   │
   └─ JS redirige a /dashboard/ o muestra confirmación
```

## 5. Descarga de ticket PDF

```
GET /ticket/<link_id>/
  │
  ├─ Verifica sesión y ownership del link
  ├─ Recupera LinkPago con desglose de comisiones
  ├─ Renderiza template ticket_pdf.html
  ├─ WeasyPrint → bytes PDF
  └─ HttpResponse(content_type='application/pdf')
```

## 6. Cálculo de comisiones

El cálculo se realiza en `app1/crud.py` al crear el link:

```
monto_bruto
    │
    ├── arancel = monto × ParametroFinanciero.arancel_[tipo_tarjeta]
    ├── comision = monto × CuotaConfig.comision (o ParametroFinanciero.comision_[tipo])
    ├── tasa = monto × CuotaConfig.tasa
    ├── iva_21 = (comision + tasa) × ParametroFinanciero.iva_21 (si aplica)
    ├── iva_105 = arancel × ParametroFinanciero.iva_105 (si aplica)
    └── monto_neto = monto_bruto − arancel − comision − tasa − iva_21 − iva_105
```

## 7. Impersonación de comercio (admin)

```
Admin autenticado
   │
   ├─ GET /admin/login-as/<cliente_id>/
   │   ├─ Guarda admin_id en session
   │   ├─ Guarda cliente_id en session
   │   └─ Redirect → /dashboard/ (vista del comercio)
   │
   └─ GET /admin/volver-admin/
       ├─ Restaura session del admin
       └─ Redirect → /admin/gestion-usuarios/
```

## 8. Configuración de planes de cuotas

```
Admin
   │
   ├─ GET /admin/configuracion-financiera/
   │   └─ Muestra ParametroFinanciero + lista CuotaConfig
   │
   ├─ POST (guardar parámetros globales)
   │   └─ Actualiza ParametroFinanciero (fila única)
   │
   ├─ POST (crear/editar CuotaConfig)
   │   ├─ Si alcance=global → visible para todos los comercios
   │   └─ Si alcance=por_usuario → M2M con Clientes seleccionados
   │
   └─ El formulario /crear-link/ filtra CuotaConfig según el cliente en sesión
```

## 9. Flujo de emails transaccionales

| Evento | Template | Destinatario |
|---|---|---|
| Registro de comercio | `emails/notificacion_registro.html` | Email del comercio |
| Aprobación de cuenta | `emails/cuenta_aprobada.html` | Email del comercio |
| (Pendiente) Liquidación | — | Email admin del comercio |
| (Pendiente) Chat interno | — | Email del administrador Pago Tech |
