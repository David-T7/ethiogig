import json
import os
import google.generativeai as genai
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from core import models
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from pypdf import PdfReader

genai.configure(api_key=os.environ["GEMINI_API_KEY"])


def extract_text_from_pdf(pdf_path):
    text = ''
    print("Started extracting")
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    print("Finished extracting")
    return text


def score_resume_with_gemini(resume_text, position_applied_for):
    prompt = f"""
    You are a hiring expert for top freelancing sites. Given the following resume text and the positions applied for, please evaluate it based on these criteria and provide a score from 0 to 100 along with a comment for each position:

    Position Applied For: {position_applied_for}

    Criteria:
    - Relevant Experience: Number of years in the specific field or similar roles.
    - Educational Background: Degrees, certifications, or courses completed relevant to the job.
    - Skills: Specific technical or soft skills required for the projects.
    - Achievements: Notable accomplishments, awards, or recognitions.
    - Professionalism: Clarity and organization of the resume, grammar, and presentation.

    Resume Text:
    {resume_text}

    please return the score and a comment in this format:
    {{
        "position_name": {{"score": float, "comment": string}},
        "position_name": {{"score": float, "comment": string}},
        ...
    }}
    """
    prompt += "\nResponse format:\n{\"position_name\": {\"score\": float, \"comment\": string}}"

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return parse_json_from_response(response.text)
    except Exception as e:
        print(f"Error scoring resume with AI: {e}")
        return {'error': 'Error occurred during scoring.'}


def parse_json_from_response(response_text):
    json_text = response_text.strip().strip('```json').strip('```').strip()
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON from response: {response_text}")
        return {}


def _send_email(to_email, subject, html_content):
    text_content = "Please view this email in an HTML-compatible email client."
    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    email_message.attach_alternative(html_content, "text/html")
    try:
        email_message.send(fail_silently=False)
        print("email sent")
    except Exception as e:
        print(f"Error sending email: {e}")


def send_resume_result_email(user_email, score, passed, comments):
    if passed:
        body = f'Congratulations! Your resume has passed the screening with a score of {score}.\n\nComments: {comments}'
    else:
        body = f'We regret to inform you that your resume did not pass the screening. Your score is {score}.\n\nComments: {comments}'

    html_content = f"<html><body><p>{body}</p></body></html>"
    _send_email(user_email, 'Your Resume Screening Result', html_content)


def generate_password_reset_link(user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return f"{settings.FRONTEND_URL}reset-password/{uid}/{token}/"


def send_password_reset_email(user_email):
    try:
        user = models.User.objects.get(email=user_email)
    except models.User.DoesNotExist:
        print(f"No user found with email {user_email}")
        return

    reset_link = generate_password_reset_link(user)
    html_content = f"""
    <html>
        <body>
            <p>Click the following link to reset your password:</p>
            <a href="{reset_link}">{reset_link}</a>
        </body>
    </html>
    """
    _send_email(user_email, 'Password Reset Request', html_content)
    print(f"Password reset link sent to {user_email}")


def create_freelancer_from_resume(resume):
    user_email = resume.email

    freelancer, freelancer_created = models.Freelancer.objects.get_or_create(
        email=user_email,
        defaults={'full_name': resume.full_name},
    )
    if freelancer_created:
        freelancer.email_verified = True
        freelancer.save()

    if resume.password:
        freelancer.password = resume.password
        freelancer.save()

    models.FullAssessment.objects.get_or_create(
        freelancer=freelancer,
        applied_position=resume.applied_position,
    )

    print(f"Freelancer created: {freelancer_created}, Freelancer: {freelancer.full_name}")
    return freelancer
