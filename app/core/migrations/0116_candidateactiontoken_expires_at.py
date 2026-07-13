import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0115_fix_milestone_indispute_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidateactiontoken',
            name='expires_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
