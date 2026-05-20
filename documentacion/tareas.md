# Tareas Pendientes — Pago Tech

> Última actualización: 2026-05-01
> Estado: pendiente de implementación

---

## Prioridad Alta

### T-01 — Aceptación de términos y condiciones

**Descripción:** Al ingresar al panel del comercio (cliente), el sistema debe mostrar de forma obligatoria los términos y condiciones antes de que el usuario pueda operar.

**Criterios de aceptación:**
- [ ] Mostrar modal o pantalla de T&C al primer inicio de sesión (o cuando los T&C sean actualizados)
- [ ] El usuario no puede acceder al dashboard hasta aceptar
- [ ] Registrar en base de datos: fecha y hora de aceptación + versión de los T&C aceptados
- [ ] Si el comercio ya aceptó, no volver a mostrarlo hasta una nueva versión

**Cambios técnicos sugeridos:**
- Agregar campos `acepto_tyc` (BooleanField), `fecha_acepto_tyc` (DateTimeField), `version_tyc` (CharField) al modelo `Cliente`
- Middleware o decorador que intercepte el dashboard y redirija a `/tyc/` si no hay aceptación
- Vista `GET/POST /tyc/` con el texto de los T&C y botón de aceptación

---

### T-02 — Calculadora de cuotas en el link de pago

**Descripción:** Al generar un link de pago, mostrar una calculadora interactiva que permita al comercio simular el precio final al cliente según el recargo aplicado.

**Criterios de aceptación:**
- [ ] Campo "costo del comercio" (precio base ingresado por el comercio)
- [ ] Selector de recargo (porcentaje o monto fijo)
- [ ] Cálculo en tiempo real: `precio final = costo + recargo`
- [ ] Desglose visible: `costo comercio + recargo = precio de venta al cliente`
- [ ] El precio final calculado se puede usar directamente como monto del link de pago
- [ ] La calculadora debe funcionar sin recargar la página (JS puro o HTMX)

**Cambios técnicos sugeridos:**
- Agregar bloque de calculadora en `app1/templates/app1/creacion_link.html`
- Lógica de cálculo en JavaScript (sin llamadas al servidor)
- Al confirmar, el monto calculado se copia al campo `monto` del formulario

---

## Prioridad Media

### T-03 — Envío de liquidación al email del comercio

**Descripción:** Cuando se genera una liquidación, el sistema debe enviar automáticamente un resumen al email de administración del comercio, con opción de activar/desactivar el envío automático.

**Criterios de aceptación:**
- [ ] Al marcar un `LinkPago` como pagado, generar y enviar el email de liquidación
- [ ] El email incluye: fecha, monto bruto, desglose de comisiones (arancel, comisión, tasa, IVA), monto neto
- [ ] Opción en el perfil del comercio para activar/desactivar el envío automático
- [ ] Posibilidad de enviar manualmente desde el panel del admin de Pago Tech

**Cambios técnicos sugeridos:**
- Agregar campo `recibir_liquidacion_email` (BooleanField, default=True) en `Cliente`
- Crear template de email `app1/templates/emails/liquidacion.html`
- Llamar a la función de envío desde `app1/crud.py` al confirmar el pago
- Agregar toggle en la vista de perfil del comercio

---

### T-04 — Visualización de liquidaciones en el panel de Pago Tech

**Descripción:** El superadministrador de Pago Tech debe poder ver todas las liquidaciones realizadas a los comercios, con filtros y detalle por liquidación.

**Criterios de aceptación:**
- [ ] Vista `/admin/liquidaciones/` con listado paginado de todas las liquidaciones
- [ ] Filtros por: comercio, rango de fecha, monto, estado (pagado/pendiente)
- [ ] Vista de detalle de cada liquidación con todos los campos del `LinkPago`
- [ ] Exportar lista a CSV o Excel
- [ ] Totalizadores visibles: suma de montos, cantidad de operaciones

**Cambios técnicos sugeridos:**
- Nueva vista `liquidaciones` en `app2/views.py`
- Nueva URL `/admin/liquidaciones/` en `app2/urls.py`
- Template `app2/templates/app2/liquidaciones.html` con tabla + filtros
- Usar `django-filter` o filtros manuales por QueryString

---

### T-05 — Botón de WhatsApp visible y de mayor tamaño

**Descripción:** Agregar un botón/ícono flotante de WhatsApp en las páginas del portal del comercio y en la landing page, con número predefinido y mensaje de bienvenida.

**Criterios de aceptación:**
- [ ] Botón flotante (fixed, bottom-right) visible en todas las páginas del portal
- [ ] Al hacer clic, abrir `https://wa.me/<numero>?text=<mensaje_predefinido>`
- [ ] El número de WhatsApp debe ser configurable (variable de entorno o parámetro en admin)
- [ ] El botón debe ser visualmente destacado (tamaño mínimo 56px, color verde WhatsApp)
- [ ] Debe ser responsive (visible en móvil y escritorio)

**Cambios técnicos sugeridos:**
- Agregar bloque HTML/CSS en `app1/templates/app1/base_usuario.html` (y en `index.html`)
- Ícono SVG oficial de WhatsApp o Font Awesome
- Número configurable vía `settings.py` o `ParametroFinanciero`

---

## Prioridad Baja

### T-06 — Chat interno con copia al administrador

**Descripción:** Implementar un sistema de mensajería interna dentro del panel del comercio, donde los mensajes puedan hacer referencia a órdenes de pago y se envíe una copia por email al administrador de Pago Tech.

**Criterios de aceptación:**
- [ ] Los comercios pueden enviar mensajes desde su panel
- [ ] Cada mensaje puede referenciar opcionalmente un `LinkPago` (por ID o número de orden)
- [ ] Los mensajes se almacenan en base de datos con: remitente, texto, fecha, referencia de pago (opcional)
- [ ] Al enviar un mensaje, se envía una copia por email al administrador (email configurable)
- [ ] El administrador puede ver y responder los mensajes desde el panel de administración
- [ ] El comercio puede ver las respuestas del administrador

**Cambios técnicos sugeridos:**
- Nuevo modelo `MensajeInterno` con campos: `cliente` (FK), `admin` (FK nullable), `texto`, `fecha`, `link_pago` (FK nullable), `leido` (BooleanField)
- Vista y URL en `app1` para que el comercio envíe/vea mensajes
- Vista y URL en `app2` para que el admin gestione los mensajes
- Función de email en `utils/email.py` para notificación al admin
- Plantilla de email `utils/templates/emails/nuevo_mensaje.html`

---

## Resumen de tareas

| ID | Tarea | Prioridad | Estado |
|---|---|---|---|
| T-01 | Aceptación de términos y condiciones | Alta | Pendiente |
| T-02 | Calculadora de cuotas en link de pago | Alta | Pendiente |
| T-03 | Envío de liquidación al email del comercio | Media | Pendiente |
| T-04 | Visualización de liquidaciones en panel admin | Media | Pendiente |
| T-05 | Botón WhatsApp visible y de mayor tamaño | Media | Pendiente |
| T-06 | Chat interno con copia al administrador | Baja | Pendiente |
