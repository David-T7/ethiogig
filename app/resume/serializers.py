from rest_framework import serializers
from core import models
class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Resume
        fields = ['id', 'full_name','password','email','is_email_verified','applied_position','verification_token','resume_file', 'uploaded_at']
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
        fields = [
            'passing_score_threshold',
            'disable_application_holds',
            'skip_email_verification_for_testing',
            'skip_ai_screening_for_testing',
            'skip_kyc_for_testing',
            'disable_surveillance_for_testing',
            'require_manual_proctoring',
            'updated_at',
        ]
        read_only_fields = ['updated_at']


class ProctorFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ProctorFlag
        fields = ['id', 'note', 'flagged_at']
        read_only_fields = ['id', 'flagged_at']


class ProctorSessionSerializer(serializers.ModelSerializer):
    flags = ProctorFlagSerializer(many=True, read_only=True)
    proctor_name = serializers.SerializerMethodField()
    candidate_name = serializers.SerializerMethodField()

    class Meta:
        model = models.ProctorSession
        fields = [
            'id', 'stage', 'status', 'proctor_name', 'candidate_name',
            'started_at', 'ended_at', 'created_at', 'flags',
        ]
        read_only_fields = fields

    def get_proctor_name(self, obj):
        return obj.proctor.full_name if obj.proctor else None

    def get_candidate_name(self, obj):
        return obj.resume.full_name

class FieldSerializer(serializers.ModelSerializer):    
    class Meta:
        model = models.Field
        fields = ['id', 'name', 'description', 'accepting_applications']
        read_only_fields = ['id']

class FullAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FullAssessment
        fields = [
            'id', 'freelancer', 'finished', 'soft_skills_assessment_status', 'status',
            'depth_skill_assessment_status', 'applied_position', 'live_assessment_status',
            'project_assessment_status', 'passed', 'on_hold', 'hold_until',
            'theoretical_test_score', 'practical_test_score',
            'created_at', 'updated_at', 'new_freelancer',
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


class VettingPipelineRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.VettingPipelineRecord
        fields = [
            'id', 'resume', 'stage', 'status', 'score',
            'external_submission_id', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


