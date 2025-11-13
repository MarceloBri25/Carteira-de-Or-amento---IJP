from django.core.management.base import BaseCommand
from core.models import Orcamento, JornadaClienteHistorico
from django.utils import timezone
import datetime

class Command(BaseCommand):
    help = 'Migrates old jornada_cliente comments to the new JornadaClienteHistorico model.'

    def handle(self, *args, **options):
        orcamentos = Orcamento.objects.filter(jornada_cliente__isnull=False).exclude(jornada_cliente__exact='')
        self.stdout.write(f'Found {orcamentos.count()} orçamentos with old comments to migrate.')

        for orcamento in orcamentos:
            # Check if a historical entry with the exact same comment already exists to avoid duplicates
            if not JornadaClienteHistorico.objects.filter(orcamento=orcamento, comentario=orcamento.jornada_cliente).exists():
                # Combine date and time
                migration_datetime = datetime.datetime.combine(orcamento.data_solicitacao, datetime.time.min)
                # Make it timezone aware if timezone support is enabled in Django settings
                if timezone.is_aware(timezone.now()):
                    migration_datetime = timezone.make_aware(migration_datetime, timezone.get_default_timezone())

                JornadaClienteHistorico.objects.create(
                    orcamento=orcamento,
                    usuario=orcamento.usuario,
                    comentario=orcamento.jornada_cliente,
                    data_edicao=migration_datetime
                )
                self.stdout.write(self.style.SUCCESS(f'Successfully migrated comment for orcamento {orcamento.numero_orcamento}.'))
            else:
                self.stdout.write(self.style.WARNING(f'Skipping migration for orcamento {orcamento.numero_orcamento} as it seems to be a duplicate.'))
        
        self.stdout.write(self.style.SUCCESS('Migration completed.'))

        self.stdout.write('Clearing old jornada_cliente field...')
        for orcamento in orcamentos:
            orcamento.jornada_cliente = None
            orcamento.save()
        self.stdout.write(self.style.SUCCESS('Old jornada_cliente field cleared.'))