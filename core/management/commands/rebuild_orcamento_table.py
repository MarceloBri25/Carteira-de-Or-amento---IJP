from django.core.management.base import BaseCommand
from django.db import connection
from decimal import Decimal, InvalidOperation
from core.models import User
from datetime import date

class Command(BaseCommand):
    help = 'Rebuilds the core_orcamento table to clean up invalid data'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # 0. Disable foreign key checks
            self.stdout.write('Disabling foreign key checks...')
            cursor.execute("PRAGMA foreign_keys = OFF")

            # 1. Drop temporary table if it exists
            self.stdout.write('Dropping temporary table if it exists...')
            cursor.execute("DROP TABLE IF EXISTS core_orcamento_temp")

            # 2. Create a new temporary table
            self.stdout.write('Creating temporary table...')
            cursor.execute("""
                CREATE TABLE core_orcamento_temp (
                    id INTEGER NOT NULL PRIMARY KEY,
                    data_solicitacao date NOT NULL,
                    categoria varchar(20) NOT NULL,
                    numero_orcamento varchar(50) UNIQUE,
                    data_envio date,
                    valor_orcamento decimal NOT NULL,
                    termometro varchar(6) NOT NULL,
                    data_previsao_fechamento date,
                    semana_previsao_fechamento varchar(20),
                    etapa varchar(50) NOT NULL,
                    jornada_cliente text,
                    data_fechada_ganha date,
                    especificador_id bigint,
                    nome_cliente_id bigint,
                    usuario_id bigint NOT NULL REFERENCES core_user (id) DEFERRABLE INITIALLY DEFERRED
                )
            """)

            # 3. Copy and clean data
            self.stdout.write('Copying and cleaning data...')
            cursor.execute("SELECT * FROM core_orcamento")
            rows = cursor.fetchall()
            
            first_superuser = User.objects.filter(is_superuser=True).first()
            if not first_superuser:
                self.stdout.write(self.style.ERROR('No superuser found. Please create a superuser before running this command.'))
                return

            numeros_orcamento = set()
            for row in rows:
                row = list(row)
                try:
                    Decimal(row[5])
                except (InvalidOperation, TypeError):
                    self.stdout.write(self.style.WARNING(f'Invalid valor_orcamento for orcamento {row[0]}: {row[5]}'))
                    row[5] = Decimal('0.00')
                
                if row[9] is None:
                    self.stdout.write(self.style.WARNING(f'Null etapa for orcamento {row[0]}'))
                    row[9] = 'Especificação'
                
                if row[14] is None:
                    self.stdout.write(self.style.WARNING(f'Null usuario_id for orcamento {row[0]}'))
                    row[14] = first_superuser.id

                if row[3] in numeros_orcamento:
                    self.stdout.write(self.style.WARNING(f'Duplicate numero_orcamento for orcamento {row[0]}: {row[3]}'))
                    row[3] = f'{row[3]}_{row[0]}'
                numeros_orcamento.add(row[3])

                if row[1] is None:
                    self.stdout.write(self.style.WARNING(f'Null data_solicitacao for orcamento {row[0]}'))
                    row[1] = date.today()

                cursor.execute("""
                    INSERT INTO core_orcamento_temp VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, row)

            # 4. Delete old table
            self.stdout.write('Deleting old table...')
            cursor.execute("DROP TABLE core_orcamento")

            # 5. Rename new table
            self.stdout.write('Renaming temporary table...')
            cursor.execute("ALTER TABLE core_orcamento_temp RENAME TO core_orcamento")

            # 6. Enable foreign key checks
            self.stdout.write('Enabling foreign key checks...')
            cursor.execute("PRAGMA foreign_keys = ON")

        self.stdout.write(self.style.SUCCESS('Finished rebuilding orcamento table'))
