import base64
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from clientes.models import Cliente
from core import roles as r
from core.exceptions import ErrorDeNegocio, StockInsuficiente, TransicionInvalida
from despacho.models import Entrega, Ruta
from inventario.models import Insumo, ItemBOM, MovimientoInventario, Producto
from pedidos.models import Cotizacion, CotizacionItem, DetallePedido, Estado, Pedido

PNG = "data:image/png;base64," + base64.b64encode(
    base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
).decode()


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        for g in r.TODOS:
            Group.objects.get_or_create(name=g)

        def mk(nombre, grupo, **kw):
            u = U.objects.create_user(nombre, password="x", **kw)
            u.groups.add(Group.objects.get(name=grupo))
            return u

        cls.ventas = mk("ventas", r.VENTAS)
        cls.cocina = mk("cocina", r.COCINA)
        cls.reparto = mk("reparto", r.REPARTO)
        cls.otro_reparto = mk("reparto2", r.REPARTO)
        cls.admin = U.objects.create_superuser("admin", password="x")
        cls.cliente = Cliente.objects.create(nombre="Ana", direccion="Calle 1")
        cls.harina = Insumo.objects.create(nombre="Harina", unidad="g", stock=1000, stock_minimo=100, costo_unitario=2)
        cls.huevo = Insumo.objects.create(nombre="Huevos", unidad="un", stock=10, stock_minimo=2, costo_unitario=100)
        cls.torta = Producto.objects.create(nombre="Torta", mano_obra=1000, margen_pct=50)
        ItemBOM.objects.create(producto=cls.torta, insumo=cls.harina, cantidad=300)
        ItemBOM.objects.create(producto=cls.torta, insumo=cls.huevo, cantidad=4)

    def nuevo_pedido(self, cantidad=1, horas=48):
        p = Pedido.objects.create(cliente=self.cliente, diseno="x", creado_por=self.ventas,
                                  fecha_entrega=timezone.now() + timedelta(hours=horas))
        DetallePedido.objects.create(pedido=p, producto=self.torta, cantidad=cantidad)
        p.recalcular_total()
        return p


class ReglasDeNegocio(Base):
    def test_precio_sugerido_usa_bom(self):
        # costo = 300*2 + 4*100 = 1000; + mano de obra 1000 = 2000; +50% = 3000
        self.assertEqual(self.torta.precio_sugerido(), Decimal("3000"))

    def test_cotizacion_se_aprueba_y_crea_pedido(self):
        c = Cotizacion.objects.create(cliente=self.cliente, diseno="d", creado_por=self.ventas,
                                      fecha_entrega=timezone.now() + timedelta(days=3))
        CotizacionItem.objects.create(cotizacion=c, producto=self.torta, cantidad=2)
        c.recalcular_total()
        self.assertEqual(c.total, Decimal("6000"))
        p = c.aprobar(self.ventas)
        c.refresh_from_db()
        self.assertEqual(c.estado, Cotizacion.Estado.APROBADA)
        self.assertEqual(p.estado, Estado.RECIBIDO)
        self.assertEqual(p.total, Decimal("6000"))
        self.assertEqual(p.direccion_entrega, "Calle 1")
        with self.assertRaises(ErrorDeNegocio):
            c.aprobar(self.ventas)

    def test_anticipacion_minima(self):
        p = Pedido(cliente=self.cliente, diseno="x", fecha_entrega=timezone.now() + timedelta(hours=2))
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_descuento_automatico_por_bom(self):
        p = self.nuevo_pedido(cantidad=2)
        p.cambiar_estado(Estado.EN_PREPARACION, self.cocina)
        self.harina.refresh_from_db()
        self.huevo.refresh_from_db()
        self.assertEqual(self.harina.stock, Decimal("400"))   # 1000 - 2*300
        self.assertEqual(self.huevo.stock, Decimal("2"))      # 10 - 2*4
        self.assertTrue(p.insumos_descontados)
        movs = MovimientoInventario.objects.filter(pedido=p)
        self.assertEqual(movs.count(), 2)
        self.assertTrue(all(m.tipo == "CONSUMO" for m in movs))
        p.descontar_insumos()  # idempotente
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock, Decimal("400"))

    def test_stock_insuficiente_no_descuenta_nada(self):
        p = self.nuevo_pedido(cantidad=3)  # necesita 12 huevos y hay 10
        with self.assertRaises(StockInsuficiente) as ctx:
            p.cambiar_estado(Estado.EN_PREPARACION, self.cocina)
        self.assertIn("Huevos", str(ctx.exception))
        p.refresh_from_db()
        self.harina.refresh_from_db()
        self.assertEqual(p.estado, Estado.RECIBIDO)
        self.assertEqual(self.harina.stock, Decimal("1000"))
        self.assertFalse(MovimientoInventario.objects.exists())

    def test_transiciones_invalidas(self):
        p = self.nuevo_pedido()
        with self.assertRaises(TransicionInvalida):
            p.cambiar_estado(Estado.LISTO, self.cocina)
        for e in (Estado.EN_PREPARACION, Estado.HORNEADO_DECORADO, Estado.CONTROL_CALIDAD):
            p.cambiar_estado(e, self.cocina)
        p.cambiar_estado(Estado.HORNEADO_DECORADO, self.cocina)  # control de calidad rechaza
        p.cambiar_estado(Estado.CONTROL_CALIDAD, self.cocina)
        p.cambiar_estado(Estado.LISTO, self.cocina)
        self.assertEqual(p.historial.count(), 7)

    def test_cancelar_solo_recibido(self):
        p = self.nuevo_pedido()
        p.cancelar(self.ventas)
        self.assertEqual(p.estado, Estado.CANCELADO)
        p2 = self.nuevo_pedido()
        p2.cambiar_estado(Estado.EN_PREPARACION, self.cocina)
        with self.assertRaises(TransicionInvalida):
            p2.cancelar(self.ventas)


