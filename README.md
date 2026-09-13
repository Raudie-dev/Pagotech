# Pago Tech

Pago Tech es una plataforma Django para la gestión de cobros en línea, generación de links de pago y administración de clientes y liquidaciones. Está diseñada para funcionar con pasarela Payzen y ofrece paneles separados para clientes y administradores.

## Características principales

- Registro y autenticación de clientes
- Aprobación, bloqueo y gestión de clientes desde el panel administrativo
- Generación de links de pago con Payzen
- Verificación de estado de pago en tiempo real
- Descarga de tickets PDF
- Chat / mensajes entre clientes y administradores
- Gestión de configuraciones financieras y liquidaciones
- Soporte para términos y condiciones (.tyc)
- Uso de SQLite en local y MySQL en producción

## Tecnologías

- Backend: Django 5.2
- Base de datos: SQLite (local) / MySQL (producción)
- Pasarela de pago: Payzen
- PDF: WeasyPrint / ReportLab
- Servidor WSGI: Passenger / Gunicorn
- Frontend: Django Templates + Bootstrap + JavaScript

## Estructura del proyecto

- `app1/`: módulo principal de clientes, pago y generación de links
- `app2/`: módulo administrativo y configuración financiera
- `proyecto/`: configuración Django, URLs y WSGI
- `templates/`: plantillas HTML de la aplicación
- `assets/`: CSS, JS e imágenes
- `utils/`: utilidades compartidas para correo y context processors
- `documentacion/`: documentación técnica y de configuración
- `CreateUser.py`: script para crear usuarios administrativos

## Rutas principales

### Cliente

- `/` - Página principal
- `/register/` - Registro de cliente
- `/login/cliente` - Login de cliente
- `/dashboard/` - Panel cliente
- `/crear-link/` - Generar link de pago
- `/perfil/` - Perfil de cliente
- `/tyc/` - Términos y condiciones
- `/mensajes/` - Chat / mensajes

### Administrador

- `/app2/login/` - Login administrativo
- `/app2/aprobacion/` - Aprobación de clientes
- `/app2/gestion_usuarios/` - Gestión de usuarios aprobados
- `/app2/configuracion_financiera/` - Configuración de cuotas y parámetros
- `/app2/links_pagos/` - Gestión de links de pago
- `/app2/liquidaciones/` - Liquidaciones
- `/app2/mensajes/` - Mensajes administrativos

## API

### Envío de correos

- `POST /api/enviar-correo/`

Este endpoint recibe un cuerpo JSON y envía un correo usando la configuración SMTP del proyecto.

Cuerpo esperado:

```json
{
  "asunto": "Texto del asunto",
  "destinatarios": ["cliente@example.com"],
  "mensaje_plano": "Texto plano opcional",
  "template_html": "emails/plantilla.html",
  "contexto": { "clave": "valor" }
}
```

Respuestas posibles:

- `200 OK` – `{ "status": "enviado" }`
- `400 Bad Request` – `{ "error": "JSON inválido" }` o `{ "error": "Faltan asunto o destinatarios" }`
- `500 Internal Server Error` – `{ "error": "..." }`

> Nota: este endpoint utiliza `@csrf_exempt` y está diseñado para recibir peticiones POST con JSON.

## Instalación local

1. Clona el repositorio o descarga el proyecto.
2. En la raíz del proyecto, crea y activa un entorno virtual:

   Linux/macOS:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

   Windows:
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```

3. Instala las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

4. Configura las variables de entorno en un archivo `.env`.
5. Aplica migraciones:

   ```bash
   python manage.py migrate
   ```

6. Crea usuarios administrativos usando:

   ```bash
   python CreateUser.py
   ```

7. Inicia el servidor de desarrollo:

   ```bash
   python manage.py runserver
   ```

## Configuración de entorno (`.env`)

Las variables más importantes son:

- `ENVIRONMENT` – `LOCAL` / `PROD`
- `SECRET_KEY`
- `DEBUG` – `True` / `False`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` (MySQL en producción)
- `DB_NAME_SQLITE` (SQLite local, por ejemplo `db.sqlite3`)
- `PAYZEN_SHOP_ID`
- `PAYZEN_REST_PASS`
- `PAYZEN_URL`
- `PAYZEN_CHECK_URL`
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`

## Notas de despliegue

- En producción usar `ENVIRONMENT=PROD` y `DEBUG=False`.
- Ejecutar `python manage.py collectstatic` antes de desplegar.
- El archivo `passenger_wsgi.py` ya está preparado para despliegues con Passenger.
- `STATICFILES_DIRS` incluye la carpeta `assets/` y `STATIC_ROOT` está configurado en `staticfiles/`.

## Documentación adicional

La carpeta `documentacion/` contiene documentación extendida sobre:

- `arquitectura.md`
- `modulos.md`
- `flujos.md`
- `api_payzen.md`
- `configuracion.md`
- `tareas.md`

## Información útil

- `manage.py` es el punto de entrada para comandos Django.
- `proyecto/settings.py` carga variables de entorno y define la base de datos según `ENVIRONMENT`.
- Las notificaciones por correo usan `EMAIL_RECEPTORES` o `EMAIL_RECEPTOR` en la configuración.
- El sistema registra logs en `logs/pagotech.log`.

## Cómo contribuir

1. Crea una rama nueva para tu cambio.
2. Realiza los cambios y prueba localmente.
3. Asegúrate de migrar la base de datos si agregas modelos.
4. Envía un pull request con descripción clara de los cambios.
