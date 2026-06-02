# Stable Release Checkpoint — 2026-06-01

This checkpoint preserves the current StockQuest / Candy Kingdom demo before any additional feature work. It records the app baseline, completed improvements, verification history, and restoration steps so the build can be recovered quickly if later changes regress the demo.

## Checkpoint identity

- **Checkpoint date:** 2026-06-01
- **Branch:** `work`
- **Restorable app baseline commit:** `94e1ff4` (`auto-commit for 51d4db9b-07c9-4f79-8f14-7e75a9ada0bc`)
- **Release documentation commit:** the commit containing this checkpoint document (`git rev-parse HEAD` after checkout)
- **Product:** StockQuest custodial parent dashboard + Candy Kingdom kid investing demo
- **Demo session model:** single shared MongoDB document under `session_id="demo_session"`

## Completed improvements included in the checkpoint

### Iteration 1 — MVP demo

- FastAPI backend with Socket.IO realtime sync, MongoDB state persistence, and Emergent LLM integration.
- Six kid-friendly candy investments mapped to real stock tickers: AAPL, GOOGL, TSLA, DIS, MCD, and NFLX.
- Parent dashboard workflow for wallet funding, approvals, denials, reward redemption, limits, holdings, and activity history.
- Kid Candy Kingdom workflow for shopping, chest/holdings, prizes, quests, confetti, animated feedback, and AI investment stories.
- REST API coverage for state, funding, buy requests, approval/denial, reward redemption, quest completion, limit updates, reset, AI stories, and AI quests.
- Backend regression result recorded as **25/25 tests passed** in `test_reports/iteration_1.json`.

### Iteration 2 — Wish & Grow

- Kid-friendly options-style prediction flow where children place GROW or SHRINK wishes using candy coins.
- Timed wish resolver background loop with win/loss outcomes, XP updates, coin payouts, and gentle feedback.
- Parent controls for enabling/disabling wishes and capping the maximum wish stake.
- Kid navigation expanded with a Wish tab and mobile-first Wish & Grow experience.
- Socket.IO events added for wish placement and wish resolution.
- Backend regression result recorded as **42/42 tests passed** in `test_reports/iteration_2.json`.

### Iteration 3 — Live pricing, walkthrough, pitch deck, and audio polish

- Finnhub live-price integration for the six demo tickers, with demo-safe fallback behavior.
- Demo walkthrough mode with Play Demo button, staged narration/captions, progress display, and automated dual-persona interactions.
- Downloadable one-page pitch deck PDF endpoint with portfolio stats, AI-narrated story, holdings visualization, and recent activity.
- Web Audio sound effects for wins and wish interactions, plus a mute toggle.
- Copy and tap-target polish for a 4-year-old-friendly demo experience.
- Backend regression result recorded as **11/11 new tests passed** in `test_reports/iteration_3.json`.

## Current functional scope

- Dual view shell: Parent, Split, and Kid modes.
- Realtime WebSocket broadcasts for price ticks, state updates, trades, approvals, denials, prize redemption, quest completion, wish placement, and wish resolution.
- Parent dashboard tabs for overview, approvals, funding, holdings, rewards, limits, and history.
- Kid mobile frame with shop, Wish & Grow, chest, prizes, and quests.
- AI story and quest generation with fallback behavior when model access is unavailable.
- Confetti, animated kid feedback, unicorn mascot, pitch deck PDF generation, and sound effects.

## Verification snapshot

Historical verification artifacts already present in the repository:

| Area | Result | Artifact |
| --- | --- | --- |
| MVP backend/API/WebSocket regression | 25/25 passed | `test_reports/iteration_1.json` |
| Wish & Grow backend regression | 42/42 passed | `test_reports/iteration_2.json` |
| Live pricing + pitch deck regression | 11/11 passed | `test_reports/iteration_3.json` |
| Pytest XML outputs | Recorded | `test_reports/pytest/` |

Current environment note: the active container does not have Python test dependencies or frontend node modules installed by default. Restore/install dependencies before rerunning verification commands.

## Recommended verification commands after dependency restore

From the repository root:

```bash
python -m pip install -r backend/requirements.txt
pytest backend/tests -q
cd frontend && yarn install && yarn build
```

If using local services instead of the hosted demo environment, ensure these environment variables are configured before starting the backend:

```bash
export MONGO_URL='<mongodb connection string>'
export DB_NAME='<database name>'
export EMERGENT_LLM_KEY='<optional Emergent LLM key>'
export FINNHUB_API_KEY='<optional Finnhub key>'
```

## Restoration procedure

Use this process to restore the checkpoint if later work introduces regressions:

1. Save or discard any uncommitted work from the later branch.
2. Fetch the repository state that contains the checkpoint baseline.
3. Create a recovery branch from the restorable baseline commit:

   ```bash
   git fetch --all
   git checkout -b restore/stable-2026-06-01 94e1ff4
   ```

4. Reinstall backend and frontend dependencies if the environment is fresh:

   ```bash
   python -m pip install -r backend/requirements.txt
   cd frontend && yarn install
   ```

5. Reconfigure the runtime environment (`MONGO_URL`, `DB_NAME`, optional `EMERGENT_LLM_KEY`, optional `FINNHUB_API_KEY`).
6. Run the backend tests and frontend production build.
7. If the checkpoint must replace a broken branch, merge or cherry-pick from `restore/stable-2026-06-01` after confirming tests/build.

## Known checkpoint caveats

- The app is a single-session demo and intentionally does not include production authentication.
- Backend state is stored as one MongoDB document, so concurrent production-scale writes are outside the checkpoint scope.
- Finnhub and Emergent LLM integrations are external-service dependent; fallback behavior exists for demo resilience.
- The frontend dependency tree is not vendored in the repository, so dependency installation is required in a fresh environment.

## Safe next-step guidance

Before starting new feature work, branch from this checkpoint or create a tag such as:

```bash
git tag stable-2026-06-01 94e1ff4
```

Then make incremental changes on a new branch and rerun the verification commands above before merging.
