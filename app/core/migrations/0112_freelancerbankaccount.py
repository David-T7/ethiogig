import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0111_screeningconfig_skip_email_verification'),
    ]

    operations = [
        migrations.CreateModel(
            name='FreelancerBankAccount',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('account_type', models.CharField(
                    choices=[('bank', 'Bank Transfer'), ('mobile_money', 'Mobile Money (TeleBirr / CBE Birr)')],
                    default='bank', max_length=20,
                )),
                ('account_number', models.CharField(max_length=50)),
                ('account_name', models.CharField(max_length=100)),
                ('bank_code', models.CharField(blank=True, max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('freelancer', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='bank_account',
                    to='core.freelancer',
                )),
            ],
        ),
    ]
