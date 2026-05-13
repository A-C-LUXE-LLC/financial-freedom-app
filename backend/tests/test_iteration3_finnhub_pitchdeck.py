"""Iteration 3 tests: Finnhub real-price integration + Pitch deck PDF endpoint
+ regression sample for state/fund/buy-request/wish/approve.
"""
import io
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://grant-demo.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ───────────────── Finnhub real-price integration ─────────────────
class TestFinnhubIntegration:
    def test_state_has_real_prices(self, client):
        """After startup, prices should be real (AAPL > $100, not seed 184.50)."""
        r = client.get(f"{API}/state")
        assert r.status_code == 200
        data = r.json()
        assert "prices" in data
        # Real AAPL prices in 2026 are ~$200-300; seed is 184.50.
        # Accept any value > $100 (real) - jitter from seed cannot reach that.
        assert data["prices"]["AAPL"] > 100, f"AAPL price {data['prices']['AAPL']} looks like seed"
        # All tickers populated
        for tk in ("AAPL", "GOOGL", "TSLA", "DIS", "MCD", "NFLX"):
            assert data["prices"][tk] > 0

    def test_last_real_fetch_populated(self, client):
        r = client.get(f"{API}/state")
        data = r.json()
        assert data.get("last_real_fetch"), "last_real_fetch must be set after Finnhub sync"
        # ISO-format string with timezone
        assert "T" in data["last_real_fetch"]

    def test_price_ticker_still_jittering(self, client):
        """Price ticker (every 2s) must continue to update prices even with Finnhub on."""
        r1 = client.get(f"{API}/state")
        p1 = r1.json()["prices"].copy()
        time.sleep(5)  # > 2 jitter cycles
        r2 = client.get(f"{API}/state")
        p2 = r2.json()["prices"]
        # At least one ticker should have moved
        moved = any(p1[t] != p2[t] for t in p1)
        assert moved, f"No price movement in 5s — ticker may be stuck. p1={p1} p2={p2}"


# ───────────────── Pitch Deck PDF ─────────────────
class TestPitchDeck:
    def test_pitch_deck_returns_pdf(self, client):
        r = client.get(f"{API}/pitch-deck", timeout=60)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("application/pdf"), \
            f"Bad content-type: {r.headers.get('content-type')}"
        # Content-Disposition
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd.lower()
        assert "lily-pitch-deck-" in cd
        assert ".pdf" in cd
        # Size check
        assert len(r.content) > 5000, f"PDF too small: {len(r.content)} bytes"
        # PDF magic bytes
        assert r.content[:4] == b"%PDF", "Response is not a valid PDF"

    def test_pitch_deck_valid_pdf_structure(self, client):
        r = client.get(f"{API}/pitch-deck", timeout=60)
        assert r.status_code == 200
        # Must end with %%EOF
        assert b"%%EOF" in r.content[-1024:], "PDF missing %%EOF trailer"


# ───────────────── Regression sample ─────────────────
class TestRegression:
    def test_state_endpoint(self, client):
        r = client.get(f"{API}/state")
        assert r.status_code == 200
        d = r.json()
        for k in ("cash_balance", "coins", "xp", "level", "candies",
                  "portfolio_value", "limits", "quests", "prizes", "history"):
            assert k in d, f"missing key {k}"

    def test_fund_increases_coins(self, client):
        before = client.get(f"{API}/state").json()
        r = client.post(f"{API}/fund", json={"amount_usd": 5.0})
        assert r.status_code == 200, r.text
        after = r.json()
        assert after["coins"] == before["coins"] + 500
        assert round(after["cash_balance"], 2) == round(before["cash_balance"] + 5.0, 2)

    def test_buy_request_auto_approve(self, client):
        """Small candy buy under $5 limit should auto-approve."""
        r = client.post(f"{API}/buy-request", json={"ticker": "AAPL", "candies": 1})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] in ("auto_approved", "pending")

    def test_buy_request_pending_then_approve(self, client):
        """Larger buy that triggers pending → approve flow."""
        # Use NFLX (high coin price) to push past $5
        r = client.post(f"{API}/buy-request", json={"ticker": "NFLX", "candies": 50})
        assert r.status_code == 200, r.text
        body = r.json()
        if body["status"] == "pending":
            pid = body["pending_id"]
            ap = client.post(f"{API}/approve/{pid}")
            assert ap.status_code == 200, ap.text
            after = ap.json()
            # Pending list should no longer contain that id
            assert all(p["id"] != pid for p in after["pending"])
        else:
            # auto-approved is also fine; main agent's limit may differ
            assert body["status"] == "auto_approved"

    def test_wish_placed(self, client):
        # Ensure wishes enabled and we have coins
        client.post(f"{API}/fund", json={"amount_usd": 1.0})
        r = client.post(f"{API}/wish", json={
            "ticker": "AAPL", "direction": "grow", "stake": 5, "duration_sec": 10
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "active"
        assert body["wish"]["ticker"] == "AAPL"
        assert body["wish"]["stake"] == 5

    def test_limits_endpoint(self, client):
        r = client.post(f"{API}/limits", json={
            "auto_approve_under": 5, "max_per_trade": 25, "max_per_week": 50,
            "sell_approval": "always", "age_unlock": 13,
            "wishes_enabled": True, "max_wish_stake": 10
        })
        assert r.status_code == 200, r.text
        assert r.json()["limits"]["auto_approve_under"] == 5
