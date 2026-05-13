"""
StockQuest / Candy Kingdom — Backend Test Suite
Tests REST API + Socket.IO WebSocket lifecycle.
"""
import asyncio
import os
import time

import pytest
import requests
import socketio

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://grant-demo.preview.emergentagent.com").rstrip("/")
# If env not set, fall back to frontend/.env value
if "BACKEND_URL_OVERRIDE" in os.environ:
    BASE_URL = os.environ["BACKEND_URL_OVERRIDE"].rstrip("/")

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


# ---------- /api/state ----------
class TestState:
    def test_state_returns_enriched(self, client):
        r = client.get(f"{API}/state", timeout=10)
        assert r.status_code == 200
        d = r.json()
        for key in ["candies", "portfolio_value", "prices", "coins", "xp",
                    "pending", "holdings", "prizes", "quests", "limits", "history"]:
            assert key in d, f"missing key {key}"
        assert isinstance(d["candies"], list) and len(d["candies"]) == 6
        # candy enrichment check
        c0 = d["candies"][0]
        for k in ["ticker", "price", "coin_price", "change_pct", "icon"]:
            assert k in c0
        assert isinstance(d["portfolio_value"], (int, float))


# ---------- /api/fund ----------
class TestFund:
    def test_fund_increases_coins_and_cash(self, client):
        before = client.get(f"{API}/state").json()
        r = client.post(f"{API}/fund", json={"amount_usd": 10}, timeout=10)
        assert r.status_code == 200
        after = r.json()
        assert after["coins"] == before["coins"] + 1000
        assert round(after["cash_balance"] - before["cash_balance"], 2) == 10.00
        assert after["history"][0]["type"] == "fund"
        assert "+$10.00" in after["history"][0]["amount_str"]

    def test_fund_invalid(self, client):
        r = client.post(f"{API}/fund", json={"amount_usd": 0}, timeout=10)
        assert r.status_code in (400, 422)


