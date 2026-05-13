"""
StockQuest / Candy Kingdom — Wish & Grow Feature Test Suite (iteration 2)
Tests the new POST /api/wish endpoint, wish_resolver_loop, Socket.IO 'wish_placed'
and 'wish_resolved' events, and extended LimitsReq (wishes_enabled, max_wish_stake).
"""
import asyncio
import os
import time

import pytest
import requests
import socketio

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://grant-demo.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(autouse=True)
def reset_state(client):
    r = client.post(f"{API}/reset", timeout=15)
    assert r.status_code == 200, f"reset failed: {r.status_code} {r.text}"
    yield


# ---------- /api/reset includes new wish fields ----------
class TestResetIncludesWishDefaults:
    def test_reset_has_wishes_list_and_wish_limits(self, client):
        r = client.post(f"{API}/reset", timeout=10)
        assert r.status_code == 200
        d = r.json()
        # wishes list initialized empty
        assert "wishes" in d, "state missing 'wishes' key"
        assert isinstance(d["wishes"], list)
        assert d["wishes"] == []
        # limits include new wish fields with proper defaults
        lim = d["limits"]
        assert lim.get("wishes_enabled") is True
        assert lim.get("max_wish_stake") == 10


# ---------- POST /api/wish — happy path ----------
class TestWishCreation:
    def test_create_wish_deducts_coins_and_adds_active(self, client):
        before = client.get(f"{API}/state").json()
        coins_before = before["coins"]
        wishes_before = len(before["wishes"])

        r = client.post(
            f"{API}/wish",
            json={"ticker": "AAPL", "direction": "grow",
                  "stake": 3, "duration_sec": 30},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "active"
        assert "wish" in body and "state" in body
        wish = body["wish"]
        # wish object shape
        for k in ["id", "ticker", "candy_name", "icon", "direction", "stake",
                  "start_price", "duration_sec", "created_at", "expires_at",
                  "status", "end_price", "payout"]:
            assert k in wish, f"wish missing {k}"
        assert wish["ticker"] == "AAPL"
        assert wish["direction"] == "grow"
        assert wish["stake"] == 3
        assert wish["status"] == "active"
        assert wish["end_price"] is None
        assert wish["payout"] == 0
        assert isinstance(wish["start_price"], (int, float))

        # state side-effects
        st = body["state"]
        assert st["coins"] == coins_before - 3, "stake not deducted"
        assert len(st["wishes"]) == wishes_before + 1
        # newest wish should be first
        assert st["wishes"][0]["id"] == wish["id"]
        # history entry created
        assert st["history"][0]["type"] == "wish"

    def test_wish_direction_shrink_ok(self, client):
        r = client.post(
            f"{API}/wish",
            json={"ticker": "TSLA", "direction": "shrink",
                  "stake": 2, "duration_sec": 10},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json()["wish"]["direction"] == "shrink"


# ---------- POST /api/wish — validation errors ----------
class TestWishValidation:
    def test_invalid_direction_returns_400(self, client):
        r = client.post(
            f"{API}/wish",
            json={"ticker": "AAPL", "direction": "sideways",
                  "stake": 2, "duration_sec": 10},
            timeout=10,
        )
        # Pydantic only validates types; runtime check should give 400
        assert r.status_code == 400, r.text

    def test_unknown_ticker_returns_400(self, client):
        r = client.post(
            f"{API}/wish",
            json={"ticker": "ZZZ", "direction": "grow",
                  "stake": 2, "duration_sec": 10},
            timeout=10,
        )
        assert r.status_code == 400

    def test_stake_above_pydantic_bound_returns_422(self, client):
        # stake > 20 -> Pydantic validation 422
        r = client.post(
            f"{API}/wish",
            json={"ticker": "AAPL", "direction": "grow",
                  "stake": 50, "duration_sec": 10},
            timeout=10,
        )
        assert r.status_code in (400, 422)

    def test_stake_above_parent_max_returns_400(self, client):
        # default max_wish_stake = 10; stake=15 (allowed by Pydantic <=20) but > parent's cap
        r = client.post(
            f"{API}/wish",
            json={"ticker": "AAPL", "direction": "grow",
                  "stake": 15, "duration_sec": 10},
            timeout=10,
        )
        assert r.status_code == 400, r.text
        assert "max" in r.text.lower() or "stake" in r.text.lower()

    def test_insufficient_coins_returns_400(self, client):
        # Lower max_wish_stake unchanged; first drain coins via large redeem? Easier: set limits then push stake near coin balance
        # Set max_wish_stake high enough to bypass parent-cap, then attempt stake > coins
        client.post(
            f"{API}/limits",
            json={"auto_approve_under": 5, "max_per_trade": 25, "max_per_week": 50,
                  "sell_approval": "always", "age_unlock": 13,
                  "wishes_enabled": True, "max_wish_stake": 20},
            timeout=10,
        )
        # Spend most coins via redeem to get coins low? Initial coins=680.
        # Simplest: ensure coins < stake by checking state and choosing stake just above
        st = client.get(f"{API}/state").json()
        # Drain coins to a low number by issuing many auto-approved buys is complex.
        # Instead, monkey-patch via direct DB? Not allowed. Use a different trick:
        # Use a fresh reset then set max_wish_stake=20, but we still have 680 coins.
        # So this specific test is harder without DB access — instead simulate by spending coins via small wishes.
        # Burn through coins with sequential wishes of stake=20 if needed.
        # Actually simpler: test the negative branch by mocking coins. Skip if impractical.
        if st["coins"] >= 20:
            # Burn down: place many wishes (each loses stake immediately upon resolve, or stake locked in active)
            # For determinism, just place a wish that takes 20 coins, then check follow-up wish > remaining
            # We'll place enough active wishes to drain coins below 20.
            remaining = st["coins"]
            while remaining >= 20:
                rr = client.post(
                    f"{API}/wish",
                    json={"ticker": "AAPL", "direction": "grow",
                          "stake": 20, "duration_sec": 120},
                    timeout=10,
                )
                if rr.status_code != 200:
                    break
                remaining = rr.json()["state"]["coins"]
            st = client.get(f"{API}/state").json()
        # Now stake larger than remaining coins should 400
        try_stake = max(1, st["coins"] + 5)
        # cap to Pydantic max 20
        try_stake = min(20, try_stake)
        if try_stake > st["coins"]:
            r = client.post(
                f"{API}/wish",
                json={"ticker": "AAPL", "direction": "grow",
                      "stake": try_stake, "duration_sec": 10},
                timeout=10,
            )
            assert r.status_code == 400
            assert "coin" in r.text.lower() or "enough" in r.text.lower()
        else:
            pytest.skip(f"could not drain coins below 20 (remaining={st['coins']})")

    def test_wishes_disabled_returns_403(self, client):
        # Disable wishes via limits
        r0 = client.post(
            f"{API}/limits",
            json={"auto_approve_under": 5, "max_per_trade": 25, "max_per_week": 50,
                  "sell_approval": "always", "age_unlock": 13,
                  "wishes_enabled": False, "max_wish_stake": 10},
            timeout=10,
        )
        assert r0.status_code == 200
        assert r0.json()["limits"]["wishes_enabled"] is False

        r = client.post(
            f"{API}/wish",
            json={"ticker": "AAPL", "direction": "grow",
                  "stake": 2, "duration_sec": 10},
            timeout=10,
        )
        assert r.status_code == 403, r.text


# ---------- /api/limits — new fields persist ----------
class TestLimitsExtended:
    def test_set_wish_fields_persist(self, client):
        payload = {"auto_approve_under": 5, "max_per_trade": 25, "max_per_week": 50,
                   "sell_approval": "always", "age_unlock": 13,
                   "wishes_enabled": False, "max_wish_stake": 7}
        r = client.post(f"{API}/limits", json=payload, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["limits"]["wishes_enabled"] is False
        assert d["limits"]["max_wish_stake"] == 7
        # verify persistence via GET /state
        r2 = client.get(f"{API}/state", timeout=10).json()
        assert r2["limits"]["wishes_enabled"] is False
        assert r2["limits"]["max_wish_stake"] == 7

    def test_existing_limits_payload_still_works(self, client):
        """Existing iteration_1 payload without wish fields should still succeed
        because both new fields have Pydantic defaults."""
        payload = {"auto_approve_under": 8, "max_per_trade": 30,
                   "max_per_week": 60, "sell_approval": "always", "age_unlock": 14}
        r = client.post(f"{API}/limits", json=payload, timeout=10)
        assert r.status_code == 200, r.text
        lim = r.json()["limits"]
        # defaults applied
        assert lim["wishes_enabled"] is True
        assert lim["max_wish_stake"] == 10


# ---------- wish_resolver_loop — terminal resolution ----------
class TestWishResolver:
    def test_short_wish_resolves_to_won_or_lost(self, client):
        # duration_sec=10 (minimum allowed). Wait ~13s for resolver to run.
        before = client.get(f"{API}/state").json()
        coins_before = before["coins"]
        xp_before = before["xp"]

        r = client.post(
            f"{API}/wish",
            json={"ticker": "AAPL", "direction": "grow",
                  "stake": 2, "duration_sec": 10},
            timeout=10,
        )
        assert r.status_code == 200
        wish_id = r.json()["wish"]["id"]

        # Stake immediately deducted
        st = r.json()["state"]
        assert st["coins"] == coins_before - 2

        # Wait for resolver (loop tick is 1s, starts 3s after startup but well past now)
        deadline = time.time() + 25
        resolved = None
        while time.time() < deadline:
            now_state = client.get(f"{API}/state", timeout=10).json()
            w = next((w for w in now_state["wishes"] if w["id"] == wish_id), None)
            if w and w["status"] in ("won", "lost"):
                resolved = w
                break
            time.sleep(1)
        assert resolved is not None, "wish did not resolve within 25s"
        assert resolved["status"] in ("won", "lost")
        assert resolved["end_price"] is not None
        assert isinstance(resolved["end_price"], (int, float))

        final = client.get(f"{API}/state").json()
        if resolved["status"] == "won":
            # coins: -stake +2*stake = +stake net; xp: +50
            assert final["coins"] == coins_before + 2, f"won payout wrong: {final['coins']} vs {coins_before+2}"
            assert final["xp"] == xp_before + 50
            assert resolved["payout"] == 4
            assert final["history"][0]["type"] == "wish_won"
        else:  # lost
            # coins remain at coins_before - stake; xp: max(0, xp_before-10)
            assert final["coins"] == coins_before - 2
            assert final["xp"] == max(0, xp_before - 10)
            assert resolved["payout"] == 0
            # newest history entry should be wish_lost
            assert final["history"][0]["type"] == "wish_lost"


# ---------- Socket.IO events: wish_placed & wish_resolved ----------
class TestWishSocketEvents:
    def test_wish_placed_and_resolved_events(self):
        async def _t():
            sio = socketio.AsyncClient(reconnection=False)
            events = {"wish_placed": None, "wish_resolved": None}

            @sio.on("wish_placed")
            async def on_placed(data):
                if events["wish_placed"] is None:
                    events["wish_placed"] = data

            @sio.on("wish_resolved")
            async def on_resolved(data):
                if events["wish_resolved"] is None:
                    events["wish_resolved"] = data

            await sio.connect(BASE_URL, socketio_path="/api/socket.io",
                              transports=["websocket"], wait_timeout=15)
            await sio.emit("join_room", {"room_id": "demo_session"})
            await asyncio.sleep(1)

            # Trigger wish
            r = requests.post(
                f"{API}/wish",
                json={"ticker": "AAPL", "direction": "grow",
                      "stake": 2, "duration_sec": 10},
                timeout=10,
            )
            assert r.status_code == 200, r.text

            # Wait for wish_placed quickly
            for _ in range(40):
                if events["wish_placed"]:
                    break
                await asyncio.sleep(0.25)

            # Wait up to ~25s for wish_resolved
            for _ in range(100):
                if events["wish_resolved"]:
                    break
                await asyncio.sleep(0.25)

            await sio.disconnect()

            assert events["wish_placed"] is not None, "no wish_placed event"
            wp = events["wish_placed"]
            # wish_placed is emitted via broadcast_state(...event="wish_placed", extra={...})
            # so the wish metadata lives under '_event_extra' (same pattern as
            # trade_executed/pending_added). The full state is also in the payload.
            assert "_event_extra" in wp, "wish_placed missing _event_extra"
            extra = wp["_event_extra"]
            for k in ["wish_id", "ticker", "direction", "icon"]:
                assert k in extra, f"wish_placed _event_extra missing {k}"
            assert extra["ticker"] == "AAPL"
            assert extra["direction"] == "grow"
            # Also confirm the enriched state is included (coins deducted, wishes list updated)
            assert "wishes" in wp and any(
                w["id"] == extra["wish_id"] for w in wp["wishes"]
            ), "wish not present in broadcast state"

            assert events["wish_resolved"] is not None, "no wish_resolved event"
            wr = events["wish_resolved"]
            for k in ["wish_id", "ticker", "won", "payout",
                      "start_price", "end_price"]:
                assert k in wr, f"wish_resolved missing {k}"
            assert isinstance(wr["won"], bool)
            assert isinstance(wr["payout"], (int, float))
            assert isinstance(wr["start_price"], (int, float))
            assert isinstance(wr["end_price"], (int, float))

        asyncio.run(_t())


# ---------- Regression: existing flows still work ----------
class TestRegressionExistingFlows:
    def test_state_still_enriched_with_wish_fields(self, client):
        r = client.get(f"{API}/state", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "candies" in d and "portfolio_value" in d
        assert "wishes" in d
        assert "wishes_enabled" in d["limits"]
        assert "max_wish_stake" in d["limits"]

    def test_fund_still_works(self, client):
        before = client.get(f"{API}/state").json()
        r = client.post(f"{API}/fund", json={"amount_usd": 5}, timeout=10)
        assert r.status_code == 200
        after = r.json()
        assert after["coins"] == before["coins"] + 500

    def test_buy_request_auto_approve_still_works(self, client):
        r = client.post(f"{API}/buy-request",
                        json={"ticker": "AAPL", "candies": 30}, timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "auto_approved"

    def test_pending_approve_deny_still_work(self, client):
        client.post(f"{API}/fund", json={"amount_usd": 20})
        r = client.post(f"{API}/buy-request",
                        json={"ticker": "GOOGL", "candies": 50}, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        pid = body["pending_id"]
        r2 = client.post(f"{API}/approve/{pid}", timeout=10)
        assert r2.status_code == 200
