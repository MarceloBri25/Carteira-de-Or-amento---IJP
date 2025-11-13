from django.db import migrations

def populate_user_loja(apps, schema_editor):
    User = apps.get_model('core', 'User')
    Loja = apps.get_model('core', 'Loja')

    for user in User.objects.all():
        if user.loja_old:
            try:
                loja_obj = Loja.objects.get(nome=user.loja_old)
                user.loja = loja_obj
                user.save()
            except Loja.DoesNotExist:
                # Handle cases where the old loja name doesn't exist in the new Loja table
                pass

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_add_loja_fk_to_user'),
    ]

    operations = [
        migrations.RunPython(populate_user_loja, reverse_code=migrations.RunPython.noop),
    ]