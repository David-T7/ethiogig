from rest_framework import serializers
from core import models
class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Resume
        fields = ['id', 'full_name','password','email','is_email_verified','applied_positions', 'resume_file', 'uploaded_at']
        read_only_fields = ['id','uploaded_at']
        extra_kwargs = {'password': {'write_only': True, 'min_length': 5}}


class ScreeningResultSerializer(serializers.ModelSerializer):
    resume = ResumeSerializer(read_only=True)
    
    class Meta:
        model = models.ScreeningResult
        fields = ['id', 'resume', 'score', 'passed', 'comments', 'screened_at']
        read_only_fields = ['id','screened_at']

class ScreeningConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ScreeningConfig
        fields = ['passing_score_threshold', 'updated_at']
        read_only_fields = ['updated_at']

class FieldSerializer(serializers.ModelSerializer):    
    class Meta:
        model = models.Field
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']

class FullAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FullAssessment
        fields = [
            'id', 'freelancer', 'finished', 'soft_skills_assessment_status','status','depth_skill_assessment_status', 
            'applied_position', 'live_assessment_status', 'project_assessment_status', 'passed', 
            'on_hold', 'hold_until', 'created_at', 'updated_at', 'new_freelancer'
        ]
        read_only_fields = ['id']

class AssessmentTerminationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AssessmentTermination
        fields = ['id', 'freelancer', 'termination_count']
        read_only_fields = ['id']

class ApplicationOnHoldSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ApplicationOnHold
        fields = ['id', 'resume', 'email', 'position', 'hold_until', 'created_at','reason']
        read_only_fields = ['id', 'created_at']


