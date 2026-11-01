"""Carga datos de demostración: usuarios por rol, insumos, productos con BOM, pedidos y una ruta."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from clientes.models import Cliente
from core import roles as r
from despacho.models import Entrega, Ruta
from inventario.models import Insumo, ItemBOM, Producto
from pedidos.models import Cotizacion, CotizacionItem, DetallePedido, Estado, Pedido

INSUMOS = [
    # nombre, unidad, stock, mínimo, costo/unidad, perecible, días para vencer
    ("Harina", "g", 20000, 3000, "1.1", False, None),
    ("Azúcar", "g", 10000, 2000, "1.3", False, None),
    ("Huevos", "un", 120, 30, "180", True, 20),
    ("Mantequilla", "g", 8000, 1500, "6.5", True, 45),
    ("Leche", "ml", 10000, 2000, "1.2", True, 6),
    ("Crema de leche", "ml", 6000, 1000, "4.8", True, 5),
    ("Chocolate cobertura", "g", 5000, 1000, "9.5", False, None),
    ("Fondant", "g", 3000, 500, "7.0", False, None),
    ("Frutillas", "g", 2000, 500, "5.5", True, 3),
    ("Esencia de vainilla", "ml", 500, 100, "25", False, None),
    ("Polvos de hornear", "g", 40, 100, "12", False, None),
    ("Colorante alimentario", "ml", 100, 20, "60", False, None),
]

PRODUCTOS = [
    ("Torta de chocolate", "Bizcocho húmedo de chocolate con ganache.", 20, 180, 15000, 35,
     {"Harina": 500, "Azúcar": 400, "Huevos": 6, "Mantequilla": 300, "Chocolate cobertura": 350, "Leche": 250}),
    ("Torta tres leches", "Bizcocho de vainilla bañado en tres leches con crema.", 16, 150, 12000, 35,
     {"Harina": 350, "Azúcar": 300, "Huevos": 7, "Leche": 500, "Crema de leche": 400, "Esencia de vainilla": 10}),
    ("Docena de cupcakes decorados", "Cupcakes de vainilla con crema y fondant.", 12, 120, 9000, 40,
     {"Harina": 300, "Azúcar": 250, "Huevos": 4, "Mantequilla": 200, "Leche": 150, "Fondant": 100,
      "Colorante alimentario": 5}),
    ("Kuchen de frutilla", "Masa quebrada, crema pastelera y frutillas frescas.", 10, 90, 8000, 30,
     {"Harina": 300, "Azúcar": 150, "Huevos": 3, "Mantequilla": 150, "Frutillas": 400, "Leche": 300}),
]


class Command(BaseCommand):
    help = "Crea usuarios por rol y datos de ejemplo para probar el sistema."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="dulce1234", help="Contraseña de los usuarios de demo")

    def handle(self, *args, **opts):
        User = get_user_model()
        pw = opts["password"]
        for nombre in r.TODOS:
            Group.objects.get_or_create(name=nombre)

        def usuario(username, grupo, **extra):
            u, creado = User.objects.get_or_create(username=username, defaults=extra)
            if creado:
                u.set_password(pw)
                u.save()
            u.groups.add(Group.objects.get(name=grupo))
            return u

        admin, creado = User.objects.get_or_create(
            username="admin", defaults={"is_staff": True, "is_superuser": True, "first_name": "Administrador"})
        if creado:
            admin.set_password("admin1234")
            admin.save()
        admin.groups.add(Group.objects.get(name=r.ADMIN))
        ventas = usuario("ventas", r.VENTAS, first_name="Valentina Ventas")
        cocina = usuario("cocina", r.COCINA, first_name="Camilo Cocina")
        reparto = usuario("reparto", r.REPARTO, first_name="Rodrigo Reparto")

        hoy = timezone.localdate()
        insumos = {}
        for nombre, unidad, stock, minimo, costo, perecible, dias in INSUMOS:
            i, _ = Insumo.objects.get_or_create(nombre=nombre, defaults=dict(
                unidad=unidad, stock=stock, stock_minimo=minimo, costo_unitario=Decimal(costo),
                perecible=perecible, fecha_vencimiento=hoy + timedelta(days=dias) if dias else None,
                proveedor="Proveedor local"))
            insumos[nombre] = i

        productos = {}
        for nombre, desc, porc, tmin, mo, margen, bom in PRODUCTOS:
            p, creado = Producto.objects.get_or_create(nombre=nombre, defaults=dict(
                descripcion=desc, porciones=porc, tiempo_preparacion_min=tmin, mano_obra=mo, margen_pct=margen))
            if creado:
                for ins, cant in bom.items():
                    ItemBOM.objects.create(producto=p, insumo=insumos[ins], cantidad=cant)
            productos[nombre] = p

        if Pedido.objects.exists():
            self.stdout.write(self.style.WARNING("Ya existen pedidos: no se recrean datos de ejemplo."))
            return

        clientes = [
            Cliente.objects.get_or_create(nombre=n, defaults=dict(email=e, telefono=t, direccion=d))[0]
            for n, e, t, d in [
                ("María Contreras", "maria@example.com", "+56 9 1111 2222", "Av. Alemania 0456, Temuco"),
                ("Colegio Los Aromos", "eventos@losaromos.example", "+56 45 255 0000", "Calle Prat 321, Temuco"),
                ("Joaquín Pérez", "joaquin@example.com", "+56 9 3333 4444", "Los Notros 1200, Padre Las Casas"),
            ]
        ]

        def pedido(cliente, dias, horas, diseno, lineas):
            ped = Pedido.objects.create(
                cliente=cliente, diseno=diseno, creado_por=ventas,
                fecha_entrega=timezone.now() + timedelta(days=dias, hours=horas))
            for prod, cant in lineas:
                DetallePedido.objects.create(pedido=ped, producto=productos[prod], cantidad=cant)
            ped.recalcular_total()
            return ped

        pedido(clientes[0], 3, 0, "Torta de cumpleaños, mensaje «Feliz 30», flores de fondant lilas.",
               [("Torta de chocolate", 1)])
        p2 = pedido(clientes[1], 2, 2, "Cupcakes con el logo del colegio en fondant azul.",
                    [("Docena de cupcakes decorados", 3)])
        p3 = pedido(clientes[2], 1, 6, "Tres leches con decoración de frutillas y crema.",
                    [("Torta tres leches", 1), ("Kuchen de frutilla", 1)])
        p4 = pedido(clientes[0], 2, 0, "Kuchen para once familiar.", [("Kuchen de frutilla", 2)])

        p2.cambiar_estado(Estado.EN_PREPARACION, cocina)
        p3.cambiar_estado(Estado.EN_PREPARACION, cocina)
        p3.cambiar_estado(Estado.HORNEADO_DECORADO, cocina)
        for est in (Estado.EN_PREPARACION, Estado.HORNEADO_DECORADO, Estado.CONTROL_CALIDAD, Estado.LISTO):
            p4.cambiar_estado(est, cocina)

        cot = Cotizacion.objects.create(
            cliente=clientes[2], creado_por=ventas, diseno="Torta de chocolate para matrimonio, 2 pisos.",
            fecha_entrega=timezone.now() + timedelta(days=10))
        CotizacionItem.objects.create(cotizacion=cot, producto=productos["Torta de chocolate"], cantidad=2)
        cot.recalcular_total()

        ruta = Ruta.objects.create(nombre="Ruta centro", fecha=hoy + timedelta(days=1), repartidor=reparto)
        Entrega.objects.create(ruta=ruta, pedido=p4, orden=1)

        self.stdout.write(self.style.SUCCESS(
            "Datos de demo cargados.\n  admin / admin1234\n  ventas, cocina, reparto / %s" % pw))
