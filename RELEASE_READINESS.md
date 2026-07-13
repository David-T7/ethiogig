# EthioGig — Release readiness (vetting MVP)

**Last updated:** 2026-07-13  
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

### Admin testing bypasses (`ScreeningConfig` — migrations `0110`–`0111`)

All default **OFF**. Enable only in local/staging QA — **never in production**.

| Toggle | Effect |
|--------|--------|
| **Skip email verification for testing** | Application submit marks email verified immediately; screening starts (no verification email). |
| **Skip AI screening for testing** | Auto-passes AI screening (no Gemini call). |
| **Skip KYC for testing** | Auto-passes KYC and invites **theoretical test** (no 8005). |
| **Disable surveillance for testing** | Frontend skips camera pre-check and in-test face proctoring (no 8003 required). |
| **Require manual proctoring** | When ON, `pipeline-status` returns `manual_proctoring.required: true`; candidates must connect via WebRTC to a live proctor before any test. Default OFF — keep OFF unless testing the proctoring feature itself. |

**Pipeline status API** exposes flags as `testing_policy`: `{ skip_email_verification, skip_ai_screening, skip_kyc, disable_surveillance }` alongside `hold_policy`.

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

- [x] Admin: enable all four testing bypasses + optionally disable holds.
- [x] Start Docker: main (8000), theoretical (8001), React (3000).
- [x] Run taxonomy sync + seed (see Taxonomy setup; steps 1–2 and link command sufficient for theory).
- [x] Apply with **new email** → sign in at `/application/track` immediately (no inbox step).
- [x] `/application/track` → `/application/status` → **Choose stack & tests**.
- [x] Start a theory skill → lands on MCQ test **without** camera check when surveillance bypass is on.
- [x] Complete test → hub pass/fail banner → `vetting-tech-result` recorded.
- [x] Pass all **required** skills in stack → pipeline advances; certificates on status page.

**E2E smoke passed: 2026-06-30. Theoretical test MVP is shippable.**

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
ProctorSession.objects.all().delete()
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
- [x] `testing_policy.py` + `ScreeningConfig` bypass toggles (email verify, AI screening, KYC, surveillance) — migrations `0110`–`0111`
- [x] `testing_policy` in pipeline-status API + apply response; unit tests in `resume/tests/test_testing_policy.py`
- [x] Hold notification email + `resend-hold-notification`
- [x] Migrations `0106`–`0114`
- [x] Admin: pipeline inlines, holds, screening config toggles
- [x] **Security: one-time action tokens** — `CandidateActionToken` model (migration `0113`); `generate_candidate_action_token` saves `jti` to DB; `redeem_candidate_action_token` validates one-time use with `select_for_update`; replayed links rejected
- [x] **Security: rate limiting** — `_check_action_token_rate_limit` on `request-password-change` and `request-email-change`; max 3 per resume/purpose per hour (DB-based, no extra cache infra)
- [x] **Security: opaque magic-link tokens** — magic links now carry a UUID (`jti`) instead of a JWT; no secret key needed; expiry stored in `expires_at` DB field (migration `0116`); `CANDIDATE_ACTION_SECRET_KEY` is now unused
- [x] **Security: TTL split** — password-change links expire in 1 hour; email-change links expire in 24 hours
- [x] **Security: notification emails** — after `confirm_password_change` and `confirm_email_change`, previous address receives "If this wasn't you, contact support" email
- [x] **Security: email uniqueness** — `confirm_email_change` blocks any `Resume` using `new_email` (was: only `is_email_verified=True`)
- [x] **Security: password policy** — minimum length raised to 8 on all three password-set paths (magic-link confirm, legacy direct endpoint, frontend validation)
- [x] **Manual live proctoring** — `Proctor` (User MTI), `ProctorSession`, `ProctorFlag` models (migration `0117`); `ScreeningConfig.require_manual_proctoring`; 5 REST endpoints; `ProctorSessionConsumer` WebSocket signaling with dual auth; `manual_proctoring_required()` in `testing_policy.py`; `pipeline-status` returns `manual_proctoring` block

