# EthioGig Main Backend — Developer Reference

Primary Django REST API for EthioGig: users, projects, contracts, assessments, resume intake, and the **candidate vetting pipeline**.

**Path:** `c:\toptal\Django Project\`  
**Port:** `8000`  
**Frontend:** `c:\toptal\React App\my-react-app\`  
**API prefix:** `/api/`

---

## Running

```bash
cd "c:\toptal\Django Project"
docker compose up -d          # app + postgres + redis + celery
docker compose exec app python manage.py migrate
docker compose exec app python test_pipeline.py   # pipeline integration smoke test
```

Swagger: `http://127.0.0.1:8000/api/docs/`

---

## Environment

Copy `app/.env.example` → `app/.env` (git-ignored). Required secrets:

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | AI resume screening (`score_resume_with_gemini`) — **never commit** |
| Email vars | Brevo/SMTP for verification and pipeline emails |

`docker-compose.yml` references sibling services:

| Env | Default |
|---|---|
| `THEORETICAL_TEST_SERVICE_URL` | `http://localhost:8001` |
| `PRACTICAL_TEST_SERVICE_URL` | `http://localhost:8002` |
| `SURVEILLANCE_SERVICE_URL` | `http://localhost:8003` |
| `KYC_SERVICE_URL` | `http://localhost:8005` |

**JWT:** `SECRET_KEY` in `ethiogig/settings.py` signs **candidate tokens** consumed by all microservices. All services must use the same key.

---

## App Layout

```
app/
├── ethiogig/          # settings, urls, wsgi
├── core/              # Resume, Freelancer, VettingPipelineRecord, Services, …
├── resume/            # Pipeline, screening, candidate auth — **start here for vetting**
├── user/              # Auth, profiles, role management
├── project/           # Projects, contracts, disputes
├── assessment/        # Full assessment lifecycle
├── interview/         # Interviewer appointments
├── services/          # Service/position catalog
└── test_pipeline.py   # End-to-end pipeline script
```

---

## Candidate Vetting Pipeline

### Stages (`resume/views.py`)

```python
PIPELINE_STAGES = [
    'ai_screening',
    'kyc',
    'theoretical_test',
    'practical_test',
    'resume_check',
    'full_assessment',
]
```

### Key endpoints (`resume/urls.py`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/resumes/` | Public | Submit application |
| POST | `/api/verify-email/` | Public | Email verification → triggers AI screening |
| GET | `/api/resumes/{id}/pipeline-status/` | Candidate Bearer | Stage list for status page |
| GET | `/api/resumes/{id}/candidate-info/` | Candidate Bearer | Name/email for KYC forms |
| POST | `/api/resumes/candidate-login/` | Public | Applicant sign-in by email + application password |
| POST | `/api/resumes/{id}/candidate-token/` | Password body | Re-issue 7-day JWT |
| POST | `/api/resumes/{id}/request-password-change/` | Candidate Bearer | Email magic link to change password |
| POST | `/api/resumes/confirm-password-change/` | Public | Body: `token`, `new_password` |
| POST | `/api/resumes/{id}/request-email-change/` | Candidate Bearer | Email magic link to change email |
| POST | `/api/resumes/confirm-email-change/` | Public | Body: `token`, `new_email` → sets unverified + sends verify email |
| POST | `/api/resumes/{id}/change-password/` | Candidate Bearer + current password | **Legacy** inline change; prefer magic-link flow |
| POST | `/api/resumes/{id}/pipeline-stage/` | Candidate Bearer | Report stage pass/fail + advance |

**URL order:** In `resume/urls.py`, all `resumes/candidate-login/`, `resumes/confirm-*`, and `resumes/<uuid>/…` custom paths must be listed **before** `include(router.urls)` — otherwise `resumes/<pk>/` swallows paths like `candidate-login` (405 on POST).

### Candidate JWT (`generate_candidate_token`)

```python
{
  'user_id': str(resume.id),   # resume UUID — used everywhere as candidate/freelancer_id
  'email': resume.email,
  'full_name': resume.full_name,
  'role': 'candidate',
  'exp': utcnow + 7 days,
}
```

Validated by `_authenticate_candidate()` — token `user_id` must match URL `resume_id`.

### Applicant account change tokens (`generate_candidate_action_token`)

Separate from session JWT (`role: candidate`). Used in email links for password/email change.

```python
{
  'user_id': str(resume.id),
  'purpose': 'change_password' | 'change_email',
  'role': 'candidate_action',
  'exp': utcnow + 24 hours,
}
```

