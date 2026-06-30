from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0110_screeningconfig_testing_bypasses'),
    ]

    operations = [
        migrations.AddField(
            model_name='screeningconfig',
            name='skip_email_verification_for_testing',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'When enabled, new applications are marked email-verified immediately on submit '
                    'and screening starts without sending a verification link (local/testing only).'
                ),
            ),
        ),
        migrations.AlterField(
            model_name='screeningconfig',
            name='skip_ai_screening_for_testing',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'When enabled, verified applicants auto-pass AI resume screening and advance '
                    'the pipeline without calling Gemini (local/testing only).'
                ),
            ),
        ),
    ]
