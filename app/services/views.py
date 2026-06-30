import json
from core.models import Freelancer, Technology, Services
from rest_framework.views import APIView
from user.serializers import FreelancerSerializer
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import viewsets, status, generics
from .serializers import TechnologySerializer, ServicesSerializer, SkillSearchSerializer
from core.models import SkillSearch
from django.utils import timezone
from django.db.models import F
from datetime import timedelta
from rest_framework import permissions


def _parse_skills(skills_field):
    """Return a list of lowercase skill name strings from a freelancer's skills JSON."""
    if not skills_field:
        return []
    try:
        data = json.loads(skills_field) if isinstance(skills_field, str) else skills_field
        if isinstance(data, list):
            return [
                s['skill'].lower() for s in data
                if isinstance(s, dict) and s.get('skill')
            ]
        if isinstance(data, dict) and data.get('skill'):
            return [data['skill'].lower()]
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return []


def _score_freelancer(freelancer, tech_stack_lower, working_preference):
    """
    Deterministic recommendation score 0–100.
      60 pts  skill overlap  (matched / required * 60)
      20 pts  experience     (capped at 10 years)
      15 pts  rating         (0–5 → 0–15)
       5 pts  availability   (working preference match)
    """
    verified = set(_parse_skills(freelancer.skills))
    required = set(tech_stack_lower)

    if required:
        match_count = len(verified & required)
        skill_score = (match_count / len(required)) * 60
    else:
        skill_score = 30  # no filter — neutral score

    try:
        exp = min(float(freelancer.experience or 0), 10)
    except (TypeError, ValueError):
        exp = 0
    exp_score = (exp / 10) * 20

    try:
        rating = float(freelancer.average_rating or 0)
    except (TypeError, ValueError):
        rating = 0
    rating_score = (rating / 5.0) * 15

    pref_match = (
        not working_preference
        or working_preference == "I'll decide later"
        or freelancer.preferred_working_hours == working_preference
    )
    availability_score = 5 if pref_match else 0

    return skill_score + exp_score + rating_score + availability_score


class FreelancerSearchView(APIView):

    def get(self, request, *args, **kwargs):
        working_preference = request.query_params.get('working_preference', '')
        tech_stack_json = request.query_params.get('tech_stack', '')

        try:
            tech_stack = json.loads(tech_stack_json) if tech_stack_json else []
        except (json.JSONDecodeError, TypeError):
            tech_stack = []

        tech_stack_lower = [s.lower() for s in tech_stack]

        freelancers = Freelancer.objects.all()
        ranked = []

        for freelancer in freelancers:
            # When a required tech stack is given, skip freelancers with zero matching skills
            if tech_stack_lower:
                verified = set(_parse_skills(freelancer.skills))
                if not verified & set(tech_stack_lower):
                    continue

            score = _score_freelancer(freelancer, tech_stack_lower, working_preference)
            ranked.append((score, freelancer))

        ranked.sort(key=lambda x: x[0], reverse=True)
        top_freelancers = [f for _, f in ranked]

        serializer = FreelancerSerializer(top_freelancers, many=True)
        return Response({'freelancers': serializer.data})


class TechnologyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Technology.objects.all()
    serializer_class = TechnologySerializer


class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Services.objects.all()
    serializer_class = ServicesSerializer
    permission_classes = [AllowAny]


class ServicesByFieldView(generics.ListAPIView):
    serializer_class = ServicesSerializer

    def get_queryset(self):
        field_id = self.request.query_params.get('field_id')
        if field_id:
            return Services.objects.filter(field_id=field_id)
        return Services.objects.none()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response(
                {'message': 'No services available for the selected field'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SkillSearchViewSet(viewsets.ViewSet):

    def list(self, request):
        min_search_count = 10
        max_time_gap_days = 180
        date_threshold = timezone.now() - timedelta(days=max_time_gap_days)

        skills = SkillSearch.objects.filter(
            search_count__gte=min_search_count,
            last_searched_at__gte=date_threshold,
        ).order_by('-search_count', '-last_searched_at')

        if len(skills) > 15:
            skills = skills[:15]

        serializer = SkillSearchSerializer(skills, many=True)
        return Response(serializer.data)

    def create(self, request):
        skill_names = request.data.get('skill_names', [])
        if not isinstance(skill_names, list):
            return Response(
                {'error': 'Expected a list of skill names.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        skills_data = []
        for skill_name in skill_names:
            skill, created = SkillSearch.objects.get_or_create(skill_name=skill_name)
            if not created:
                skill.search_count = F('search_count') + 1
                skill.last_searched_at = timezone.now()
                skill.save(update_fields=['search_count', 'last_searched_at'])
                skill.refresh_from_db()
            else:
                skill.search_count = 1
                skill.save()
            skills_data.append(SkillSearchSerializer(skill).data)

        return Response(skills_data, status=status.HTTP_201_CREATED)
