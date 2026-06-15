from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0108_screeningconfig_disable_application_holds'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vettingpipelinerecord',
            name='stage',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('ai_screening', 'AI Screening'),
                    ('kyc', 'KYC Verification'),
                    ('theoretical_test', 'Theoretical Skills Test'),
                    ('practical_test', 'Practical Skills Test'),
                    ('resume_check', 'Resume Check'),
                    ('full_assessment', 'Full Assessment'),
                    ('interview', 'Interview'),
                ],
            ),
        ),
    ]
