from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0107_vetting_taxonomy'),
    ]

    operations = [
        migrations.AddField(
            model_name='screeningconfig',
            name='disable_application_holds',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'When enabled, automatic application holds are not created or enforced '
                    '(useful for local/testing). Existing holds can still be deleted in admin.'
                ),
            ),
        ),
    ]
