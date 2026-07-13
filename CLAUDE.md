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
| `CHAPA_SECRET_KEY` | Chapa payment gateway (test key from dashboard.chapa.co) — **never commit** |
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
| GET | `/api/resumes/{id}/pipeline-status/` | Candidate Bearer | `{ stages, application_hold, hold_policy }` |
| POST | `/api/resumes/{id}/resend-hold-notification/` | Candidate Bearer | Resend on-hold email |
| GET | `/api/resumes/{id}/vetting-stacks/` | Candidate Bearer | Stacks for applied position |
| GET/POST | `/api/resumes/{id}/vetting-progress/` | Candidate Bearer | Stack selection + skill progress |
| POST | `/api/resumes/{id}/vetting-tech-result/` | Candidate Bearer | Per-skill theory/practical result |
| POST | `/api/resumes/{id}/proctoring-violation/` | Candidate Bearer | Camera hold (14d/30d) |
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

### Contract & Escrow endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/contracts/<id>/cancel/` | Client Bearer | Cancel contract; refunds funded escrows via Chapa |
| POST | `/api/payments/escrow/<id>/initialize/` | Client Bearer | Start Chapa payment for escrow funding |
| GET | `/api/payments/escrow/<id>/verify/` | Client Bearer | Verify Chapa payment; sets `deposit_confirmed=True` |
| POST | `/api/payments/webhook/` | Public (Chapa) | Server-to-server Chapa callback; double-verifies before confirming |
| GET/PUT | `/api/user/bank-account/` | Freelancer Bearer | Freelancer payout bank account details |

### WebSocket endpoints

| Route | Consumer | Purpose |
|---|---|---|
| `ws/chat/<chat_id>/?token=<jwt>` | `ChatConsumer` | Real-time per-chat messaging |
| `ws/inbox/?token=<jwt>` | `InboxConsumer` | User-level push; fires when any chat receives a new message |

**Channel layer:** Redis via `channels_redis` (`CHANNEL_LAYERS` in settings). Celery and WebSockets share the same Redis instance.

---

## Models (vetting)

- **`Resume`** — applicant record; ID doubles as candidate `user_id`.
- **`VettingPipelineRecord`** — per-stage status (`invited`, `passed`, `failed`, `on_hold`, …), score, timestamps.
- **`CandidateVettingProgress`** — selected stack, `technology_results` JSON per skill.
- **`VettingSkill` / `VettingStack` / `StackSkill` / `ServiceVettingStack`** — DB taxonomy (required vs optional skills).
- **`SkillCertificate`** — 365-day skill verification after theory + practical pass.
- **`ApplicationOnHold`** — email + position + `hold_until`; enforced unless `ScreeningConfig.disable_application_holds`.
- **`ScreeningResult`** — AI screening scores per position.

## Models (contract & payment)

- **`Escrow`** — one per contract (or per milestone if milestone-based). Statuses: `Pending`, `Released`, `Refunded`. Auto-created via Django signal (`project/signals.py`) when `Contract.status` becomes `accepted`.
  - `release()` — blocked if open dispute exists or not funded; pays out freelancer via `_payout_to_freelancer()`.
  - `refund()` — calls Chapa `POST /v1/refunds`; marks `Refunded` on success or failure (for manual tracking).
- **`FreelancerBankAccount`** — OneToOne with `Freelancer`. Stores `account_type`, `account_number`, `account_name`, `bank_code` for Chapa payouts. Migration `0112`.
- **`Dispute`** — `contract` + optional `milestone` FK; `status` in `open / cancelled / resolved / auto_resolved / drc_forwarded`.

### Celery tasks (`core/tasks.py`)

| Task | Schedule | Purpose |
|------|----------|---------|
| `auto_resolve_disputes` | Hourly | Auto-closes disputes past their response deadline; notifies both parties |
| `remove_expired_holds` | Daily 2 AM | Deletes expired `ApplicationOnHold` rows; emails candidate |
| `update_expired_holds` | Daily 2:30 AM | Resets `FullAssessment` holds past `hold_until` |

Celery app: `ethiogig/celery.py`. Beat uses `DatabaseScheduler` (django-celery-beat). docker-compose services: `celery -A ethiogig worker` and `celery -A ethiogig beat`.

### Taxonomy commands

```bash
python manage.py sync_vetting_taxonomy
python manage.py link_vetting_test_ids   # needs test services on 8001/8002; use host.docker.internal from Docker
```

Logic: `resume/vetting_taxonomy_service.py` (DB-first, fallback `vetting_catalog.py`).

### Hold policy (`resume/hold_policy.py`)