# ---------- /api/buy-request ----------
class TestBuy:
    def test_auto_approve_small_buy(self, client):
        before = client.get(f"{API}/state").json()
        coins_before = before["coins"]
        # AAPL coin_price ~12, 30 candies => 360 coins => $3.60 < $5 auto
        r = client.post(f"{API}/buy-request",
                        json={"ticker": "AAPL", "candies": 30}, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "auto_approved"
        st = body["state"]
        assert st["coins"] < coins_before  # deducted
        # XP gained 20
        assert st["xp"] == before["xp"] + 20
        # AAPL shares should increase
        assert st["holdings"]["AAPL"]["shares"] > before["holdings"]["AAPL"]["shares"]
        assert st["history"][0]["type"] == "buy"

    def test_pending_large_buy(self, client):
        # Fund wallet so we have enough coins for a large buy
        client.post(f"{API}/fund", json={"amount_usd": 20})
        before = client.get(f"{API}/state").json()
        coins_before = before["coins"]
        pending_count_before = len(before["pending"])
        # 100 candies of AAPL => ~1200 coins => $12 > $5 -> pending
        r = client.post(f"{API}/buy-request",
                        json={"ticker": "AAPL", "candies": 100}, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "pending"
        assert "pending_id" in body
        st = body["state"]
        # coins should NOT be deducted yet
        assert st["coins"] == coins_before
        assert len(st["pending"]) == pending_count_before + 1

    def test_buy_unknown_ticker(self, client):
        r = client.post(f"{API}/buy-request",
                        json={"ticker": "ZZZ", "candies": 5}, timeout=10)
        assert r.status_code == 400

    def test_buy_insufficient_coins(self, client):
        r = client.post(f"{API}/buy-request",
                        json={"ticker": "NFLX", "candies": 1000}, timeout=10)
        assert r.status_code == 400


# ---------- /api/approve & /api/deny ----------
class TestApproveDeny:
    def test_approve_executes_trade(self, client):
        # Fund first so we can afford a pending GOOGL buy
        client.post(f"{API}/fund", json={"amount_usd": 20})
        # Create a pending trade
        r = client.post(f"{API}/buy-request",
                        json={"ticker": "GOOGL", "candies": 50}, timeout=10)
        body = r.json()
        assert body.get("status") == "pending", f"got {body}"
        tx_id = body["pending_id"]
        before = client.get(f"{API}/state").json()
        coins_before = before["coins"]
        xp_before = before["xp"]
        googl_before = before["holdings"].get("GOOGL", {"shares": 0})["shares"]

        r2 = client.post(f"{API}/approve/{tx_id}", timeout=10)
        assert r2.status_code == 200, r2.text
        after = r2.json()
        assert after["coins"] < coins_before
        assert after["xp"] == xp_before + 20
        assert after["holdings"]["GOOGL"]["shares"] > googl_before
        assert all(p["id"] != tx_id for p in after["pending"])

    def test_approve_invalid_tx(self, client):
        r = client.post(f"{API}/approve/nonexistent-id", timeout=10)
        assert r.status_code == 404

    def test_deny_removes_pending(self, client):
        client.post(f"{API}/fund", json={"amount_usd": 20})
        r = client.post(f"{API}/buy-request",
                        json={"ticker": "TSLA", "candies": 80}, timeout=10)
        body = r.json()
        if body.get("status") != "pending":
            pytest.skip(f"expected pending, got {body}")
        tx_id = body["pending_id"]
        before = client.get(f"{API}/state").json()
        coins_before = before["coins"]

        r2 = client.post(f"{API}/deny/{tx_id}", timeout=10)
        assert r2.status_code == 200
        after = r2.json()
        assert after["coins"] == coins_before
        assert all(p["id"] != tx_id for p in after["pending"])
        assert after["history"][0]["type"] == "deny"

    def test_deny_invalid_tx(self, client):
        r = client.post(f"{API}/deny/nonexistent", timeout=10)
        assert r.status_code == 404


# ---------- /api/redeem ----------
class TestRedeem:
    def test_redeem_success(self, client):
        # initial xp=450, pizza=300 cost
        r = client.post(f"{API}/redeem/pizza", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["xp"] == 150
        assert any(x["id"] == "pizza" for x in d["redeemed"])
        assert d["history"][0]["type"] == "redeem"

    def test_redeem_insufficient_xp(self, client):
        # park costs 2000, initial xp=450
        r = client.post(f"{API}/redeem/park", timeout=10)
        assert r.status_code == 400

    def test_redeem_unknown(self, client):
        r = client.post(f"{API}/redeem/does-not-exist", timeout=10)
        assert r.status_code == 404


# ---------- /api/quest-complete ----------
class TestQuests:
    def test_quest_complete_adds_xp(self, client):
        before = client.get(f"{API}/state").json()
        xp_before = before["xp"]
        # q1 incomplete, xp=200
        r = client.post(f"{API}/quest-complete/q1", timeout=10)
        assert r.status_code == 200
        after = r.json()
        assert after["xp"] == xp_before + 200
        q1 = next(x for x in after["quests"] if x["id"] == "q1")
        assert q1["done"] is True
        assert q1["progress"] == q1["target"]

    def test_quest_unknown(self, client):
        r = client.post(f"{API}/quest-complete/q999", timeout=10)
        assert r.status_code == 404


# ---------- /api/limits ----------
class TestLimits:
    def test_set_limits(self, client):
        payload = {"auto_approve_under": 8, "max_per_trade": 30,
                   "max_per_week": 60, "sell_approval": "always", "age_unlock": 14}
        r = client.post(f"{API}/limits", json=payload, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["limits"]["auto_approve_under"] == 8
        assert d["limits"]["max_per_trade"] == 30
        assert d["limits"]["age_unlock"] == 14


# ---------- /api/reset ----------
class TestReset:
    def test_reset_restores_initial(self, client):
        # mutate
        client.post(f"{API}/fund", json={"amount_usd": 50})
        r = client.post(f"{API}/reset", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["cash_balance"] == 1.24
        assert d["coins"] == 680
        assert d["xp"] == 450
        assert len(d["pending"]) == 2


# ---------- /api/ai/story ----------
class TestAIStory:
    def test_story_response_shape(self, client):
        r = client.post(f"{API}/ai/story",
                        json={"ticker": "AAPL", "change_pct": 1.5}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ["story", "ticker", "candy_name", "icon"]:
            assert k in d
        assert isinstance(d["story"], str) and len(d["story"]) > 0
        assert d["ticker"] == "AAPL"

    def test_story_unknown_ticker(self, client):
        r = client.post(f"{API}/ai/story",
                        json={"ticker": "ZZZ", "change_pct": 1}, timeout=15)
        assert r.status_code == 400


# ---------- /api/ai/quests ----------
class TestAIQuests:
    def test_ai_quests_returns_5(self, client):
        r = client.post(f"{API}/ai/quests", timeout=45)
        assert r.status_code == 200
        d = r.json()
        assert "quests" in d
        assert isinstance(d["quests"], list)
        assert len(d["quests"]) == 5
        for q in d["quests"]:
            for k in ["id", "title", "desc", "xp", "target", "icon"]:
                assert k in q


# ---------- WebSocket / Socket.IO ----------
class TestWebSocket:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro) \
            if False else asyncio.run(coro)

    def test_connect_join_room_state_update(self):
        async def _t():
            sio = socketio.AsyncClient(reconnection=False)
            received = {"state": None, "connected": False}

            @sio.event
            async def connect():
                received["connected"] = True

            @sio.on("state_update")
            async def on_state(data):
                if received["state"] is None:
                    received["state"] = data

            await sio.connect(BASE_URL, socketio_path="/api/socket.io",
                              transports=["websocket"], wait_timeout=15)
            await sio.emit("join_room", {"room_id": "demo_session"})
            # wait for state_update
            for _ in range(30):
                if received["state"] is not None:
                    break
                await asyncio.sleep(0.2)
            await sio.disconnect()
            assert received["connected"], "did not connect"
            assert received["state"] is not None, "no state_update after join"
            assert "candies" in received["state"]
            assert "coins" in received["state"]
        asyncio.run(_t())

    def test_price_tick_received(self):
        async def _t():
            sio = socketio.AsyncClient(reconnection=False)
            ticks = []

            @sio.on("price_tick")
            async def on_tick(data):
                ticks.append(data)

            await sio.connect(BASE_URL, socketio_path="/api/socket.io",
                              transports=["websocket"], wait_timeout=15)
            await sio.emit("join_room", {"room_id": "demo_session"})
            # price ticker fires every ~2s; wait up to 6s
            for _ in range(30):
                if ticks:
                    break
                await asyncio.sleep(0.25)
            await sio.disconnect()
            assert len(ticks) >= 1, "no price_tick received"
            t0 = ticks[0]
            assert "prices" in t0 and "candies" in t0
        asyncio.run(_t())

    def test_trade_executed_and_pending_events(self):
        async def _t():
            sio = socketio.AsyncClient(reconnection=False)
            events = {"trade_executed": None, "pending_added": None,
                      "trade_approved": None}

            @sio.on("trade_executed")
            async def on_te(data):
                events["trade_executed"] = data

            @sio.on("pending_added")
            async def on_pa(data):
                events["pending_added"] = data

            @sio.on("trade_approved")
            async def on_ta(data):
                events["trade_approved"] = data

            await sio.connect(BASE_URL, socketio_path="/api/socket.io",
                              transports=["websocket"], wait_timeout=15)
            await sio.emit("join_room", {"room_id": "demo_session"})
            await asyncio.sleep(1)

            # Trigger auto-approve trade via REST
            requests.post(f"{API}/buy-request",
                          json={"ticker": "AAPL", "candies": 30}, timeout=10)
            for _ in range(20):
                if events["trade_executed"]:
                    break
                await asyncio.sleep(0.25)

            # Trigger pending - fund first so coins are sufficient
            requests.post(f"{API}/fund", json={"amount_usd": 20}, timeout=10)
            await asyncio.sleep(0.5)
            r = requests.post(f"{API}/buy-request",
                              json={"ticker": "AAPL", "candies": 100}, timeout=10)
            pending_id = r.json().get("pending_id")
            for _ in range(20):
                if events["pending_added"]:
                    break
                await asyncio.sleep(0.25)

            # Approve
            if pending_id:
                requests.post(f"{API}/approve/{pending_id}", timeout=10)
                for _ in range(20):
                    if events["trade_approved"]:
                        break
                    await asyncio.sleep(0.25)

            await sio.disconnect()
            assert events["trade_executed"] is not None, "no trade_executed"
            assert events["pending_added"] is not None, "no pending_added"
            assert events["trade_approved"] is not None, "no trade_approved"
        asyncio.run(_t())

    def test_two_clients_same_room(self):
        async def _t():
            c1 = socketio.AsyncClient(reconnection=False)
            c2 = socketio.AsyncClient(reconnection=False)
            c1_state = []
            c2_state = []

            @c1.on("state_update")
            async def s1(data):
                c1_state.append(data)

            @c2.on("state_update")
            async def s2(data):
                c2_state.append(data)

            await c1.connect(BASE_URL, socketio_path="/api/socket.io",
                             transports=["websocket"], wait_timeout=15)
            await c2.connect(BASE_URL, socketio_path="/api/socket.io",
                             transports=["websocket"], wait_timeout=15)
            await c1.emit("join_room", {"room_id": "demo_session"})
            await c2.emit("join_room", {"room_id": "demo_session"})
            await asyncio.sleep(1.5)
            c1_count_before = len(c1_state)
            c2_count_before = len(c2_state)

            # Trigger broadcast (fund)
            requests.post(f"{API}/fund", json={"amount_usd": 5}, timeout=10)
            for _ in range(20):
                if len(c1_state) > c1_count_before and len(c2_state) > c2_count_before:
                    break
                await asyncio.sleep(0.25)

            await c1.disconnect()
            await c2.disconnect()
            assert len(c1_state) > c1_count_before, "client1 did not get broadcast"
            assert len(c2_state) > c2_count_before, "client2 did not get broadcast"
        asyncio.run(_t())
