from rest_framework import serializers
from core.models import Resume, ScreeningResult, ScreeningConfig ,Field , FullAssessment

class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = ['id', 'full_name','password','email', 'applied_positions', 'resume_file', 'uploaded_at']
        read_only_fields = ['id','uploaded_at']
        extra_kwargs = {'password': {'write_only': True, 'min_length': 5}}


class ScreeningResultSerializer(serializers.ModelSerializer):
    resume = ResumeSerializer(read_only=True)
    
    class Meta:
        model = ScreeningResult
        fields = ['id', 'resume', 'score', 'passed', 'comments', 'screened_at']
        read_only_fields = ['id','screened_at']

class ScreeningConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScreeningConfig
        fields = ['passing_score_threshold', 'updated_at']
        read_only_fields = ['updated_at']

class FieldSerializer(serializers.ModelSerializer):    
    class Meta:
        model = Field
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']

class FullAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FullAssessment
        fields = [
            'id', 'freelancer', 'finished', 'soft_skills_assessment_status', 'depth_skill_assessment_status', 
            'applied_positions', 'live_assessment_status', 'project_assessment_status', 'passed', 
            'on_hold', 'on_hold_duration', 'created_at', 'updated_at', 'new_freelancer'
        ]
        read_only_fields = ['id']


