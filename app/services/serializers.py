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
    
    class Meta:
        model = Services
        fields = ['id', 'name', 'description','field','technologies'] 
        read_only_fields = ['id',]

class SkillSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillSearch
        fields = ['id','skill_name', 'search_count', 'last_searched_at']
        read_only_fields = ['id',]