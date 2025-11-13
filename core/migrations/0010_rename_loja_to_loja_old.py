from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_populate_lojas'),
    ]

    operations = [
        migrations.RenameField(
            model_name='user',
            old_name='loja',
            new_name='loja_old',
        ),
    ]