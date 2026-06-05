# serializers.py

from rest_framework import serializers
from core.models import Services, Technology , SkillSearch

class TechnologySerializer(serializers.ModelSerializer):
    class Meta:
        model = Technology
        fields = ['id', 'name', 'description']
        read_only_fields = ['id',]

class ServicesSerializer(serializers.ModelSerializer):
    technologies = TechnologySerializer(many=True, read_only=True)
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Services
        fields = [
            'id', 'name', 'slug', 'hireable_role_label', 'display_name',
            'specialization_tags', 'description', 'field', 'technologies',
        ]
        read_only_fields = ['id',]

    def get_display_name(self, obj):
        label = obj.hireable_role_label or obj.name
        tags = obj.specialization_tags or []
        if tags:
            return f"{label} ({', '.join(tags)})"
        return label

class SkillSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillSearch
        fields = ['id','skill_name', 'search_count', 'last_searched_at']
        read_only_fields = ['id',]