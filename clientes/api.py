from rest_framework import filters, viewsets

from core import roles as r

from .models import Cliente
from .serializers import ClienteSerializer


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    roles_lectura = (r.VENTAS, r.REPARTO)
    roles_escritura = (r.VENTAS,)
    filter_backends = [filters.SearchFilter]
    search_fields = ["nombre", "email", "telefono"]