### Frontend (`ethiogurus_frontend` — 3000)

- [x] Stack hub (`CandidateStackHubPage`), required/optional badges, scores
- [x] Test submit → `vetting-tech-result` → hub with pass/fail banner
- [x] Camera check preserves `technology`, `skill_id`, `position` query params
- [x] Hold UX: banner on status/hub; camera check blocked; no snapshot text in hold modal
- [x] `applicationHold.js` + resend hold email button
- [x] **Anti-cheat: fullscreen enforcement** — test enters fullscreen on start; exit immediately blocks test with overlay until user returns (was just counting violations)
- [x] **Anti-cheat: copy/paste/right-click blocked** during active test
- [x] **Anti-cheat: devtools keyboard shortcuts blocked** (F12, Ctrl+Shift+I/J/U, PrintScreen, etc.)
- [x] **Anti-cheat: browser back button intercepted** — `popstate` trap shows custom warning modal; "Leave anyway" fires terminal violation before navigating
- [x] **Anti-cheat: tab close / refresh blocked** — native `beforeunload` dialog + `pagehide` keepalive fetch records violation if user confirms leave
- [x] **Anti-cheat: violation counter survives refresh** — count written to localStorage on every violation; restored on session reload so escalation ladder can't be reset by refreshing
- [x] **Anti-cheat: burst snapshot on focus violation** — 3 frames at 0 / 1.5 / 3 s via `triggerBurstCapture`
- [x] **Snapshot efficiency** — baseline 15 s interval (was 10 s), 320×240 @ JPEG 0.75 (~9× less data than original)
- [x] **Session recovery** — answers + question index saved to localStorage on every change; restored on power outage / accidental refresh with yellow "session restored" banner
- [x] **Test UX** — Back button added; "Submit & next" → "Next"; answer options are full-width selectable cards (A/B/C/D) instead of radio buttons
- [x] **Hub accessible after passing** — pipeline status shows "Assessment hub (optional tests)" link even when `theoretical_test` is `passed`
- [x] **Pass threshold from ScreeningConfig** — `passing_score_threshold` field now actually applied in `report_vetting_tech_result` (was stored but ignored; test service threshold was used instead)
- [x] **Application status button disabled during test** — `CandidateLayout` detects active test routes and renders a non-clickable span instead of a link
- [x] Fixed `candidateId` TDZ crash in `TestPage` (moved `useCandidateAuth` above `reportFocusViolation`)
- [x] **Testing bypass UX** — reads `testing_policy` from pipeline-status; skips camera when `disable_surveillance`; apply page reflects `email_verification_required`
- [x] **Security: JWT stripped from URL** — `useCandidateAuth` saves token to sessionStorage then `replaceState` removes `?token=` from URL; 8 files updated to never put session JWT in navigation URLs; magic-link pages (`change-password`, `change-email`) strip action token from URL on mount
- [x] **Manual live proctoring (frontend)** — `CandidateProctorWaitingRoom` (WebRTC offer, camera + screen), `ProctorPage` / `ProctorDashboard` / `ProctorSessionTile` (answer side); `/proctor` route; `CandidateStackHubPage` intercepts `startTest`; `applicationHold.js` returns `manualProctoring`

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
| **Skip email / AI / KYC / surveillance (QA)** | Admin → **Screening configs** → bypass checkboxes |
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

## Contract, Escrow & Payment system (2026-06-30)

### Backend

