import json
import pypdf
import os
import google.generativeai as genai
from django.core.mail import send_mail
from django.conf import settings
from core import models
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

# Configure the API key for generative AI
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

from pypdf import PdfReader

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    text = ''
    print("Started extracting")
    try:
        reader = PdfReader(pdf_path)
        number_of_pages = len(reader.pages)
        for page_num in range(number_of_pages):
            page = reader.pages[page_num]
            page_text = page.extract_text()
            if page_text:
                text += page_text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    print("Finished extracting")
    return text

def score_resume_with_chatgpt(resume_text, position_applied_for):
    """Score a resume using the ChatGPT model."""
    prompt = f"""
    You are a hiring expert for top freelancing site. Given the following resume text and the position applied for, please evaluate it based on these criteria and provide a score from 0 to 100 and return comment:

    Position Applied For: {position_applied_for}

    Criteria:
    - Relevant Experience: Number of years in the specific field or similar roles.
    - Educational Background: Degrees, certifications, or courses completed relevant to the job.
    - Skills: Specific technical or soft skills required for the projects.
    - Achievements: Notable accomplishments, awards, or recognitions.
    - Professionalism: Clarity and organization of the resume, grammar, and presentation.

    Resume Text:
    {resume_text}

    Score (0-100):
    """
    prompt += "\nResponse format:\n{\"score\": float, \"comment\": string}"

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')  # Verify this model name
        response = model.generate_content(prompt)
        # print("evaluation report ",response.text)
        evaluation_json = parse_json_from_response(response.text)
        score = evaluation_json.get("score", 0)
        comment = evaluation_json.get("comment", "")
        return {'score': score, 'comment': comment}
    except Exception as e:
        print(f"Error scoring resume with AI: {e}")
        return {'score': 0, 'comment': 'Error occurred during scoring.'}

def parse_json_from_response(response_text):
    """Parse JSON from the AI response text."""
    json_text = response_text.strip().strip('```json').strip('```').strip()
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON from response: {response_text}")
        return {}




def send_resume_result_email(user_email, score, passed, comments):
    subject = 'Your Resume Screening Result'
    print("mail started sening")
    if passed:
        message = f'Congratulations! Your resume has passed the screening with a score of {score}.\n\nComments: {comments}'
    else:
        message = f'We regret to inform you that your resume did not pass the screening. Your score is {score}.\n\nComments: {comments}'
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user_email],
        fail_silently=False,
    )
    print("mail sent")


def generate_password_reset_link(user):
    """Generate a password reset link."""
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    reset_link = f"http://127.0.0.1:8000/api/resume/reset-password/{uid}/{token}/"
    return reset_link

def send_password_reset_email(user_email):
    """Generate a password reset link and send it to the user's email."""
    try:
        user = models.User.objects.get(email=user_email)
    except models.User.DoesNotExist:
        print(f"No user found with email {user_email}")
        return
    
    reset_link = generate_password_reset_link(user)
    subject = 'Password Reset Request'
    message = f'Click the following link to reset your password: {reset_link}'

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user_email],
        fail_silently=False,
    )
    print(f"Password reset link sent to {user_email}")

def create_freelancer_from_resume(resume):
    """Create a Freelancer from a passed resume and send a password reset link."""
    user_email = resume.email

    # Create or update Freelancer profile
    freelancer, freelancer_created = models.Freelancer.objects.get_or_create(
        email=user_email,
        defaults={
            'full_name': resume.full_name,
            # Add other default fields as necessary
        }
    )

    # After ensuring the Freelancer is created or updated, handle User
    user, user_created = models.User.objects.get_or_create(
        email=user_email,
    )

    # Set the password and save the user
    if resume.password:
        user.set_password(resume.password)
        user.save()
        # Debugging: Check the hashed password
        print(f"Hashed password for user: {user.password}")

    # Optionally: Send a password reset link if needed
    # ...

    # Debugging
    print(f"Freelancer created: {freelancer_created}, Freelancer: {freelancer.email}")
