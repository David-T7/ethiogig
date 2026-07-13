import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0116_candidateactiontoken_expires_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='screeningconfig',
            name='require_manual_proctoring',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'When enabled, a human proctor must be connected and monitoring before '
                    'the candidate can start any skills test.'
                ),
            ),
        ),
        migrations.CreateModel(
            name='Proctor',
            fields=[
                (
                    'user_ptr',
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ('full_name', models.CharField(max_length=100)),
                ('phone_number', models.CharField(blank=True, max_length=15, null=True)),
                ('max_concurrent_sessions', models.PositiveIntegerField(default=5)),
            ],
            bases=('core.user',),
        ),
        migrations.CreateModel(
            name='ProctorSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    'resume',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='proctor_sessions',
                        to='core.resume',
                    ),
                ),
                (
                    'proctor',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='sessions',
                        to='core.proctor',
                    ),
                ),
                ('stage', models.CharField(max_length=50)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('proctor_joined', 'Proctor Joined'),
                            ('active', 'Active'),
                            ('completed', 'Completed'),
                            ('terminated', 'Terminated'),
                        ],
                        default='pending',
                        max_length=20,
                    ),
                ),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='ProctorFlag',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    'session',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='flags',
                        to='core.proctorsession',
                    ),
                ),
                ('note', models.TextField()),
                ('flagged_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
