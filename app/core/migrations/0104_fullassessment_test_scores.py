from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0103_vettingpipelinerecord'),
    ]

    operations = [
        migrations.AddField(
            model_name='fullassessment',
            name='theoretical_test_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='fullassessment',
            name='practical_test_score',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
