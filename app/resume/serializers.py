from rest_framework import serializers
from core.models import Resume, ScreeningResult, ScreeningConfig , Technology , Services

class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = ['id', 'full_name','password','email', 'position_applied_for', 'resume_file', 'uploaded_at']
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


