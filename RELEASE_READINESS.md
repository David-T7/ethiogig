# EthioGig — Release readiness (vetting MVP)

**Last updated:** 2026-06-20  
**Maturity:** Beta vetting platform — core hire path works; production hardening incomplete.

**Current focus (June 2026):** Theoretical test MVP smoke path. Use admin **Screening configs** bypass toggles for local QA without Gemini, KYC (8005), or surveillance (8003). Full pipeline (practical, KYC, proctoring) remains implemented but deferred for sign-off.

---

## Services in database (seed must match exactly)

| `Services.name` | Hireable role label (taxonomy) | Example stacks |
|-----------------|----------------------------------|----------------|
| Landing Page Development | Frontend Developer | React Developer, Frontend Fundamentals |
| Web Application Interface Development | Frontend Developer | React Developer, Full Stack JavaScript |

### Taxonomy setup (run after deploy)

```bash
# 1. Main DB: roles, stacks, skills, service links
docker exec djangoproject-app-1 python manage.py migrate core
docker exec djangoproject-app-1 python manage.py sync_vetting_taxonomy

# 2. Test services (skill_id columns + seed content)
docker exec djangotestingproject-app-1 python manage.py migrate core
docker exec djangotest-app-1 python manage.py migrate core
docker exec djangotestingproject-app-1 python manage.py seed_vetting_tests --categories "Landing Page Development" "Web Application Interface Development"
docker exec djangotest-app-1 python manage.py seed_vetting_tests --categories "Landing Page Development" "Web Application Interface Development"

# 3. Link test UUIDs onto VettingSkill rows (from inside main container)
docker exec -e THEORETICAL_TEST_SERVICE_URL=http://host.docker.internal:8001 \
  -e PRACTICAL_TEST_SERVICE_URL=http://host.docker.internal:8002 \
  djangoproject-app-1 python manage.py link_vetting_test_ids
```

**Test services:** `ALLOWED_HOSTS` must include `host.docker.internal` and `localhost` so `link_vetting_test_ids` works from Docker.

**Canonical model:** `Service` → `VettingStack` → `VettingSkill` (`is_required` via `StackSkill`) → `theoretical_test_id` / `practical_test_id` on skill row.  
Fallback catalog: `app/resume/vetting_catalog.py` + `vetting_taxonomy_service.py` (DB-first).  
**Certificates:** `SkillCertificate` — 365-day validity, shown on application status.

---

## Minimum pass rule (candidates)

- Candidate selects **one stack** (e.g. React Developer).
- Must **pass all required skills** in that stack for **theoretical**, then **practical** (practical locked until theory passes per skill).
- Optional stack skills do not block the pipeline.
- Pipeline stages `theoretical_test` and `practical_test` auto-mark **passed** when required skills are met.
- Per-skill results: `POST /api/resumes/{id}/vetting-tech-result/` from frontend after each test.

Legacy constant `MIN_TECHNOLOGIES_TO_PASS = 2` in `vetting_catalog.py` — superseded by per-stack required skill count.

---

## Application holds

| Source | Creates hold? | Email? |
|--------|---------------|--------|
| Stage failure (`handle_stage_failure`) | Yes | Yes — subject `Application on hold — EthioGurus` |
| Proctoring (`report_proctoring_violation`) | Yes (14d / 30d) | Yes |
| AI screening fail | Yes | Yes |
| Admin `Application on holds` | Manual | Yes |

**Pipeline status API** returns `{ stages, application_hold, hold_policy }` (not a bare array).

**Resend email:** `POST /api/resumes/{id}/resend-hold-notification/` (candidate Bearer).

**Testing without holds:** Admin → **Screening configs** → check **Disable application holds**. Skips creating and enforcing holds (local QA). Clear existing holds via Resume admin actions.

### Admin testing bypasses (`ScreeningConfig` — migration `0110`)

All default **OFF**. Enable only in local/staging QA — **never in production**.

| Toggle | Effect |
|--------|--------|
| **Skip AI screening for testing** | Email verify auto-passes AI screening (no Gemini call). |
| **Skip KYC for testing** | Auto-passes KYC and invites **theoretical test** (no 8005). |
| **Disable surveillance for testing** | Frontend skips camera pre-check and in-test face proctoring (no 8003 required). |

**Pipeline status API** exposes flags as `testing_policy`: `{ skip_ai_screening, skip_kyc, disable_surveillance }` alongside `hold_policy`.

**Typical theoretical-only local stack:** 8000 + 8001 + React 3000 (8003 optional when surveillance bypass is on).

