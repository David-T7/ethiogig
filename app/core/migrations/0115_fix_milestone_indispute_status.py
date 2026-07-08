from django.db import migrations, models


def fix_milestone_indispute(apps, schema_editor):
    Milestone = apps.get_model('core', 'Milestone')
    Milestone.objects.filter(status='inDsipute').update(status='inDispute')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0114_escrow_refund_failed_status'),
    ]

    operations = [
        migrations.RunPython(fix_milestone_indispute, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='milestone',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('pending', 'Pending'),
                    ('accepted', 'accepted'),
                    ('inDispute', 'InDispute'),
                    ('pendingApproval', 'Pending Approval'),
                    ('active', 'Active'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                ],
                default='pending',
            ),
        ),
    ]
