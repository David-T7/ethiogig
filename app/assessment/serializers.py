from rest_framework import serializers
from core.models import FullAssessment


class FullAssessmentSerializer(serializers.ModelSerializer):
    # Customize `on_hold_duration` field to return duration in a readable format (e.g., days, hours)
    on_hold_duration = serializers.DurationField(required=False, allow_null=True)

    class Meta:
        model = FullAssessment
        fields = [
            'id', 
            'freelancer', 
            'finished', 
            'soft_skills_assessment', 
            'depth_skill_assessment', 
            'applied_positions',
            'live_assessment', 
            'project_assessment', 
            'passed', 
            'on_hold', 
            'on_hold_duration',
            'created_at', 
            'updated_at', 
            'new_freelancer'
        ]
        read_only_fields = ['id','created_at', 'updated_at']

    def to_representation(self, instance):
        # Customize the output of on_hold_duration for better readability
        representation = super().to_representation(instance)
        if instance.on_hold_duration:
            # Display on_hold_duration in days, hours, minutes
            total_seconds = instance.on_hold_duration.total_seconds()
            days = int(total_seconds // 86400)
            hours = int((total_seconds % 86400) // 3600)
            minutes = int((total_seconds % 3600) // 60)
            representation['on_hold_duration'] = f"{days} days, {hours} hours, {minutes} minutes"
        return representation