---

## End-to-end smoke test (one candidate)

### Full pipeline (production-like)

- [ ] Apply → verify email → AI screening passes (or admin sets `ai_screening` passed).
- [ ] `/application/track` → sign in with application password.
- [ ] `/application/status` — pipeline stages; hold banner if applicable; **Resend hold email** works.
- [ ] KYC + liveness → surveillance reference stored.
- [ ] `/skills-test/theoretical?position=<Services.name>&candidate_id=&token=` → select stack → pass required theory skills.
- [ ] Hub shows scores + pass/fail banner after each test; practical unlocks per skill.
- [ ] `/skills-test/practical` → pass required practical skills.
- [ ] Status page lists verified technologies / certificates.
- [ ] On hold: blocked at status/hub/camera check (not mid-test with snapshot wording).
- [ ] Admin: taxonomy synced; test IDs linked; holds clearable.

### Theoretical-only (current MVP QA — bypass toggles ON)

- [ ] Admin: enable all three testing bypasses + optionally disable holds.
- [ ] Start Docker: main (8000), theoretical (8001), React (3000).
- [ ] Run taxonomy sync + seed (see Taxonomy setup; steps 1–2 and link command sufficient for theory).
- [ ] Apply with **new email** → verify email → pipeline shows **theoretical test invited** (no KYC step).
- [ ] `/application/track` → `/application/status` → **Choose stack & tests**.
- [ ] Start a theory skill → lands on MCQ test **without** camera check when surveillance bypass is on.
- [ ] Complete test → hub pass/fail banner → `vetting-tech-result` recorded.
- [ ] Pass all **required** skills in stack → pipeline advances; certificates on status page.

**Reset applicant data for a fresh run** (main DB, from Django container):

```bash
docker exec djangoproject-app-1 python manage.py shell -c "
from core.models import *
SkillCertificate.objects.all().delete()
VettingPipelineRecord.objects.all().delete()
CandidateVettingProgress.objects.all().delete()
ResumeCheck.objects.all().delete()
ApplicationOnHold.objects.all().delete()
ScreeningResult.objects.all().delete()
Resume.objects.all().delete()
print('Applicant/vetting data cleared.')
"
```

Optional: clear theoretical submissions (`8001`) and surveillance profiles (`8003`) if retesting same browser session.

---

## Per-repository checklist

### Main backend (`ethiogig` — 8000)

- [x] Candidate JWT, pipeline APIs, proctoring violation hold
- [x] DB taxonomy: `VettingSkill`, `VettingStack`, `StackSkill`, `ServiceVettingStack`, `SkillCertificate`
- [x] `sync_vetting_taxonomy`, `link_vetting_test_ids` management commands
- [x] `vetting-stacks`, `vetting-progress`, `vetting-tech-result` APIs
- [x] `hold_policy.py` + `ScreeningConfig.disable_application_holds`
- [x] `testing_policy.py` + `ScreeningConfig` bypass toggles (AI screening, KYC, surveillance) — migration `0110`
- [x] `testing_policy` in pipeline-status API; unit tests in `resume/tests/test_testing_policy.py`
- [x] Hold notification email + `resend-hold-notification`
- [x] Migrations `0106`–`0110`
- [x] Admin: pipeline inlines, holds, screening config toggles
- [ ] One-time action tokens, rate limits (see `CLAUDE.md`)

### Frontend (`ethiogurus_frontend` — 3000)

- [x] Stack hub (`CandidateStackHubPage`), required/optional badges, scores
- [x] Test submit → `vetting-tech-result` → hub with pass/fail banner
- [x] Camera check preserves `technology`, `skill_id`, `position` query params
- [x] Hold UX: banner on status/hub; camera check blocked; no snapshot text in hold modal
- [x] `applicationHold.js` + resend hold email button
- [x] **Anti-cheat: fullscreen enforcement** — test enters fullscreen on start; exit = focus violation (same escalation ladder)
- [x] **Anti-cheat: copy/paste/right-click blocked** during active test
- [x] **Anti-cheat: devtools keyboard shortcuts blocked** (F12, Ctrl+Shift+I/J/U, PrintScreen, etc.)
- [x] **Anti-cheat: burst snapshot on focus violation** — 3 frames at 0 / 1.5 / 3 s via `triggerBurstCapture`
- [x] **Snapshot efficiency** — baseline 15 s interval (was 10 s), 320×240 @ JPEG 0.75 (~9× less data than original)
- [x] Fixed `candidateId` TDZ crash in `TestPage` (moved `useCandidateAuth` above `reportFocusViolation`)
- [x] **Testing bypass UX** — reads `testing_policy` from pipeline-status; skips camera check + surveillance when `disable_surveillance`
- [ ] Remove JWT from query strings (P1 security)