class Despacho(Base):
    def pedido_listo(self):
        p = self.nuevo_pedido()
        for e in (Estado.EN_PREPARACION, Estado.HORNEADO_DECORADO, Estado.CONTROL_CALIDAD, Estado.LISTO):
            p.cambiar_estado(e, self.cocina)
        return p

    def test_solo_pedidos_listos_en_ruta(self):
        ruta = Ruta.objects.create(nombre="R", fecha=timezone.localdate(), repartidor=self.reparto)
        with self.assertRaises(ValidationError):
            Entrega(ruta=ruta, pedido=self.nuevo_pedido()).full_clean()

    def test_confirmacion_requiere_firma_o_foto(self):
        p = self.pedido_listo()
        ruta = Ruta.objects.create(nombre="R", fecha=timezone.localdate(), repartidor=self.reparto)
        e = Entrega.objects.create(ruta=ruta, pedido=p)
        with self.assertRaises(ErrorDeNegocio):
            e.confirmar("Ana", "", None, self.reparto)
        e.confirmar("Ana", PNG, None, self.reparto)
        e.refresh_from_db(); p.refresh_from_db(); ruta.refresh_from_db()
        self.assertEqual(e.estado, Entrega.Estado.ENTREGADA)
        self.assertTrue(e.firma)
        self.assertEqual(p.estado, Estado.ENTREGADO)
        self.assertEqual(ruta.estado, Ruta.Estado.COMPLETADA)

    def test_firma_invalida(self):
        p = self.pedido_listo()
        ruta = Ruta.objects.create(nombre="R", fecha=timezone.localdate(), repartidor=self.reparto)
        e = Entrega.objects.create(ruta=ruta, pedido=p)
        with self.assertRaises(ErrorDeNegocio):
            e.confirmar("Ana", "data:text/html;base64,AAAA", None, self.reparto)


