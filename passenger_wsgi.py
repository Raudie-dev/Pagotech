import os
import sys

# Ruta hacia la carpeta donde está manage.py
sys.path.insert(0, '/home/pagotech/pagotech')

# Añadir también la carpeta del proyecto para que encuentre settings.py
sys.path.insert(1, '/home/pagotech/pagotech/proyecto')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()