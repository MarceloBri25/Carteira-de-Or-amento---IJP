from django.core.management.base import BaseCommand
from core.models import Orcamento, Cliente, Especificador

class Command(BaseCommand):
    help = 'Deletes all Orcamento and Cliente objects from the database'

    def handle(self, *args, **options):
        orcamento_count, _ = Orcamento.objects.all().delete()
        cliente_count, _ = Cliente.objects.all().delete()
        especificador_count, _ = Especificador.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {orcamento_count} orçamentos.'))
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {cliente_count} clientes.'))
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {especificador_count} especificadores.'))