| Item | Status |
|------|--------|
| `Escrow` auto-created via Django signal on `Contract.status → accepted` | Done |
| `Escrow.release()` bug fixes (missing `save()`, wrong status, double-release guard) | Done |
| `Escrow.release()` frozen when open dispute exists on contract/milestone | Done |
| `Escrow.refund()` — calls Chapa `POST /v1/refunds`; marks `Refunded` on success, `RefundFailed` on failure | Done |
| `Escrow.status` choices: `Pending`, `Released`, `Refunded`, `RefundFailed` — migration `0114` | Done |
| `FreelancerBankAccount` model (OneToOne with Freelancer) — migration `0112` | Done |
| `FreelancerBankAccountView` (`GET`/`PUT` `/api/user/bank-account/`) | Done |
| Chapa `initialize_payment`, `verify_payment`, `transfer_to_bank`, `refund_payment` | Done |
| Escrow payment views: initialize, verify, webhook (`/api/payments/escrow/…`) | Done |
| `CancelContractView` — validates ownership, blocks on open dispute, refunds escrows, notifies | Done (`POST /api/contracts/<id>/cancel/`) |
| `CancelContractView` — **blocks cancellation of `active` contracts**; escrow loop wrapped in `select_for_update` + `transaction.atomic()` to prevent double-refund race | Done |
| `FreelancerCancelContractView` — freelancer cancels `pending`/`accepted` contract when no escrow is funded; deletes unfunded escrows, notifies both parties | Done (`POST /api/contracts/<id>/freelancer-cancel/`) |
| `ApproveMilestoneView` — client approves `pendingApproval` milestone; triggers `escrow.release()` → Chapa payout; auto-closes contract when all milestones complete | Done (`POST /api/milestones/<id>/approve/`) |
| `CancelMilestoneView` — client cancels single milestone (`pending`/`accepted` only); refunds funded escrow via Chapa or deletes unfunded; blocks on open dispute | Done (`POST /api/milestones/<id>/cancel/`) |
| `ContractViewSet.update()` — auto-calls `escrow.release()` when non-milestone contract set to `completed` | Done |
| `Escrow` registered in Django admin with status filter — `RefundFailed` escrows visible for manual action | Done |
| `MilestoneSerializer.validate()` — sum of milestone amounts ≤ `contract.amount_agreed` | Done |
| `auto_resolve_disputes` Celery task — runs hourly; handles no-response + no-counter-response cases | Done |
| `celery.py` in `ethiogig/` — Celery app wired; `__init__.py` exposes `celery_app` | Done |
| `CELERY_BEAT_SCHEDULE` in `settings.py` — dispute resolution, hold expiry tasks | Done |
| `docker-compose.yml` — celery/beat use `-A ethiogig`; beat uses `DatabaseScheduler` | Done |
| SendGrid removed; all emails use Django `EmailMultiAlternatives` | Done |
| `CHAPA_SECRET_KEY` in `.env.example`; read via `os.environ.get` in settings | Done |
| Migrations `0111` (ScreeningConfig), `0112` (FreelancerBankAccount) | Run on deploy |

### Frontend

| Item | Status |
|------|--------|
| `ContractDetailsPage` — Escrow Payments section; Fund Escrow button → Chapa checkout | Done |
| `ContractDetailsPage` — Activate Project blocked until all escrows funded | Done |
| `ContractDetailsPage` — Cancel Contract button hidden for `active` contracts; inline error/warning banners replace `alert()` | Done |
| `ContractDetailsPage` — milestone cards show **Approve & Release Payment** button when `pendingApproval`; calls `ApproveMilestoneView` | Done |
| `PaymentSuccessPage` — verifies payment on return from Chapa, shows status | Done |
| `FreelancerSettingsPage` — Payout Bank Account form (type, account number, name, bank code) | Done |
| `CreateContractPage` — live milestone total bar; submit blocked when total ≠ contract amount | Done |
| Inbox (`Inbox.js`, `freelancerMessages.js`) — replaced 10-second polling with WebSocket (`ws/inbox/`) | Done |
| `REACT_APP_WS_URL=ws://localhost:8000` in `.env` | Done |

### WebSocket / Real-time chat

| Item | Status |
|------|--------|
| `ChatConsumer` — JWT auth, saves messages, broadcasts to chat room group | Done |
| `InboxConsumer` — user-level WS at `ws/inbox/`; receives push when any chat gets a new message | Done |
| `ChatConsumer` sends to recipient's `inbox_{user_id}` group on each saved message | Done |
| Routes: `ws/chat/<chat_id>/` and `ws/inbox/` | Done |
| `CHANNEL_LAYERS` using Redis via `channels_redis` | Done |
| `REACT_APP_WS_URL` in frontend `.env` | Done |

