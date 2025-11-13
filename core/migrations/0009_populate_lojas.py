from django.db import migrations

LOJA_CHOICES = [
    'Portobello Manaus',
    'Portobello Santarém',
    'Portobello Rio Branco',
    'Artefacto',
    'Bontempo',
    'Smart',
]

def populate_lojas(apps, schema_editor):
    Loja = apps.get_model('core', 'Loja')
    for loja_nome in LOJA_CHOICES:
        Loja.objects.get_or_create(nome=loja_nome)

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_loja_alter_user_loja'),
    ]

    operations = [
        migrations.RunPython(populate_lojas),
    ]