### Theoretical tests (`ethiogig-testing` — 8001)

- [x] `skill_id` on `SkillTest`; `GET /api/theoretical-tests/by-skill/<uuid>/`
- [x] `skill_id` in serializer; `ALLOWED_HOSTS` for Docker link command
- [x] `seed_vetting_tests` management command
- [x] `SkillTest.sample_size` (migration `0010`) — random question sampling per session
- [x] Question order + MCQ option order shuffled on every session (backend, no frontend change needed)
- [x] 20 curated MCQ questions per skill (HTML, CSS, JavaScript, React, Node.js, PostgreSQL); `sample_size = 15`

### Practical tests (`ethio_gig_code_testing` — 8002)

- [x] `skill_id` on `PracticalTest`; `GET /api/practical-tests/by-skill/<uuid>/`
- [x] `skill_id` in serializer; `ALLOWED_HOSTS` for Docker link command
- [x] Story-style seeds + Monaco editor on frontend
- [x] **Execution engine** — `TestCase` model (migration `0018`), Node.js subprocess replaces Judge0 (WSL2 cgroups v1 incompatibility), `submit_answer` runs all test cases + passes results to Gemini, `run-tests` dry-run endpoint
- [x] `TestCase.description` field (migration `0019`); catalog + existing DB rows have descriptions
- [x] `visible_test_cases` in `PracticalTestQuestionSerializer` (id + description per non-hidden case)
- [x] Frontend: individual test case cards (`CodingTestPage.js`) — description + ▶ play button + ✓/✗ status; Submit gated on all visible cases passing
- [x] Per-test-case individual execution (`run-test-case` endpoint; ▶ button runs only that card)
- [x] Graceful Gemini quota handling — 3-retry backoff; fallback score from test cases; follow-ups skipped silently
- [x] Technology-specific challenges per skill (HTML, CSS, React, Node.js, TypeScript)
- [ ] HTML/CSS native execution via Judge0 (currently JS string-output harnesses via Node.js; requires Judge0 WSL2/cgroups-v1 fix)

### Surveillance (8003)

- [x] Reference photo + verify snapshot APIs
- [x] Frontend: pause vs hold modal variants; hold reported to main backend
- [ ] Tune tolerance if false pauses are common

### KYC (8005)

- [x] Document + liveness flow
- [ ] Staging smoke with real document samples

---

## Admin operations

| Task | Where |
|------|--------|
| **Disable holds for testing** | Admin → **Screening configs** → **Disable application holds** |
| **Skip AI / KYC / surveillance (QA)** | Admin → **Screening configs** → three bypass checkboxes |
| Clear candidate holds | **Resumes** → action **Remove holds + reset on-hold stages** |
| Delete hold rows only | **Application on holds** → delete selected |
| Edit stage status | **Resumes** → **Vetting pipeline stages** inline |
| Taxonomy | **Vetting stacks** / **Vetting skills** / **Services** (stack inline) |
| Link test IDs | `python manage.py link_vetting_test_ids` (after test seeds) |
| Reset stack progress | **Candidate vetting progress** → edit JSON or delete row |

---

## Git / deploy (all repos under `c:\toptal\`)

| Repo | Remote |
|------|--------|
| React App | `ethiogurus_frontend` |
| Django Project | `ethiogig` |
| Django Testing Project | `ethiogig-testing` |
| Django Test | `ethio_gig_code_testing` |
| Surveillance System | `Camera-Surveillance-System-` |
| ID Verification | `IDVerification` |

Before release tag: migrate all DBs, run taxonomy sync + link command, seed tests, restart Docker stacks, run one full candidate smoke test.

---

## Known risks

1. **String coupling** — legacy `category` / `position` must match `Services.name` where DB taxonomy not used.
2. **Dual state** — `VettingPipelineRecord` vs `CandidateVettingProgress` can disagree if only one is updated.
3. **Email delivery** — Brevo/SMTP in `app/.env`; holds saved even if send fails (use resend endpoint).
4. **Heavy local dev** — five backends + React; document ports in each `CLAUDE.md`.
5. **Root `node_modules` in React App repo** — keep gitignored; dependencies live under `my-react-app/`.
