# EthioGig — Developer Reference

EthioGig is a Toptal-style freelance talent marketplace for Ethiopia. It connects vetted freelancers with clients through a rigorous multi-stage assessment pipeline, AI-powered resume screening, contract/escrow management, and dispute resolution.

---

## Architecture Overview

```
app/
├── core/           # Custom User models, shared models, Celery config
├── user/           # Auth, registration, profile management, chat, notifications
├── resume/         # Resume submission, Gemini AI screening, resume checker workflow
├── interview/      # Appointment scheduling, interviewer assignment, interview records
├── assessment/     # FullAssessment workflow (soft skills → depth → live → project)
├── project/        # Projects, Contracts, Milestones, Escrow, CounterOffers, Disputes
├── services/       # Services (positions), Technologies, Fields, freelancer search
├── dispute_docs/   # Supporting documents for dispute resolution
└── ethiogig/       # Django settings, root URL config, WSGI/ASGI
```

**Infrastructure:** Django 5.0.6 · PostgreSQL · Redis · Celery + Celery Beat · Docker Compose

---

## Running the Project

```bash
# Start all services (app, db, redis, celery worker, celery beat)
docker-compose up --build -d

# View logs
docker-compose logs -f app
docker-compose logs -f celery

# Run migrations
docker-compose exec app python manage.py migrate

# Create superuser
docker-compose exec app python manage.py createsuperuser

# Setup periodic tasks (celery beat schedule)
docker-compose exec app python manage.py setup_periodic_tasks

# Open Django shell
docker-compose exec app python manage.py shell
```

The app runs on **http://localhost:8000**.  
API docs (Swagger): **http://localhost:8000/api/docs/**  
Django admin: **http://localhost:8000/admin/**

---

## Environment Variables

Set in `.env` (app directory) and referenced in `docker-compose.yml`:

| Variable | Purpose |
|---|---|
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASS` | PostgreSQL connection |
| `GEMINI_API_KEY` | Google Generative AI for resume screening |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP (Brevo) for transactional email |
| `DEFAULT_FROM_EMAIL` | Sender address |

> **Note:** `GEMINI_API_KEY` is currently hardcoded in `docker-compose.yml` — move it to `.env` before any production deployment.

---

## User Model Hierarchy

All role models inherit from the custom `User` base (email as `USERNAME_FIELD`, UUID PK):

```
User (AbstractBaseUser)
├── Freelancer     — skills, portfolio, hourly rate, availability
├── Client         — company info, projects posted
├── Interviewer    — expertise, working hours, interview type (technical / soft / live)
├── ResumeChecker  — working hours, daily/weekly capacity
└── DisputeManager — dispute capacity
```

**Admin registration:** `Interviewer`, `ResumeChecker`, and `DisputeManager` must be registered with `UserAdmin`-based admin classes (already done in `core/admin.py`) so that passwords are hashed correctly on creation.

---

## API Structure

Base path: `/api/`  
Authentication: JWT Bearer tokens (SimpleJWT) — 60-day access, 120-day refresh.

| Prefix | App | Notes |
|---|---|---|
| `/api/user/` | user | Auth, profiles, chat, notifications |
| `/api/resumes/` | resume | Resume CRUD + screening |
| `/api/appointments/`, `/api/interviews/` | interview | Scheduling |
| `/api/assessments/` | assessment | FullAssessment records |
| `/api/projects/`, `/api/contracts/`, `/api/disputes/` | project | Project lifecycle |
| `/api/services/`, `/api/technologies/` | services | Skill taxonomy |

---

## Freelancer Vetting Pipeline

```
Resume Submitted
      ↓
AI Screening (Gemini)  ←  ScreeningConfig defines criteria per position
      ↓
ResumeChecker Review   ←  Admin assigns ResumeChecker; result stored in ResumeCheck
      ↓
FullAssessment Created
      ├── soft_skills  (Interviewer — soft skills type)
      ├── depth        (Interviewer — technical type)
      ├── live         (Interviewer — live interview type)
      └── project      (Final project-based evaluation)
      ↓
Freelancer Approved / Rejected
```

---

## Celery Tasks

| Task | Location | Schedule |
|---|---|---|
| `update_expired_holds` | `core/tasks.py` | Periodic (beat) — reactivates expired assessment holds |
| `remove_expired_holds` | `core/tasks.py` | Periodic (beat) — clears expired holds |
| `check_unresolved_disputes` | `project/tasks.py` | Periodic (beat) — auto-escalates unresolved disputes |

Beat schedule is stored in the database (`django_celery_beat`) and seeded by `setup_periodic_tasks`.

---

## Key Third-Party Integrations

| Integration | Package | Usage |
|---|---|---|
| Google Gemini AI | `google-generativeai` | Resume screening in `resume/utils.py` |
| SendGrid / Brevo | `django-sendgrid-v5` | Transactional email (verification, password reset, notifications) |
| AWS S3 | `boto3` | File/document storage |
| SimpleJWT | `djangorestframework-simplejwt` | Token-based auth |
| drf-spectacular | `drf-spectacular` | Auto-generated OpenAPI/Swagger docs |
| Celery + Redis | `celery`, `redis` | Async tasks and periodic jobs |

---

## Code Conventions

- **REST framework style:** Views use DRF `GenericAPIView`, `ModelViewSet`, and `APIView`. Serializers live in `<app>/serializers.py`.
- **Permissions:** `IsAuthenticated` is the default. Role checks are done inside view logic by detecting the model type (e.g., `hasattr(user, 'freelancer')`).
- **Signals / hooks:** Not used — business logic lives in views and tasks.
- **Migrations:** Two pending untracked migrations in `core/migrations/` (`0101`, `0102`) — run `migrate` after pulling.
- **No comments by default:** Code is self-documenting via naming. Only add a comment when the *why* is non-obvious.

---

## Common Gotchas

- **Password hashing for staff users:** Always register `User`-subclass models with a `UserAdmin`-based admin class. Plain `ModelAdmin` skips hashing.
- **JWT lifetime is long (60 days):** Intentional for the current dev stage — tighten before production.
- **CORS:** Only `localhost:3000` is allowed. Update `CORS_ALLOWED_ORIGINS` in settings before deploying.
- **`working_hours_start/end` default:** Uses `timezone.now` (a callable), which captures the time at startup, not a static default. Set explicit `datetime.time` defaults if predictable values are needed.
- **Celery broker URL:** Hardcoded as `redis://redis:6379/0` — the `redis` hostname resolves only inside Docker Compose. For local dev without Docker, change to `redis://localhost:6379/0`.
