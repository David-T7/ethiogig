from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0106_candidatevettingprogress'),
    ]

    operations = [
        migrations.AddField(
            model_name='services',
            name='hireable_role_label',
            field=models.CharField(blank=True, help_text='Display role e.g. Frontend Developer (falls back to name)', max_length=255),
        ),
        migrations.AddField(
            model_name='services',
            name='slug',
            field=models.SlugField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='services',
            name='specialization_tags',
            field=models.JSONField(blank=True, default=list, help_text='Tags e.g. landing-pages, web-apps'),
        ),
        migrations.CreateModel(
            name='VettingSkill',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('theoretical_test_id', models.UUIDField(blank=True, null=True)),
                ('practical_test_id', models.UUIDField(blank=True, null=True)),
                ('content_version', models.CharField(default='1.0', max_length=20)),
                ('content_owner', models.CharField(blank=True, max_length=255)),
                ('review_practicals', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('technology', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vetting_skill', to='core.technology')),
            ],
        ),
        migrations.CreateModel(
            name='VettingStack',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.AddField(
            model_name='candidatevettingprogress',
            name='selected_stack',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='candidate_selections', to='core.vettingstack'),
        ),
        migrations.CreateModel(
            name='StackSkill',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_required', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('skill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stack_memberships', to='core.vettingskill')),
                ('stack', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stack_skills', to='core.vettingstack')),
            ],
            options={
                'ordering': ['sort_order', 'skill__name'],
                'unique_together': {('stack', 'skill')},
            },
        ),
        migrations.CreateModel(
            name='SkillCertificate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('theoretical_score', models.FloatField(blank=True, null=True)),
                ('practical_score', models.FloatField(blank=True, null=True)),
                ('theoretical_submission_id', models.UUIDField(blank=True, null=True)),
                ('practical_submission_id', models.UUIDField(blank=True, null=True)),
                ('verified_at', models.DateTimeField()),
                ('expires_at', models.DateTimeField()),
                ('content_version', models.CharField(blank=True, max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('freelancer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='skill_certificates', to='core.freelancer')),
                ('resume', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='skill_certificates', to='core.resume')),
                ('skill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='certificates', to='core.vettingskill')),
                ('stack', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.vettingstack')),
            ],
            options={
                'unique_together': {('resume', 'skill', 'stack')},
            },
        ),
        migrations.CreateModel(
            name='ServiceVettingStack',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_default', models.BooleanField(default=False)),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='available_stacks', to='core.services')),
                ('stack', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='service_links', to='core.vettingstack')),
            ],
            options={
                'unique_together': {('service', 'stack')},
            },
        ),
    ]
