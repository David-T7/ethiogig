import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0112_freelancerbankaccount'),
    ]

    operations = [
        migrations.CreateModel(
            name='CandidateActionToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jti', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('purpose', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('resume', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='action_tokens',
                    to='core.resume',
                )),
            ],
        ),
    ]