- **Request link:** `_authenticate_candidate` + `_send_candidate_account_link_email` → frontend paths `application/change-password?token=…` / `application/change-email?token=…` (see `FRONTEND_URL`).
- **Confirm password:** `make_password(new_password)`; no session token returned (user re-signs in at `/application/track`).
- **Confirm email:** updates `email`, `is_email_verified=False`, new `verification_token`, calls `send_verification_email()`.

Helpers: `decode_candidate_action_token()`, `confirm_password_change`, `confirm_email_change`, `request_password_change_link`, `request_email_change_link` in `resume/views.py`.

### Pipeline safety rules

- **`pipeline_past_stage()`** — prevents downgrading a stage when later stages already passed (e.g. re-running AI screening must not reset KYC from `passed` to `invited`).
- **`_invite_pipeline_stage()`** — creates/activates invitations without overwriting completed progress.

### AI screening

- Triggered after email verification via `send_resume_for_screening()`.
- Uses Gemini (`GEMINI_API_KEY` in `app/.env`).
- Pass threshold: `AI_SCREENING_PASS_THRESHOLD = 60`.
- On pass → KYC stage invited + email with test links.

---

## Other Important APIs

| Area | Prefix |
|---|---|
| Users / auth | `/api/user/` |
| Projects / contracts | `/api/` (project app) |
| Assessments | `/api/` (assessment app) |
| Token refresh | `/api/user/token/refresh/` |
| Assessment termination | `/api/assessment-termination/` |

---

## Models (vetting)

- **`Resume`** — applicant record; ID doubles as candidate `user_id`.
- **`VettingPipelineRecord`** — per-stage status (`invited`, `passed`, `failed`, …), score, timestamps.
- **`ScreeningResult`** — AI screening scores per position.

---

## Testing

```bash
docker compose exec app python test_pipeline.py
```

Creates/uses test resume, walks stages, validates `PIPELINE_STAGES` alignment with frontend.

---

## Common Gotchas

- **Never hardcode `GEMINI_API_KEY`** in docker-compose — use `app/.env`.
- **Candidate token is not SimpleJWT** — custom HS256 JWT, same secret as microservices.
- **Resume ID ≠ Freelancer ID** until `create_freelancer_from_resume` / approval flows.
- **CORS** — allows frontend origin `localhost:3000` in dev.

---

## Candidate account security hardening (planned)

MVP magic-link flow is documented above. **Implement before calling production-ready:**

1. **One-time tokens** — Persist `jti` (or random id) when issuing action JWT; reject reuse after successful confirm; invalidate previous link when sending a new one.
2. **Rate limiting** — Throttle `request-*` and `confirm-*` by IP + `resume_id` (django-ratelimit, Redis, or nginx).
3. **Notification emails** — After `confirm_password_change` and after `confirm_email_change`, email the **previous** address (“If this wasn’t you, contact support”).
4. **Token transport** — Avoid long JWTs in query strings (referrer/history/logs); prefer opaque DB token or frontend URL fragment.
5. **Password policy** — Raise minimum length; optional HIBP k-anonymity check.
6. **TTL split** — Shorter expiry for `change_password` (e.g. 1h) vs `change_email` (24h).
7. **Signing key** — Dedicated secret for `candidate_action` JWTs, not shared `SECRET_KEY` across all services (or accept risk with rotation plan).
8. **Email uniqueness** — On confirm, block `new_email` if **any** `Resume` uses it, not only `is_email_verified=True`.
9. **Deprecate** `change_candidate_password` direct API if product only supports email links.

Frontend checklist: `my-react-app/CLAUDE.md` § “Candidate account security hardening (planned)”.

---

## Release readiness (vetting MVP)

**Full checklist:** [`RELEASE_READINESS.md`](./RELEASE_READINESS.md) in this repo.

### Main backend — done vs todo

| Item | Status |
|------|--------|
| `vetting_catalog.py` + stacks per service name | Done |
| `CandidateVettingProgress` + vetting APIs | Done |
| `report_proctoring_violation` | Done |
| Admin: Resume pipeline inlines, `VettingPipelineRecord` | Done |
| Migration `0106_candidatevettingprogress` | Run on deploy |
| Security: one-time tokens, rate limits | Planned |

### Current `Services.name` values (2026-06-02)

- Landing Page Development  
- Web Application Interface Development  

### Admin

**Resumes** → edit **Vetting pipeline stages** (status, score, notes). Action: **Ensure all pipeline stages exist**.

---

## Related Services

See `CLAUDE.md` in each sibling repo under `c:\toptal\`.
