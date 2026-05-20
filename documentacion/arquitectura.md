# Arquitectura del Sistema — Pago Tech

## Diagrama de alto nivel

```
┌──────────────────────────────────────────────────────┐
│                    Internet                           │
└───────────────────────┬──────────────────────────────┘
                        │
              ┌─────────▼──────────┐
              │   Servidor Web      │
              │  (Passenger / WSGI) │
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │   Django 5.2 App   │
              │                    │
              │  ┌──────────────┐  │
              │  │    app1      │  │  ← Portal del Comercio (cliente)
              │  │  (cliente)   │  │
              │  └──────────────┘  │
              │  ┌──────────────┐  │
              │  │    app2      │  │  ← Panel de Administración
              │  │   (admin)    │  │
              │  └──────────────┘  │
              │  ┌──────────────┐  │
              │  │    utils     │  │  ← Email, helpers
              │  └──────────────┘  │
              └─────────┬──────────┘
                        │
          ┌─────────────┼────────────────┐
          │             │                │
  ┌───────▼──────┐ ┌────▼──────┐ ┌──────▼─────────┐
  │   Base de    │ │  Payzen   │ │  Servidor SMTP  │
  │   Datos      │ │  REST API │ │  (email)        │
  │ SQLite/MySQL │ │ (pagos)   │ │                 │
  └──────────────┘ └───────────┘ └─────────────────┘
```

## Estructura de directorios

```
Pagotech/
├── proyecto/               # Configuración central Django
│   ├── settings.py         # Config general (DB, apps, email, logging)
│   ├── urls.py             # Enrutador raíz
│   ├── wsgi.py
│   └── asgi.py
├── app1/                   # Portal del comercio (clientes)
│   ├── models.py           # Cliente, LinkPago
│   ├── views.py            # Vistas del portal
│   ├── urls.py             # Rutas /cliente/...
│   ├── crud.py             # Lógica de negocio + Payzen
│   ├── admin.py
│   ├── migrations/
│   └── templates/app1/
├── app2/                   # Panel de administración
│   ├── models.py           # User_admin, ParametroFinanciero, CuotaConfig
│   ├── views.py            # Vistas del admin
│   ├── urls.py             # Rutas /admin/...
│   ├── crud.py             # Operaciones administrativas
│   ├── admin.py
│   ├── migrations/
│   └── templates/app2/
├── utils/                  # Funciones compartidas
│   └── email.py            # Envío de correos
├── assets/                 # Archivos estáticos (CSS, JS, imágenes)
├── logs/                   # Archivos de log
├── Documentos/             # Documentos de negocio (contratos, liquidaciones)
├── manage.py
├── requirements.txt
├── passenger_wsgi.py       # Entrypoint para Passenger
└── .env                    # Variables de entorno
```

## Capas de la aplicación

### 1. Presentación (Templates + Assets)
- Django Templates (DTL) con Bootstrap
- Vanilla JS para interacciones AJAX (polling de estado de pago)
- WeasyPrint para generación de tickets/facturas en PDF

### 2. Lógica de negocio (Views + CRUD)
- `app1/views.py` y `app1/crud.py`: creación de links, cálculo de comisiones, consulta de estado en Payzen
- `app2/views.py` y `app2/crud.py`: aprobaciones, gestión de usuarios, configuración financiera

### 3. Datos (Models + Migrations)
- ORM de Django sobre SQLite (dev) / MySQL (prod)
- Migraciones versionadas para cada cambio de esquema

### 4. Integración externa
- **Payzen**: creación de órdenes de pago y verificación de estado vía REST
- **SMTP**: notificaciones de registro, aprobación de cuenta y facturas

## Autenticación y sesiones

El sistema usa **autenticación personalizada** (no el modelo `User` estándar de Django):

| Actor | Modelo | Mecanismo |
|---|---|---|
| Comercio (cliente) | `app1.Cliente` | `request.session` + `make_password` / `check_password` |
| Administrador | `app2.User_admin` | `request.session` |
| Superadmin (login-as) | `app2.User_admin` | Impersonación con guard de sesión |

## Entornos

| Variable | LOCAL | PRODUCCIÓN |
|---|---|---|
| `ENVIRONMENT` | `LOCAL` | `PROD` |
| Base de datos | SQLite (`pagotech.sqlite3`) | MySQL en `148.251.239.17` |
| `DEBUG` | `True` | `False` |
| Payzen | Credenciales de test | Credenciales de producción |
| Archivos estáticos | Django `runserver` | WhiteNoise |
