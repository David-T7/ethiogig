from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0102_resumecheck_created_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='VettingPipelineRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('stage', models.CharField(choices=[('ai_screening', 'AI Screening'), ('kyc', 'KYC Verification'), ('theoretical_test', 'Theoretical Skills Test'), ('practical_test', 'Practical Skills Test'), ('resume_check', 'Resume Check'), ('full_assessment', 'Full Assessment')], max_length=30)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('invited', 'Invited'), ('in_progress', 'In Progress'), ('passed', 'Passed'), ('failed', 'Failed'), ('on_hold', 'On Hold')], default='pending', max_length=20)),
                ('score', models.FloatField(blank=True, null=True)),
                ('external_submission_id', models.UUIDField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resume', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pipeline_records', to='core.resume')),
            ],
            options={
                'unique_together': {('resume', 'stage')},
            },
        ),
    ]
