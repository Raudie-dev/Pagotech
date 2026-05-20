# Módulos del Sistema — Pago Tech

## app1 — Portal del Comercio

### Modelos

#### `Cliente`
Representa un comercio adherido a la plataforma.

| Campo | Tipo | Descripción |
|---|---|---|
| nombre | CharField | Razón social o nombre del comercio |
| email | EmailField (único) | Email de acceso y notificaciones |
| telefono | CharField | Teléfono de contacto |
| password | CharField | Hash bcrypt (Django) |
| aprobado | BooleanField | El admin debe aprobar la cuenta |
| bloqueado | BooleanField | Acceso suspendido por el admin |
| fecha_registro | DateTimeField | Auto al crear |

#### `LinkPago`
Representa una orden de cobro generada por el comercio.

| Campo | Tipo | Descripción |
|---|---|---|
| cliente | FK → Cliente | Comercio propietario del link |
| monto | DecimalField | Monto total a cobrar |
| cuotas_elegidas | IntegerField | Número de cuotas seleccionado |
| tipo_tarjeta | CharField | `credito` / `debito` |
| descripcion | CharField | Descripción del cobro |
| order_id | CharField | ID de orden en Payzen |
| pagado | BooleanField | Estado de pago |
| auth_code | CharField | Código de autorización bancaria |
| lote_number | CharField | Número de lote |
| nro_transaccion | CharField | Número de transacción |
| arancel | DecimalField | Arancel aplicado |
| comision | DecimalField | Comisión Pago Tech |
| tasa | DecimalField | Tasa financiera |
| iva_21 | DecimalField | IVA al 21% |
| iva_105 | DecimalField | IVA al 10.5% |
| liquidacion_texto | TextField | Texto de liquidación generado |
| fecha_creacion | DateTimeField | Auto al crear |

### Vistas y rutas

| URL | Vista | Descripción |
|---|---|---|
| `/` | `index` | Landing page pública |
| `/register/` | `register` | Registro de nuevo comercio |
| `/login/` | `login_view` | Autenticación del comercio |
| `/logout/` | `logout_view` | Cierre de sesión |
| `/dashboard/` | `dashboard` | Lista de links de pago |
| `/crear-link/` | `crear_link` | Formulario de nuevo link de pago |
| `/ticket/<id>/` | `ticket_pdf` | Descarga de ticket PDF |
| `/verificar-pago-ajax/<id>/` | `verificar_pago_ajax` | Polling AJAX de estado |
| `/api/enviar-correo/` | `enviar_correo_api` | Envío de email interno |

---

## app2 — Panel de Administración

### Modelos

#### `User_admin`
Administrador del sistema.

| Campo | Tipo | Descripción |
|---|---|---|
| username | CharField (único) | Nombre de usuario |
| password | CharField | Hash bcrypt (Django) |
| email | EmailField | Email del administrador |
| es_superadmin | BooleanField | Permisos elevados |

#### `ParametroFinanciero`
Configuración financiera global (fila única).

| Campo | Tipo | Descripción |
|---|---|---|
| iva_21 | DecimalField | Porcentaje IVA 21% |
| iva_105 | DecimalField | Porcentaje IVA 10.5% |
| comision_credito | DecimalField | Comisión tarjeta crédito (ej: 4%) |
| comision_debito | DecimalField | Comisión tarjeta débito (ej: 3.49%) |
| arancel_credito | DecimalField | Arancel crédito (ej: 1.8%) |
| arancel_debito | DecimalField | Arancel débito (ej: 0.8%) |
| aplica_iva_21 | BooleanField | Activa/desactiva IVA 21% |
| aplica_iva_105 | BooleanField | Activa/desactiva IVA 10.5% |

#### `CuotaConfig`
Plan de cuotas configurable con sobreescritura por usuario.

| Campo | Tipo | Descripción |
|---|---|---|
| nombre | CharField | Etiqueta del plan (ej: "3 cuotas sin interés") |
| cuotas | IntegerField | Cantidad de cuotas |
| tasa | DecimalField | Tasa del plan (override) |
| comision | DecimalField | Comisión override (opcional) |
| aplica_iva | BooleanField | IVA activo para este plan |
| alcance | CharField | `global` / `por_usuario` |
| usuarios | M2M → Cliente | Usuarios con acceso (si alcance=por_usuario) |

### Vistas y rutas

| URL | Vista | Descripción |
|---|---|---|
| `/admin/login/` | `login_admin` | Autenticación del administrador |
| `/admin/logout/` | `logout_admin` | Cierre de sesión |
| `/admin/gestion-usuarios/` | `gestion_usuarios` | Listado y gestión de comercios |
| `/admin/aprobacion/` | `aprobacion` | Cola de aprobaciones pendientes |
| `/admin/gestion-admins/` | `gestion_admins` | Gestión de administradores |
| `/admin/configuracion-financiera/` | `configuracion_financiera` | Parámetros financieros y cuotas |
| `/admin/links-pagos/` | `links_pagos` | Reporte de todos los links |
| `/admin/login-as/<id>/` | `login_as` | Impersonar un comercio |
| `/admin/volver-admin/` | `volver_admin` | Salir de impersonación |

---

## utils — Utilidades

### `email.py`
Funciones de envío de correo electrónico.

| Función | Descripción |
|---|---|
| `enviar_notificacion_registro(cliente)` | Email de bienvenida al registrarse |
| `enviar_cuenta_aprobada(cliente)` | Email de activación de cuenta |

---

## proyecto — Configuración central

### `settings.py` — Puntos de interés

- **`DATABASES`**: selección automática SQLite/MySQL según `ENVIRONMENT`
- **`INSTALLED_APPS`**: `app1`, `app2` registradas
- **`LOGGING`**: salida a consola y archivo `/logs/`
- **`EMAIL_BACKEND`**: `django.core.mail.backends.smtp.EmailBackend`
- **`PAYZEN_SHOP_ID`**, **`PAYZEN_REST_PASS`**: credenciales de la pasarela
- **`STATICFILES_STORAGE`**: WhiteNoise en producción
