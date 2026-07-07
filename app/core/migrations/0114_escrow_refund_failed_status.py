from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0113_candidateactiontoken'),
    ]

    operations = [
        migrations.AlterField(
            model_name='escrow',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('Pending', 'Pending'),
                    ('Released', 'Released'),
                    ('Refunded', 'Refunded'),
                    ('RefundFailed', 'Refund Failed'),
                ],
            ),
        ),
    ]
