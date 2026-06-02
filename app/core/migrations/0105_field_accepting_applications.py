from django.db import migrations, models


def mark_developer_fields_open(apps, schema_editor):
    Field = apps.get_model('core', 'Field')
    Field.objects.filter(name__icontains='developer').update(accepting_applications=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0104_fullassessment_test_scores'),
    ]

    operations = [
        migrations.AddField(
            model_name='field',
            name='accepting_applications',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_developer_fields_open, migrations.RunPython.noop),
    ]
