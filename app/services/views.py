# views.py
import json
from core.models import Freelancer
from rest_framework.views import APIView
from user.serializers import FreelancerSerializer
from rest_framework.response import Response
from django.db.models import Q
import google.generativeai as genai
import os
from core.models import Technology , Services
from rest_framework.permissions import AllowAny
from .serializers import TechnologySerializer , ServicesSerializer
from rest_framework import viewsets, status
from django.utils import timezone
from core.models import SkillSearch
from .serializers import SkillSearchSerializer
from django.db.models import F
from datetime import timedelta
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

# Configure the API key for generative AI
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

class FreelancerSearchView(APIView):

    def get(self, request, *args, **kwargs):
        tech_stack = request.query_params.getlist('tech_stack')
        working_preference = request.query_params.get('working_preference')
        project_duration = request.query_params.get('project_duration')
        project_budget = request.query_params.get('project_budget')
        project_description = request.query_params.get('project_description')

        freelancers = Freelancer.objects.all()

        ranked_freelancers = []
        for freelancer in freelancers:
            skill_matches = len(set(freelancer.skills) & set(tech_stack)) if tech_stack else 0
            if skill_matches > 0:
                if working_preference and freelancer.preferred_working_hours != working_preference:
                    continue

                score = self.evaluate_freelancer(
                    freelancer=freelancer,
                    position_applied_for=project_description,
                    project_duration=project_duration,
                    project_budget=project_budget
                )
                total_score = score + (skill_matches * 10)  # Adjust the weight of skill matches
                ranked_freelancers.append({
                    'freelancer': freelancer,
                    'score': total_score,
                })

        ranked_freelancers.sort(key=lambda x: x['score'], reverse=True)

        top_freelancers = [rf['freelancer'] for rf in ranked_freelancers]
        serializer = FreelancerSerializer(top_freelancers, many=True)
        return Response({
            'freelancers': serializer.data,
        })
    def evaluate_freelancer(self, freelancer, position_applied_for, project_duration, project_budget):
        resume_text = f"""
        Name: {freelancer.full_name}
        Title: {freelancer.professional_title}
        Skills: {', '.join(freelancer.skills)}
        Experience: {freelancer.experience} years
        Certifications: {', '.join(freelancer.certifications)}
        Portfolio: {freelancer.portfolio}
        Previous Work Experience: {freelancer.prev_work_experience}
        """
        prompt = f"""
        You are a hiring expert for a top freelancing site. Given the following resume text and the position applied for, the project budget, and the project duration, please evaluate it based on these criteria and provide a score from 0 to 100:

        Position Applied For: {position_applied_for}
        Project Duration: {project_duration}
        Project Budget: {project_budget}
        Criteria:
        Based on the match between the freelancer resume and the project requirements

        Resume Text:
        {resume_text}

        Score (0-100):
        """
        prompt += "\nResponse format:\n{\"score\": float}"

        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            evaluation_json = self.parse_json_from_response(response.text)
            score = evaluation_json.get("score", 0)
            return score
        except Exception as e:
            print(f"Error scoring resume with AI: {e}")
            return 0

    def parse_json_from_response(self, response_text):
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return {"score": 0}

class TechnologyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Technology.objects.all()
    serializer_class = TechnologySerializer

class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Services.objects.all()
    serializer_class = ServicesSerializer
    permission_classes = [AllowAny]  # Allow access to everyone

class SkillSearchViewSet(viewsets.ViewSet):
    """
    A simple ViewSet for listing, creating, and retrieving Skill Searches.
    """
    
    def list(self, request):
        """
        GET: Return recommended skills sorted by search count and last searched date.
        Allows filtering based on a minimum search count and a maximum gap in search time.
        """
        min_search_count = 10  
        max_time_gap_days = 180  
        
        # Calculate the date threshold based on the maximum time gap allowed
        date_threshold = timezone.now() - timedelta(days=max_time_gap_days)

        # Filter skills based on search count and last searched time, and then sort them
        skills = SkillSearch.objects.filter(
            search_count__gte=min_search_count,  # filter for skills with search count >= min_search_count
            last_searched_at__gte=date_threshold,
        ).order_by('-search_count', '-last_searched_at')
        if (len(skills) > 15): 
            skills = skills[:15]
        serializer = SkillSearchSerializer(skills, many=True)
        return Response(serializer.data)

    def create(self, request):
        """
        POST: Create or update search count for a list of skills.
        """
        # Assuming request.data contains a list of skill names
        skill_names = request.data.get('skill_names', [])

        if not isinstance(skill_names, list):
            return Response({"error": "Expected a list of skill names."}, status=status.HTTP_400_BAD_REQUEST)

        skills_data = []
        for skill_name in skill_names:
            skill, created = SkillSearch.objects.get_or_create(skill_name=skill_name)
            
            if not created:
                # Increment search count
                skill.search_count = F('search_count') + 1
                skill.last_searched_at = timezone.now()
                skill.save(update_fields=['search_count', 'last_searched_at'])
                skill.refresh_from_db()  # Refresh the instance to get the updated value
            else:
                skill.search_count = 1  # Initialize search count to 1
                skill.save()

            skills_data.append(SkillSearchSerializer(skill).data)

        return Response(skills_data, status=status.HTTP_201_CREATED)