# EthioGig — Release readiness (vetting MVP)

**Last updated:** 2026-06-02  
**Maturity:** Beta vetting platform — core hire path works; production hardening incomplete.

---

## Services in database (seed must match exactly)

| `Services.name` | Stacks (examples) | Technologies seeded |
|-----------------|-------------------|---------------------|
| Landing Page Development | React Developer, Frontend Fundamentals | React, JavaScript, HTML, CSS |
| Web Application Interface Development | React Developer, Full Stack JavaScript | React, JavaScript, HTML, CSS, Node.js, PostgreSQL |

After adding a new service in admin:

```bash
docker exec djangotestingproject-app-1 python manage.py seed_vetting_tests --categories "Your Service Name"
docker exec djangotest-app-1 python manage.py seed_vetting_tests --categories "Your Service Name"
```

Add stack definitions in `app/resume/vetting_catalog.py` and both test `vetting_catalog.py` files if the name is not covered by fuzzy matching.

---

## Minimum pass rule (candidates)

- Candidate selects **one stack** (e.g. MERN Developer, React Developer).
- Must **pass theoretical** tests for **≥ 2 technologies** in that stack.
- Must **pass practical** for the same technologies (practical locked until theory passes per tech).
- Pipeline stages `theoretical_test` and `practical_test` auto-mark **passed** when counts are met.
- Verified skills sync to `CandidateVettingProgress.verified_technologies` → freelancer `skills` on approval.

Config: `MIN_TECHNOLOGIES_TO_PASS = 2` in `app/resume/vetting_catalog.py`.

---

## End-to-end smoke test (one candidate)

- [ ] Apply for a position → verify email → AI screening passes (or admin sets `ai_screening` passed).
- [ ] `/application/track` → sign in with application password.
- [ ] `/application/status` shows pipeline; KYC link works if stage invited.
- [ ] KYC + liveness → surveillance reference stored.
- [ ] `/skills-test/theoretical?position=<Services.name>&candidate_id=&token=` → select stack → pass 2 theory tests.
- [ ] `/skills-test/practical` → pass 2 practical tests for same technologies.
- [ ] Status page shows **On Hold** / **Passed** correctly; verified technologies listed.
- [ ] Admin: **Resumes** → inline pipeline stages editable; action **Ensure all pipeline stages exist**.

---

## Per-repository checklist

### Main backend (`ethiogig` — 8000)

- [x] Candidate JWT auth, pipeline APIs, proctoring violation hold
- [x] `CandidateVettingProgress`, vetting stacks/progress/tech-result APIs
- [x] Django admin: pipeline inlines + `VettingPipelineRecord` list edit
- [x] Migration `0106_candidatevettingprogress`
- [ ] One-time action tokens, rate limits (see `CLAUDE.md` security section)
- [ ] `sync_services` management command (optional) to validate catalog vs DB

### Frontend (`ethiogurus_frontend` — 3000)

- [x] Applicant track/status, magic-link email/password change
- [x] Stack hub, Monaco practical editor, camera/proctoring UX
- [ ] Remove JWT from query strings (P1 security)
- [ ] Error boundary, loading skeletons

### Theoretical tests (`ethiogig-testing` — 8001)

- [x] `GET /api/theoretical-tests/by-category/<category>/`
- [x] `seed_vetting_tests` management command
- [ ] Regenerate richer question banks per technology (optional)

### Practical tests (`ethio_gig_code_testing` — 8002)

- [x] Story-style challenges in seed data
- [x] `GET /api/practical-tests/by-category/<category>/`
- [x] `seed_vetting_tests` management command

### Surveillance (8003)

- [x] Verify snapshot + reference photo APIs
- [ ] Tune `tolerance` / pause copy if too many false pauses

### KYC (8005)

- [x] Document + liveness flow
- [ ] Staging smoke with real document samples

---

## Admin operations

| Task | Where |
|------|--------|
| Edit stage status | Admin → Resumes → **Vetting pipeline stages** inline |
| Bulk edit stages | Admin → **Vetting pipeline records** |
| Clear proctoring hold | Resume action **Delete active application holds** or Application on holds |
| Reset stack progress | Admin → **Candidate vetting progress** → edit JSON or delete row |

**Avoid drift:** Prefer editing pipeline **status** in admin; tech results live in `CandidateVettingProgress`. If you mark a stage passed manually, ensure it matches business rules.

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

Before release tag: run migrations on main DB, seed tests for every `Services.name`, restart Docker stacks, run one full candidate smoke test.

---

## Known risks

1. **String coupling** — `category` / `position` must match `Services.name` (case-insensitive seed lookup).
2. **Dual state** — `VettingPipelineRecord` vs `CandidateVettingProgress` can disagree if only one is updated.
3. **Heavy local dev** — five backends + React; document ports in each `CLAUDE.md`.
4. **Root `node_modules` in React App repo** — keep gitignored; dependencies live under `my-react-app/`.
