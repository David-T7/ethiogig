# EthioGig — Release readiness (vetting MVP)

**Last updated:** 2026-06-02  
**Maturity:** Beta vetting platform — core hire path works; production hardening incomplete.

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

---

## End-to-end smoke test (one candidate)

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

---

## Per-repository checklist

### Main backend (`ethiogig` — 8000)

- [x] Candidate JWT, pipeline APIs, proctoring violation hold
- [x] DB taxonomy: `VettingSkill`, `VettingStack`, `StackSkill`, `ServiceVettingStack`, `SkillCertificate`
- [x] `sync_vetting_taxonomy`, `link_vetting_test_ids` management commands
- [x] `vetting-stacks`, `vetting-progress`, `vetting-tech-result` APIs
- [x] `hold_policy.py` + `ScreeningConfig.disable_application_holds`
- [x] Hold notification email + `resend-hold-notification`
- [x] Migrations `0106`–`0108`
- [x] Admin: pipeline inlines, holds, screening config toggle
- [ ] One-time action tokens, rate limits (see `CLAUDE.md`)

### Frontend (`ethiogurus_frontend` — 3000)

- [x] Stack hub (`CandidateStackHubPage`), required/optional badges, scores
- [x] Test submit → `vetting-tech-result` → hub with pass/fail banner
- [x] Camera check preserves `technology`, `skill_id`, `position` query params
- [x] Hold UX: banner on status/hub; camera check blocked; no snapshot text in hold modal
- [x] `applicationHold.js` + resend hold email button
- [ ] Remove JWT from query strings (P1 security)

### Theoretical tests (`ethiogig-testing` — 8001)

- [x] `skill_id` on `SkillTest`; `GET /api/theoretical-tests/by-skill/<uuid>/`
- [x] `skill_id` in serializer; `ALLOWED_HOSTS` for Docker link command
- [x] `seed_vetting_tests` management command
- [ ] Richer question banks (optional)

### Practical tests (`ethio_gig_code_testing` — 8002)

- [x] `skill_id` on `PracticalTest`; `GET /api/practical-tests/by-skill/<uuid>/`
- [x] `skill_id` in serializer; `ALLOWED_HOSTS` for Docker link command
- [x] Story-style seeds + Monaco editor on frontend

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
