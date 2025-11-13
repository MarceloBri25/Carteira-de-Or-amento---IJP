from django.core.management.base import BaseCommand
from django.db import connection
from core.models import Orcamento
from decimal import Decimal, InvalidOperation

class Command(BaseCommand):
    help = 'Cleans the valor_orcamento field in the Orcamento model'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, valor_orcamento FROM core_orcamento")
            rows = cursor.fetchall()

        for row in rows:
            orcamento_id, valor_orcamento_str = row
            try:
                Decimal(valor_orcamento_str)
            except (InvalidOperation, TypeError):
                self.stdout.write(self.style.WARNING(f'Invalid valor_orcamento for orcamento {orcamento_id}: {valor_orcamento_str}'))
                orcamento = Orcamento.objects.get(id=orcamento_id)
                orcamento.valor_orcamento = Decimal('0.00')
                orcamento.save()
                self.stdout.write(self.style.SUCCESS(f'Fixed valor_orcamento for orcamento {orcamento_id}'))
        self.stdout.write(self.style.SUCCESS('Finished cleaning valor_orcamento'))