### Pending / not yet implemented

- ~~Partial cancellation~~ — `CancelMilestoneView` (`POST /api/milestones/<id>/cancel/`) — Done
- Automated refund retry — deferred pending Chapa idempotency confirmation (risk of double-refund without it); `RefundFailed` escrows handled manually via admin

---

## Manual Live Proctoring (2026-07-13)

Human proctor monitors candidates via WebRTC (camera + full screen share) during skills tests. Configurable per admin toggle. One proctor handles multiple candidates simultaneously.

### Backend

| Item | Status |
|------|--------|
| `Proctor` model — User MTI, `max_concurrent_sessions` | Done |
| `ProctorSession` model — status machine `pending → proctor_joined → active → completed / terminated` | Done |
| `ProctorFlag` model — violation notes | Done |
| `ScreeningConfig.require_manual_proctoring` toggle | Done |
| `manual_proctoring_required()` in `testing_policy.py` | Done |
| `init_proctor_session` — auto-assign least-loaded proctor, idempotent | Done |
| `ProctorSessionListView` — proctor's active sessions | Done |
| `FlagProctorSessionView` | Done |
| `TerminateProctorSessionView` — creates 14-day `ApplicationOnHold`, sends hold email | Done |
| `CompleteProctorSessionView` | Done |
| `ProctorSessionConsumer` — WS signaling, dual auth (candidate JWT + proctor SimpleJWT) | Done |
| `ws/proctor/<session_id>/` route in `user/routing.py` | Done |
| `pipeline-status` returns `manual_proctoring: { required, session }` | Done |
| Migration `0117` (Proctor, ProctorSession, ProctorFlag, `require_manual_proctoring`) | Run on deploy |
| Admin: `ProctorAdmin`, `ProctorSessionAdmin`, `ProctorFlagInline` | Done |

### Frontend

| Item | Status |
|------|--------|
| `CandidateProctorWaitingRoom` — `getUserMedia` + `getDisplayMedia`, POST init session, WS connect, WebRTC offer, `onReady()` callback | Done |
| `ProctorSessionTile` — WS connect as proctor, receive offer, answer, split stream into camera + screen video refs, flag form, terminate confirm | Done |
| `ProctorDashboard` — polls `/api/proctor/sessions/` every 12 s, grid of tiles, mark-complete button | Done |
| `ProctorPage` — login form → `proctor_token` in sessionStorage → dashboard | Done |
| `/proctor` route | Done |
| `CandidateStackHubPage` intercepts `startTest` when manual proctoring required | Done |
| `applicationHold.js` — `parsePipelineStatusPayload` returns `manualProctoring`, `isManualProctoringRequired` helper | Done |

### Still to test in a real browser