class Api(Base):
    def cliente_api(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_requiere_autenticacion(self):
        self.assertIn(APIClient().get("/api/pedidos/").status_code, (401, 403))

    def test_permisos_por_rol_en_cambio_de_estado(self):
        p = self.nuevo_pedido()
        url = f"/api/pedidos/{p.pk}/cambiar_estado/"
        self.assertEqual(self.cliente_api(self.ventas).post(url, {"estado": "EN_PREPARACION"}, format="json").status_code, 403)
        self.assertEqual(self.cliente_api(self.reparto).post(url, {"estado": "EN_PREPARACION"}, format="json").status_code, 403)
        resp = self.cliente_api(self.cocina).post(url, {"estado": "EN_PREPARACION"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["estado"], "EN_PREPARACION")

    def test_error_de_negocio_devuelve_400_claro(self):
        p = self.nuevo_pedido(cantidad=5)
        resp = self.cliente_api(self.cocina).post(f"/api/pedidos/{p.pk}/cambiar_estado/", {"estado": "EN_PREPARACION"}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Stock insuficiente", resp.json()["detail"])
        resp = self.cliente_api(self.cocina).post(f"/api/pedidos/{p.pk}/cambiar_estado/", {"estado": "LISTO"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_crud_pedido_con_detalles_anidados(self):
        c = self.cliente_api(self.ventas)
        cuerpo = {"cliente": self.cliente.pk, "diseno": "Torta azul",
                  "fecha_entrega": (timezone.now() + timedelta(days=3)).isoformat(),
                  "detalles": [{"producto": self.torta.pk, "cantidad": 2}]}
        resp = c.post("/api/pedidos/", cuerpo, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        pk = resp.json()["id"]
        self.assertEqual(Decimal(resp.json()["total"]), Decimal("6000"))
        cuerpo["detalles"] = [{"producto": self.torta.pk, "cantidad": 1}]
        resp = c.put(f"/api/pedidos/{pk}/", cuerpo, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(Decimal(resp.json()["total"]), Decimal("3000"))
        self.assertEqual(c.delete(f"/api/pedidos/{pk}/").status_code, 204)
        cuerpo["fecha_entrega"] = (timezone.now() + timedelta(hours=1)).isoformat()
        self.assertEqual(c.post("/api/pedidos/", cuerpo, format="json").status_code, 400)

    def test_repartidor_solo_ve_sus_rutas(self):
        Ruta.objects.create(nombre="Mia", fecha=timezone.localdate(), repartidor=self.reparto)
        Ruta.objects.create(nombre="Otra", fecha=timezone.localdate(), repartidor=self.otro_reparto)
        nombres = [x["nombre"] for x in self.cliente_api(self.reparto).get("/api/rutas/").json()["results"]]
        self.assertEqual(nombres, ["Mia"])
        self.assertEqual(len(self.cliente_api(self.ventas).get("/api/rutas/").json()["results"]), 2)

    def test_stock_no_se_edita_por_api(self):
        resp = self.cliente_api(self.cocina).patch(f"/api/insumos/{self.harina.pk}/", {"stock": "99999"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock, Decimal("1000"))
        resp = self.cliente_api(self.cocina).post("/api/movimientos/registrar/", {
            "insumo": self.harina.pk, "tipo": "ENTRADA", "cantidad": "500"}, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.harina.refresh_from_db()
        self.assertEqual(self.harina.stock, Decimal("1500"))


class PaginasWeb(Base):
    def test_requiere_login(self):
        resp = self.client.get(reverse("pedido_list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_todas_las_paginas_cargan_para_admin(self):
        p = self.nuevo_pedido()
        ruta = Ruta.objects.create(nombre="R", fecha=timezone.localdate(), repartidor=self.reparto)
        cot = Cotizacion.objects.create(cliente=self.cliente, diseno="d", fecha_entrega=timezone.now() + timedelta(days=3))
        CotizacionItem.objects.create(cotizacion=cot, producto=self.torta, cantidad=1)
        self.client.force_login(self.admin)
        urls = [reverse("dashboard"), reverse("kanban")]
        for pref in ("cliente", "insumo", "producto", "movimiento", "cotizacion", "pedido", "ruta"):
            urls.append(reverse(f"{pref}_list"))
        for pref in ("cliente", "insumo", "producto", "cotizacion", "pedido", "ruta"):
            urls.append(reverse(f"{pref}_create"))
        urls += [reverse("movimiento_create"), reverse("pedido_detail", args=[p.pk]), reverse("pedido_update", args=[p.pk]),
                 reverse("cotizacion_detail", args=[cot.pk]), reverse("cotizacion_update", args=[cot.pk]),
                 reverse("producto_detail", args=[self.torta.pk]), reverse("producto_update", args=[self.torta.pk]),
                 reverse("ruta_detail", args=[ruta.pk]), reverse("insumo_update", args=[self.harina.pk]),
                 reverse("pedido_delete", args=[p.pk])]
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 200, u)

    def test_admin_django_modelos_registrados(self):
        self.client.force_login(self.admin)
        for modelo in ("clientes/cliente", "inventario/insumo", "inventario/producto", "inventario/itembom",
                       "inventario/movimientoinventario", "pedidos/cotizacion", "pedidos/pedido",
                       "pedidos/historialestado", "despacho/ruta", "despacho/entrega"):
            self.assertEqual(self.client.get(f"/admin/{modelo}/").status_code, 200, modelo)
        p = self.nuevo_pedido()
        self.assertEqual(self.client.get(f"/admin/pedidos/pedido/{p.pk}/change/").status_code, 200)

    def test_roles_restringen_secciones(self):
        self.client.force_login(self.reparto)
        self.assertEqual(self.client.get(reverse("cliente_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("kanban")).status_code, 403)
        self.assertEqual(self.client.get(reverse("ruta_list")).status_code, 200)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.client.force_login(self.cocina)
        self.assertEqual(self.client.get(reverse("kanban")).status_code, 200)
        self.assertEqual(self.client.get(reverse("cotizacion_list")).status_code, 403)

    def test_flujo_web_cotizar_y_aprobar(self):
        self.client.force_login(self.ventas)
        fecha = (timezone.localtime() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
        resp = self.client.post(reverse("cotizacion_create"), {
            "cliente": self.cliente.pk, "diseno": "Torta rosa", "fecha_entrega": fecha,
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "0", "items-MIN_NUM_FORMS": "1", "items-MAX_NUM_FORMS": "1000",
            "items-0-producto": self.torta.pk, "items-0-cantidad": "2", "items-0-precio_unitario": "",
        })
        self.assertEqual(resp.status_code, 302)
        cot = Cotizacion.objects.get()
        self.assertEqual(cot.total, Decimal("6000"))
        resp = self.client.post(reverse("cotizacion_aprobar", args=[cot.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Pedido.objects.count(), 1)


class Error404(Base):
    def test_404_redirige_a_la_aplicacion(self):
        resp = self.client.get("/esta/ruta/no/existe/")
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, 'url=/login/', status_code=404)
        self.client.force_login(self.ventas)
        resp = self.client.get("/otra-ruta-falsa")  # sin barra final: Django agrega "/" y luego muestra el 404
        self.assertEqual(resp.status_code, 301)
        resp = self.client.get("/otra-ruta-falsa", follow=True)
        self.assertContains(resp, 'url=/"', status_code=404)

    def test_404_de_la_api_es_json(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        resp = c.get("/api/no-existe/")
        self.assertEqual(resp.status_code, 404)