- `application_holds_enabled()` — reads `ScreeningConfig.disable_application_holds`.
- `active_application_hold(resume)` — returns `None` when holds disabled for testing.
- Hold emails: `_safe_send_application_hold_email()` — subject `Application on hold — EthioGurus`.

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

## Candidate account security hardening

All items implemented. See `RELEASE_READINESS.md` for details.

1. ✅ **One-time tokens** — `CandidateActionToken.jti` stored in DB; `redeem_candidate_action_token` marks used with `select_for_update`; replayed links rejected.
2. ✅ **Rate limiting** — `_check_action_token_rate_limit`: max 3 requests per resume/purpose per hour (DB-based).
3. ✅ **Notification emails** — `_send_account_change_notification_email` sends “if this wasn’t you” email to previous address after password or email change.
4. ✅ **Token transport** — Magic links carry a UUID (not a JWT); `CANDIDATE_ACTION_SECRET_KEY` is now unused; frontend strips token from URL with `replaceState` on mount.
5. ✅ **Password policy** — Minimum length raised to 8 on all password-set paths.
6. ✅ **TTL split** — Password-change links: 1 hour. Email-change links: 24 hours. Stored in `CandidateActionToken.expires_at` (migration `0116`).
7. ✅ **Signing key** — `CANDIDATE_ACTION_SECRET_KEY` superseded by opaque UUID approach; kept in settings for backward env-var compatibility but not read by code.
8. ✅ **Email uniqueness** — `confirm_email_change` blocks `new_email` if any `Resume` uses it (not just verified ones).
9. **Deprecate `change_candidate_password`** — legacy endpoint still exists; product uses magic-link flow only. Remove in a future cleanup once confirmed no clients call it.

Frontend checklist: `my-react-app/CLAUDE.md` § “Candidate account security hardening (planned)”.

---

## Release readiness (vetting MVP)

**Full checklist:** [`RELEASE_READINESS.md`](./RELEASE_READINESS.md) in this repo.

### Main backend — done vs todo

| Item | Status |
|------|--------|
| DB taxonomy + `sync_vetting_taxonomy` / `link_vetting_test_ids` | Done |
| `CandidateVettingProgress` + vetting APIs | Done |
| Pass **all required skills** per stack (not fixed count of 2) | Done |
| `report_proctoring_violation` + hold emails + resend endpoint | Done |
| `disable_application_holds` on ScreeningConfig (admin) | Done |
| **Testing bypasses** — skip email verify / AI screening / KYC / surveillance (`testing_policy.py`, migrations `0110`–`0111`) | Done |
| Admin: holds clear actions, Screening config toggles, taxonomy models | Done |
| Migrations `0106`–`0115` | Run on deploy |
| Security audit — auth/ownership/race across all 6 services | Done (2026-07-08) |
| Security: one-time action tokens, rate limits (prod hardening) | Planned |
| Chapa escrow + payout + refund | Done |
| `FreelancerBankAccount` + bank-account API | Done |
| `CancelContractView` + escrow refund on cancel | Done |
| Escrow freeze when dispute open | Done |
| `auto_resolve_disputes` Celery task + beat schedule | Done |
| WebSocket chat (`ChatConsumer`) + inbox push (`InboxConsumer`) | Done |
| SendGrid removed → Django `EmailMultiAlternatives` | Done |

### Testing bypasses (local QA only)

Admin → **Screening configs** (`core.models.ScreeningConfig`):

| Field | Backend module | Effect |
|-------|----------------|--------|
| `skip_email_verification_for_testing` | `resume/testing_policy.py` | Submit → auto-verify email + start screening |
| `skip_ai_screening_for_testing` | same | Auto-pass AI screening (no Gemini) |
| `skip_kyc_for_testing` | same | Auto-pass KYC → invite theoretical test |
| `disable_surveillance_for_testing` | same + pipeline-status API | Frontend skips camera check / face proctoring |

`GET /api/resumes/{id}/pipeline-status/` returns `testing_policy` alongside `hold_policy`.

**Theoretical-only E2E smoke passed 2026-06-30.** Contract/payment/chat system implemented (see `RELEASE_READINESS.md` § Contract, Escrow & Payment system).

### Current `Services.name` values (2026-06-02)

- Landing Page Development  
- Web Application Interface Development  

### Admin

| Task | Location |
|------|----------|
| Disable holds (testing) | **Screening configs** → **Disable application holds** |
| Skip email / AI / KYC / surveillance (QA) | **Screening configs** → bypass checkboxes |
| Clear holds | **Resumes** → **Remove holds + reset on-hold stages** |
| Edit stages | **Resumes** → **Vetting pipeline stages** inline |
| Taxonomy | **Vetting stacks**, **Vetting skills**, **Services** (stack inline) |

---

## Related Services

See `CLAUDE.md` in each sibling repo under `c:\toptal\`.
