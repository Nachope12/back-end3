# Dulce Arte · Sistema de trazabilidad y gestión de pedidos

Trazabilidad de punta a punta para una pastelería artesanal: **cotización → pedido → cocina (Kanban) → inventario (BOM) → despacho con firma/foto**.

- **Backend:** Django 5.2 + Django REST Framework
- **Base de datos:** PostgreSQL
- **Frontend:** templates Django + CSS/JS propios (el tablero Kanban consume la API REST)
- **Despliegue:** una sola instancia EC2 (Ubuntu) con Nginx + Gunicorn + PostgreSQL

> **URL pública (EC2):** `http://TU_IP_PUBLICA/`   ← reemplazar antes de entregar
> **Admin Django:** `http://TU_IP_PUBLICA/admin/` · **API:** `http://TU_IP_PUBLICA/api/`

## Funcionalidades

| Requisito | Dónde está |
|---|---|
| Cotización y registro de pedidos personalizados | Menú *Cotizaciones* y *Pedidos*. Una cotización aprobada genera el pedido. Valida anticipación mínima de 24 h. |
| Tablero Kanban de cocina | Menú *Tablero de cocina*: Recibido → En preparación → Horneado/Decorado → Control de calidad → Listo. Arrastrar o botones. Control de calidad puede devolver a Horneado. |
| Descuento automático de insumos con BOM | Al pasar a *En preparación* se descuentan los insumos de la lista de materiales (todo o nada; si falta stock se bloquea y se informa qué falta). Cada descuento queda en *Movimientos*. |
| Rutas de despacho con firma o foto | Menú *Rutas de despacho*: el repartidor confirma con firma en pantalla y/o foto del comprobante. Al confirmar, el pedido pasa a *Entregado*. |

## Roles y permisos

| Rol | Puede |
|---|---|
| **Administrador** | Todo, incluido el Admin de Django |
| **Ventas** | Clientes, cotizaciones, pedidos, planificar rutas, ver tablero (solo lectura) |
| **Cocina** | Tablero (mover pedidos), insumos, productos/BOM, movimientos |
| **Repartidor** | Ver sus rutas y confirmar entregas |

Los permisos se aplican igual en las vistas web y en la API.

## Ejecutar en local (VS Code)

1. Instalar Python 3.11+ y PostgreSQL. Crear la base:
   ```sql
   CREATE USER dulce_user WITH PASSWORD 'dulce_pass';
   CREATE DATABASE dulce_arte OWNER dulce_user;
   ```
2. En la carpeta del proyecto:
   ```bash
   python -m venv venv
   venv\Scripts\activate          # Windows   (Linux/Mac: source venv/bin/activate)
   pip install -r requirements.txt
   copy .env.example .env         # Linux/Mac: cp .env.example .env  → editar credenciales y DJANGO_DEBUG=True
   python manage.py migrate
   python manage.py seed_demo     # usuarios por rol + datos de ejemplo
   python manage.py runserver
   ```
3. Abrir <http://127.0.0.1:8000/>

**Usuarios de demo** (creados por `seed_demo`): `admin / admin1234` · `ventas`, `cocina`, `reparto` / `dulce1234`.

**Pruebas automáticas:** `python manage.py test` (21 pruebas: BOM, stock insuficiente, transiciones, permisos, API, despacho, páginas).

## Despliegue en EC2 (AWS Academy)

1. Lanzar una instancia **Ubuntu 22.04/24.04** (t2.micro/t3.micro sirve). En el *Security Group* abrir **22 (SSH)** y **80 (HTTP)**.
2. Conectarse por SSH y subir el proyecto (`git clone <tu-repo>` o `scp`).
3. Dentro de la carpeta del proyecto:
   ```bash
   bash deploy/desplegar_ec2.sh
   ./venv/bin/python manage.py seed_demo       # o createsuperuser
   ```
   El script instala PostgreSQL y Nginx, crea la base y el `.env`, aplica migraciones, genera estáticos y deja Gunicorn como servicio.
4. Abrir `http://IP_PUBLICA/`. Si la IP cambia al reiniciar la instancia, edita `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS` en `.env` y ejecuta `sudo systemctl restart dulce_arte`.

Ver estado/errores: `sudo systemctl status dulce_arte` · `sudo journalctl -u dulce_arte -n 50` · `sudo tail /var/log/nginx/error.log`.

## API REST (resumen)

Autenticación por sesión (login en `/api-auth/login/`) o Basic. Recursos: `clientes`, `insumos`, `productos`, `movimientos`, `cotizaciones`, `pedidos`, `rutas`, `entregas`.

| Acción | Endpoint |
|---|---|
| Aprobar cotización | `POST /api/cotizaciones/{id}/aprobar/` |
| Tablero | `GET /api/pedidos/kanban/` |
| Mover pedido (descuenta BOM al iniciar) | `POST /api/pedidos/{id}/cambiar_estado/` `{"estado": "EN_PREPARACION"}` |
| Insumos necesarios | `GET /api/pedidos/{id}/requerimiento/` |
| Registrar entrada/merma/ajuste | `POST /api/movimientos/registrar/` |
| Confirmar entrega | `POST /api/entregas/{id}/confirmar/` (`receptor_nombre`, `firma` data-URL PNG y/o `foto`) |

## Estructura

```
config/       settings, urls, API router
core/         roles, permisos, CRUD genérico, panel, seed_demo, pruebas
clientes/     Cliente
inventario/   Insumo, Producto, ItemBOM (BOM), MovimientoInventario, servicio de stock
pedidos/      Cotizacion, Pedido, DetallePedido, HistorialEstado, lógica Kanban/BOM
despacho/     Ruta, Entrega (firma/foto)
templates/    HTML (incluye personalización del Admin)  ·  static/  CSS y JS
deploy/       Nginx, Gunicorn, script de despliegue EC2
```

## Decisiones de diseño (para la defensa)

- **Descuento atómico:** `Pedido.descontar_insumos` usa `transaction.atomic` + `select_for_update`: si un insumo no alcanza, no se descuenta nada.
- **Sin doble descuento:** la bandera `insumos_descontados` y el bloqueo de la fila del pedido evitan descuentos repetidos por doble clic.
- **Stock auditado:** el stock solo cambia mediante `MovimientoInventario` (no se edita a mano).
- **Transiciones controladas:** el diccionario `TRANSICIONES` en `pedidos/models.py` define el flujo permitido.
- **Comprobantes privados:** las imágenes de firma/foto se sirven por una vista que exige sesión y rol, no públicamente.
