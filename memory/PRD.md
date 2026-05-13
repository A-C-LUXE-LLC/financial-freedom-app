# StockQuest / Candy Kingdom — PRD

## Original Problem Statement
Build a demo for a $10,000 grant funding pitch — a kid-friendly stock investing app called "Candy Kingdom" (kid view) backed by a "StockQuest Custodial Platform" parent dashboard. Each candy represents a real stock. Parents approve trades above auto-limit; kids see only coins and XP, never dollars. **Real time trading + options for a 4-year-old.**

## User Personas
- **Lily (Kid, age 4-12)**: Plays Candy Kingdom on phone, taps candies to invest, makes "wishes" to predict price direction, earns XP, redeems real prizes
- **Parent (Robin, 30s-40s)**: Funds wallet, approves trades, sets limits (including options/wish caps), redeems gift card codes, reviews holdings & history
- **Grant Reviewer**: Wants to see <30s wow factor demo with real-time interactivity, dual-persona UX, real fintech-grade UI

## Core Requirements
1. Single-session demo (no auth, MongoDB state under session_id="demo_session")
2. Dual view: Parent Desktop Dashboard + Kid Mobile Candy Kingdom (phone frame)
3. View toggle: Parent | Split | Kid
4. Real-time WebSocket (Socket.IO at /api/socket.io) for price ticks every 2s and event broadcasts
5. AI Investment Story (Claude Sonnet 4.5 via Emergent LLM key) after every kid buy/wish-win
6. AI Quest generator (Claude Sonnet 4.5)
7. Wish & Grow — kid-friendly options trading (GROW/SHRINK predictions, 1-10 coin stakes, 2x payout)
8. Parent control of every aspect: funding, approvals, limits, prizes, wish toggle

## Architecture
- **Backend**: FastAPI + python-socketio (ASGI wrapped), MongoDB (motor), emergentintegrations for Claude. Single `db.demo_state` collection, single doc per session.
- **Frontend**: React 19 + socket.io-client + framer-motion + react-confetti. Components: App.js (shell+toggle), ParentDashboard.jsx (7 tabs), KidView.jsx (5 nav tabs in phone frame), WishScreen.jsx, BuyModal.jsx.
- **Background tasks**: price_ticker_loop (every 2s, ±0.6% jitter with mean-reversion drift), wish_resolver_loop (every 1s, resolves expired wishes).

## Implementation Log
### 2026-01-13 — MVP Complete
- Backend: FastAPI + Socket.IO + Mongo + Emergent LLM (Claude Sonnet 4.5)
- 6 candies = real stocks (AAPL, GOOGL, TSLA, DIS, MCD, NFLX)
- REST: /api/state, /api/fund, /api/buy-request, /api/approve/:id, /api/deny/:id, /api/redeem/:id, /api/quest-complete/:id, /api/limits, /api/reset, /api/ai/story, /api/ai/quests
- Parent Dashboard: Overview, Approvals (with pending badge), Fund (presets + custom), Holdings (live gains), Rewards, Limits, History
- Kid View: Shop, Chest, Prizes, Quests — with confetti, unicorn mascot, animated story panel
- 25/25 backend tests passed (iteration_1.json)

### 2026-01-13 — Wish & Grow (Options for Kids)
- New POST /api/wish endpoint + wish_resolver_loop background task
- Kid picks candy → GROW BIG 🌱 or GET SMALL 🍃 → stake 1-10 candy coins → 30s timer
- WIN: 2x stake + 50 XP + AI unicorn celebration story
- LOSS: -stake coins, -10 XP, gentle "Try again!" message
- Parent Limits tab: `wishes_enabled` toggle + `max_wish_stake` cap (default 10)
- New 🦄 WISH tab in kid bottom nav
- 42/42 backend tests passed (iteration_2.json)

## What's Implemented (Static / Done)
- Dual-persona split-screen demo with view toggle ✅
- Real-time WebSocket sync (price_tick, state_update, trade_executed, pending_added, trade_approved, trade_denied, prize_redeemed, quest_done, wish_placed, wish_resolved) ✅
- 7 parent dashboard tabs, full CRUD on funding/approvals/limits ✅
- 5 kid nav tabs (Shop, Wish, Chest, Prizes, Quests) ✅
- AI Investment Story + AI Quest generator (Claude Sonnet 4.5) ✅
- Confetti + framer-motion animations + unicorn mascot ✅
- Wish & Grow (kid options trading) end-to-end ✅
- Parent controls for wish enable/disable + stake cap ✅

## Prioritized Backlog (P0 / P1 / P2)
- P1: Real stock prices via Finnhub (free 60 req/min, much better than Alpha Vantage's 25/day)
- P1: Multi-user auth (parent account + child profile linking) for production
- P2: Push notifications to parent's phone on approval requests
- P2: Sell flow (currently only buy)
- P2: Multi-child support per parent (siblings)
- P2: Educational micro-lessons unlocked at XP milestones
- P2: Family leaderboard ("Cousin Lily vs Cousin Max")

## Next Tasks
- Get user feedback on the WISH feature UX with a real 4-year-old test
- Add a "Demo Walkthrough Mode" — auto-plays a 60s tour for grant reviewers
- Add screenshot capability so the kid can share wins with grandma
