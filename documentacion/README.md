# Documentación — Pago Tech

Esta carpeta contiene la documentación técnica y funcional del sistema Pago Tech.

## Índice

| Archivo | Descripción |
|---|---|
| [arquitectura.md](arquitectura.md) | Visión general de la arquitectura del sistema |
| [modulos.md](modulos.md) | Descripción detallada de cada módulo |
| [flujos.md](flujos.md) | Flujos principales de negocio y técnicos |
| [api_payzen.md](api_payzen.md) | Integración con la pasarela de pago Payzen |
| [configuracion.md](configuracion.md) | Variables de entorno y configuración del sistema |
| [tareas.md](tareas.md) | Tareas pendientes de implementación (roadmap) |

## Resumen ejecutivo

**Pago Tech** es una plataforma de cobro online para comercios de Latinoamérica. Permite a los comercios adheridos generar links de pago que sus clientes finales pueden abonar con tarjeta de crédito o débito, con soporte de cuotas y liquidación detallada de comisiones e impuestos.

**Stack tecnológico:**
- Backend: Django 5.2 (Python)
- Base de datos: SQLite (desarrollo) / MySQL (producción)
- Pasarela de pago: Payzen REST API
- Generación de PDFs: WeasyPrint / ReportLab
- Servidor: Passenger WSGI / Gunicorn
- Frontend: Django Templates + Bootstrap + Vanilla JS