- [ ] Full WebRTC offer/answer handshake (requires two browser tabs — can't be tested with curl)
- [ ] Screen share picker appears correctly on candidate side
- [ ] Proctor's dual video (camera track + screen track) renders without mixing
- [ ] Terminate → hold email arrives at candidate's address

---

## Security audit — 2026-07-08

Full read-only audit of all 6 services followed by systematic fixes. All critical and high severity issues resolved.

### Main backend (8000)

| Fix | Area |
|-----|------|
| Row-level scoping via `get_queryset()` on `ProjectViewSet`, `ContractListView`, `MileStoneViewSet`, `CounterOfferMileStoneViewSet`, `CounterOfferView`, `DisputeViewSet`, `DisputeResponseViewSet` | Data leakage |
| Contract status transition guard (`CONTRACT_STATUS_TRANSITIONS`) | Logic integrity |
| Duplicate dispute prevention + `return_amount` validation | Dispute correctness |
| `CancelDisputeView`: wrong status (`resolved` → `cancelled`), added auth + ownership | Bug + auth |
| DRC cleanup on dispute resolve | Bug |
| Chapa webhook HMAC-SHA256 signature verification | Payment security |
| Escrow ownership check in `InitializeEscrowPaymentView` | Auth |
| `FreelancerInterviewViewSet`: unscoped queryset + update ownership check | Data leakage + auth |
| `UpdateAppointmentStatusView`: scoped to interviewer's assigned freelancers | Auth |
| `SelectAppointmentDateView`: serializer context fix (was silently skipping date validation) | Bug |
| `VerifyFreelancerSkillsView`: scoped to assigned freelancer | Auth |
| `FullAssessmentViewSet`: replaced broken `IsInterviewerOrReadOnly` + added `get_queryset()` | Auth + data leakage |
| `MessageViewSet`, `MarkMessagesAsReadView`, `ChatBetweenClientFreelancerView`, `FreelancerChatListView`, `ClientChatListView`: all scoped to authenticated user | Data leakage |
| `report_stage_result()`: race condition fixed with `select_for_update()` + `transaction.atomic()` | Race condition |
| `Milestone.is_completed` kept in sync with `status` via `save()` override | Data integrity |
| `send_assessment_update_email(self, ...)` spurious `self` removed (would crash callers) | Bug |
| 40+ `print()` statements removed across `user/views.py`, `resume/views.py`, `interview/views.py` | Info disclosure |
| Typos in user-facing strings fixed | Polish |
| `logging` added to all modified view modules | Observability |

### Microservices (8001 / 8002 / 8003 / 8005)

| Fix | Affected services |
|-----|-------------------|
| `IndexError` crash on malformed `Authorization` header in `CustomJWTAuthentication` + `TokenPayloadPermission` — DoS vector | All 4 |
| Raw JWT access token printed to stdout | All 4 |
| `_freelancer_id(request)` helper: always read identity from verified JWT, never from request body | All 4 |
| `SkillTestSubmissionViewSet`: unscoped queryset + `partial_update()` ownership check + `transaction.atomic()` on scoring | 8001 |
| `BulkCreateSkillTestAnswerView`: verify submission belongs to caller | 8001 |
| `SkillTestQuestionViewSet` / `SkillTestOptionViewSet`: converted to `ReadOnlyModelViewSet`; scoped to tests the candidate already submitted (prevents pre-test cheating via `is_correct` field) | 8001 |
| `SkillTestAnswerViewSet`: scoped to caller's own answers | 8001 |
| `TestSubmissionViewSet`: unscoped queryset fixed; `submit_answer` / `finalize_submission` ownership checks | 8002 |
| `FollowUpTestSubmissionViewSet`: unscoped queryset fixed; `submit_followUp_answer` ownership + `freelancer_id` from JWT | 8002 |
| `SkillTestAnswerView`: submission ownership check | 8002 |
| `selected_option_id.lower()` AttributeError on `None` fixed | 8002 |
| `finalize_submission()` wrapped in `transaction.atomic()` | 8002 |
| `FetchAndStoreProfilePictureView`, `VerifySnapshotView`, `UpdateProfilePictureView`: `freelancer_id` from JWT | 8003 |
| All KYC views (`VerifyIDView`, `VerifyPassportView`, `FaceMatchingView`, `SmileDetectionView`, `HeadRotationRightView`, `HeadRotationLeftView`, `UpdateUserImageView`): `freelancer_id` from JWT | 8005 |
| Typo fixes in error messages + 35+ print statements removed | 8005 |

---

## Known risks

1. **String coupling** — legacy `category` / `position` must match `Services.name` where DB taxonomy not used.
2. **Dual state** — `VettingPipelineRecord` vs `CandidateVettingProgress` can disagree if only one is updated.
3. **Email delivery** — Brevo/SMTP in `app/.env`; holds saved even if send fails (use resend endpoint).
4. **Heavy local dev** — five backends + React; document ports in each `CLAUDE.md`.
5. **Root `node_modules` in React App repo** — keep gitignored; dependencies live under `my-react-app/`.
