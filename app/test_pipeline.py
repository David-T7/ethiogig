"""
One-off pipeline integration test. Run inside the app container:
  python test_pipeline.py
"""
import json
import os
import sys
import uuid

import django
import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ethiogig.settings")
django.setup()

from django.contrib.auth.hashers import make_password

from core.models import Resume, VettingPipelineRecord, Services
from resume.views import (
    PIPELINE_STAGES,
    generate_candidate_token,
    send_resume_for_screening,
    report_stage_result,
    get_pipeline_status,
)
from rest_framework.test import APIRequestFactory

API = "http://localhost:8000"
FRONTEND_STAGES = [
    "ai_screening",
    "kyc",
    "theoretical_test",
    "practical_test",
    "resume_check",
    "full_assessment",
]


def header(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def ok(msg):
    print(f"  PASS  {msg}")


def fail(msg):
    print(f"  FAIL  {msg}")
    return False


def check_stage_alignment():
    header("1. Frontend vs backend stage keys")
    if PIPELINE_STAGES == FRONTEND_STAGES:
        ok(f"All {len(PIPELINE_STAGES)} stages match")
        return True
    fail(f"Mismatch backend={PIPELINE_STAGES} frontend={FRONTEND_STAGES}")
    return False


def test_gemini():
    header("2. Gemini API connectivity")
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content('Reply with exactly: {"ok": true}')
        text = (response.text or "").strip()
        ok(f"Gemini responded ({len(text)} chars)")
        return True
    except Exception as e:
        fail(f"Gemini error: {e}")
        return False


def list_existing():
    header("3. Existing pipeline records")
    resumes = Resume.objects.filter(is_email_verified=True).order_by("-uploaded_at")[:8]
    if not resumes:
        print("  (no verified resumes)")
        return None
    for r in resumes:
        stages = list(
            VettingPipelineRecord.objects.filter(resume=r).values_list("stage", "status", "score")
        )
        print(f"  {r.email} | {r.id}")
        for s in stages:
            print(f"    {s}")
    return resumes.first()


def api_get_pipeline(resume_id, token):
    r = requests.get(
        f"{API}/api/resumes/{resume_id}/pipeline-status/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    return r.status_code, r.json() if r.content else {}


def api_report_stage(resume_id, token, stage, passed=True, score=85):
    r = requests.post(
        f"{API}/api/resumes/{resume_id}/pipeline-stage/",
        headers={"Authorization": f"Bearer {token}"},
        json={"stage": stage, "passed": passed, "score": score},
        timeout=15,
    )
    return r.status_code, r.json() if r.content else {}


def api_candidate_token(resume_id, password):
    r = requests.post(
        f"{API}/api/resumes/{resume_id}/candidate-token/",
        json={"password": password},
        timeout=15,
    )
    return r.status_code, r.json() if r.content else {}


def simulate_full_pipeline(resume, password=None):
    header(f"4. Full pipeline simulation — {resume.email}")
    factory = APIRequestFactory()
    all_pass = True

    if password:
        token_resp = api_candidate_token(resume.id, password)
        if token_resp[0] != 200:
            fail(f"candidate-token HTTP {token_resp[0]}: {token_resp[1]}")
            return False
        token = token_resp[1]["token"]
        ok("candidate-token issued (password flow)")
    else:
        token = generate_candidate_token(resume)
        ok("candidate-token issued (direct, test only)")

    # Ensure ai_screening passed (simulate if missing)
    ai = VettingPipelineRecord.objects.filter(resume=resume, stage="ai_screening").first()
    if not ai or ai.status != "passed":
        req = factory.post(
            f"/api/resumes/{resume.id}/pipeline-stage/",
            {"stage": "ai_screening", "passed": True, "score": 75},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        resp = report_stage_result(req, resume.id)
        if resp.status_code != 200:
            fail(f"ai_screening report failed: {resp.data}")
            return False
        ok("ai_screening → passed (simulated)")

    stages_to_report = ["kyc", "theoretical_test", "practical_test", "resume_check", "full_assessment"]
    for stage in stages_to_report:
        code, body = api_report_stage(resume.id, token, stage, passed=True, score=88)
        if code != 200:
            fail(f"{stage} report HTTP {code}: {body}")
            all_pass = False
            break
        ok(f"{stage} → passed | next: {body.get('next_stage')}")

    code, records = api_get_pipeline(resume.id, token)
    if code != 200:
        fail(f"pipeline-status HTTP {code}")
        return False

    by_stage = {r["stage"]: r for r in records}
    print("\n  Final pipeline-status:")
    for key in FRONTEND_STAGES:
        rec = by_stage.get(key)
        status = rec["status"] if rec else "missing"
        score = rec.get("score") if rec else "-"
        mark = "✓" if status == "passed" else "✗"
        print(f"    {mark} {key}: {status} (score={score})")

    passed_count = sum(1 for k in FRONTEND_STAGES if by_stage.get(k, {}).get("status") == "passed")
    if passed_count == len(FRONTEND_STAGES):
        ok(f"All {len(FRONTEND_STAGES)} stages passed")
    else:
        fail(f"Only {passed_count}/{len(FRONTEND_STAGES)} stages passed")
        all_pass = False

    return all_pass


def retrigger_screening(resume):
    header(f"5. Re-run AI screening — {resume.email}")
    if not resume.resume_file:
        fail("No resume file on record")
        return False
    try:
        results = send_resume_for_screening(resume)
        ai = VettingPipelineRecord.objects.filter(resume=resume, stage="ai_screening").first()
        if ai:
            ok(f"ai_screening status={ai.status} score={ai.score}")
            return ai.status == "passed"
        fail(f"No ai_screening record; screening returned {results}")
        return False
    except Exception as e:
        fail(str(e))
        return False


def get_or_create_test_resume():
    email = "pipeline-test@ethiogurus.test"
    resume = Resume.objects.filter(email=email, is_email_verified=True).first()
    if resume:
        return resume, "PipelineTest123!"
    service = Services.objects.first()
    if not service:
        return None, None
    resume = Resume.objects.create(
        full_name="Pipeline Test User",
        email=email,
        is_email_verified=True,
        applied_position=service,
        password=make_password("PipelineTest123!"),
        verification_token="",
        resume_file="resumes/dummy.pdf",
    )
    return resume, "PipelineTest123!"


def main():
    results = []
    results.append(("stage alignment", check_stage_alignment()))
    results.append(("gemini", test_gemini()))

    sample = list_existing()

    target = Resume.objects.filter(email="dawittesfaye743@gmail.com", is_email_verified=True).first()
    if not target:
        target = Resume.objects.filter(is_email_verified=True).order_by("-uploaded_at").first()

    if target:
        results.append(("full pipeline API", simulate_full_pipeline(target)))
        results.append(("ai screening retry", retrigger_screening(target)))

    header("SUMMARY")
    for name, passed in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")

    if not all(p for _, p in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
