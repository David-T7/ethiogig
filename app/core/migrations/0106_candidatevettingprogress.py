from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0105_field_accepting_applications'),
    ]

    operations = [
        migrations.CreateModel(
            name='CandidateVettingProgress',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('position_name', models.CharField(blank=True, max_length=255)),
                ('selected_stack_slug', models.CharField(blank=True, max_length=100)),
                ('selected_stack_name', models.CharField(blank=True, max_length=255)),
                ('technology_results', models.JSONField(blank=True, default=dict)),
                ('verified_technologies', models.JSONField(blank=True, default=list)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resume', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='vetting_progress', to='core.resume')),
            ],
        ),
    ]
