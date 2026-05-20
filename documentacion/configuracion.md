# Configuración del Sistema — Pago Tech

## Variables de entorno (`.env`)

| Variable | Descripción | Ejemplo |
|---|---|---|
| `ENVIRONMENT` | Entorno activo | `LOCAL` / `PROD` |
| `SECRET_KEY` | Clave secreta Django | `django-insecure-...` |
| `DEBUG` | Modo debug | `True` / `False` |
| `DB_NAME` | Nombre de la BD MySQL | `pagotech_db` |
| `DB_USER` | Usuario MySQL | `pagotech_user` |
| `DB_PASSWORD` | Contraseña MySQL | — |
| `DB_HOST` | Host MySQL | `148.251.239.17` |
| `DB_PORT` | Puerto MySQL | `3306` |
| `DB_NAME_SQLITE` | Ruta SQLite (local) | `pagotech.sqlite3` |
| `PAYZEN_SHOP_ID` | ID comercio Payzen | `17684447` |
| `PAYZEN_REST_PASS` | Contraseña REST Payzen | `testpassword_...` |
| `PAYZEN_URL` | URL creación de pago | `https://...` |
| `PAYZEN_CHECK_URL` | URL consulta de estado | `https://...` |
| `EMAIL_HOST` | Servidor SMTP | `smtp.gmail.com` |
| `EMAIL_PORT` | Puerto SMTP | `587` |
| `EMAIL_HOST_USER` | Usuario SMTP | `noreply@pagotech.com` |
| `EMAIL_HOST_PASSWORD` | Contraseña SMTP | — |

## Configuración de base de datos

El sistema selecciona la base de datos automáticamente según `ENVIRONMENT`:

```python
# settings.py
if os.getenv('ENVIRONMENT') == 'LOCAL':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', ...}}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.mysql', ...}}
```

## Instalación local

```bash
# 1. Clonar el repositorio
git clone <repo>
cd Pagotech

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar entorno
cp .env.example .env       # Editar con valores locales

# 5. Aplicar migraciones
python manage.py migrate

# 6. Crear superadministrador
python CreateUser.py

# 7. Iniciar servidor de desarrollo
python manage.py runserver
```

## Despliegue en producción

1. Configurar `.env` con `ENVIRONMENT=PROD` y credenciales MySQL reales
2. Asegurarse de que `DEBUG=False`
3. Ejecutar `python manage.py collectstatic`
4. Configurar Passenger con `passenger_wsgi.py` como entry point
5. WeasyPrint requiere dependencias del sistema (ver documentación oficial)

## Creación de administradores

```bash
python CreateUser.py
```

El script solicita interactivamente: username, email, password y si el usuario es superadmin.

## Logging

Los logs se escriben en `/logs/` con el siguiente nivel:

| Logger | Nivel | Destino |
|---|---|---|
| `django` | DEBUG | Consola + archivo |
| `app1` | DEBUG | Archivo |
| `app2` | DEBUG | Archivo |

## Archivos estáticos

- **Desarrollo**: servidos por Django (`runserver`)
- **Producción**: servidos por WhiteNoise (middleware configurado en `settings.py`)
- **Ruta de colección**: `STATIC_ROOT = BASE_DIR / 'staticfiles'`
