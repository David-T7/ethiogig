from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0109_vettingpipelinerecord_interview_stage'),
    ]

    operations = [
        migrations.AddField(
            model_name='screeningconfig',
            name='skip_ai_screening_for_testing',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'When enabled, email verification auto-passes AI resume screening and advances '
                    'the pipeline without calling Gemini (local/testing only).'
                ),
            ),
        ),
        migrations.AddField(
            model_name='screeningconfig',
            name='skip_kyc_for_testing',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'When enabled, candidates skip identity verification and are invited straight '
                    'to the theoretical skills test after AI screening (local/testing only).'
                ),
            ),
        ),
        migrations.AddField(
            model_name='screeningconfig',
            name='disable_surveillance_for_testing',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'When enabled, candidates skip the camera pre-check and in-test face proctoring '
                    'for skills tests (local/testing only).'
                ),
            ),
        ),
    ]
