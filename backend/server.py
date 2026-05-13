"""
StockQuest / Candy Kingdom — Backend
FastAPI + python-socketio + MongoDB + Emergent LLM (Claude Sonnet 4.5)
"""
import asyncio
import logging
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import socketio
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ["DB_NAME"]]
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

SESSION_ID = "demo_session"

CANDIES = [
    {"ticker": "AAPL", "company": "Apple Inc.", "candy_name": "Lolly Pop Co.", "icon": "🍭",
     "gradient": "linear-gradient(145deg,#9D174D,#BE185D,#EC4899)", "base_price": 184.50, "divisor": 15},
    {"ticker": "GOOGL", "company": "Alphabet Inc.", "candy_name": "Rainbow Drops", "icon": "🌈",
     "gradient": "linear-gradient(145deg,#2E1065,#6D28D9,#8B5CF6)", "base_price": 175.20, "divisor": 10},
    {"ticker": "TSLA", "company": "Tesla Inc.", "candy_name": "Gummy Bears", "icon": "🐻",
     "gradient": "linear-gradient(145deg,#052E16,#047857,#10B981)", "base_price": 245.00, "divisor": 16},
    {"ticker": "DIS", "company": "Walt Disney Co.", "candy_name": "Ice Cream Castle", "icon": "🍦",
     "gradient": "linear-gradient(145deg,#082F49,#0369A1,#0EA5E9)", "base_price": 112.40, "divisor": 11},
    {"ticker": "MCD", "company": "McDonald's Corp.", "candy_name": "Choco Mountain", "icon": "🍫",
     "gradient": "linear-gradient(145deg,#451A03,#92400E,#B45309)", "base_price": 290.00, "divisor": 36},
    {"ticker": "NFLX", "company": "Netflix Inc.", "candy_name": "Birthday Cakes", "icon": "🎂",
     "gradient": "linear-gradient(145deg,#450A0A,#B91C1C,#EF4444)", "base_price": 620.00, "divisor": 28},
]
CANDY_BY_TICKER = {c["ticker"]: c for c in CANDIES}

DEFAULT_PRIZES = [
    {"id": "roblox-10", "icon": "🎮", "name": "$10 Roblox Card", "cost": 500, "type": "Gift Card"},
    {"id": "pizza", "icon": "🍕", "name": "Pizza Night!", "cost": 300, "type": "Experience"},
    {"id": "amazon-5", "icon": "📦", "name": "$5 Amazon Card", "cost": 400, "type": "Gift Card"},
    {"id": "toy", "icon": "🧸", "name": "Toy of Choice", "cost": 800, "type": "Prize"},
    {"id": "cash", "icon": "💵", "name": "Cash to Wallet", "cost": 1000, "type": "Cash Back"},
    {"id": "park", "icon": "🎪", "name": "Theme Park Day!", "cost": 2000, "type": "Big Prize"},
]

DEFAULT_QUESTS = [
    {"id": "q1", "title": "Rainbow Collector", "desc": "Buy 3 different candies", "xp": 200, "progress": 1, "target": 3, "done": False, "icon": "🌈"},
    {"id": "q2", "title": "Sugar Saver", "desc": "Save 100 candy coins", "xp": 100, "progress": 60, "target": 100, "done": False, "icon": "💰"},
    {"id": "q3", "title": "First Sweet Step", "desc": "Make your first investment", "xp": 50, "progress": 1, "target": 1, "done": True, "icon": "🍬"},
    {"id": "q4", "title": "Chest Champion", "desc": "Reach 10 candies in your chest", "xp": 300, "progress": 4, "target": 10, "done": False, "icon": "💎"},
    {"id": "q5", "title": "Quest Master", "desc": "Complete 3 quests", "xp": 500, "progress": 1, "target": 3, "done": False, "icon": "⭐"},
]


def _initial_state() -> dict[str, Any]:
    prices = {c["ticker"]: round(c["base_price"], 2) for c in CANDIES}
    return {
        "session_id": SESSION_ID,
        "cash_balance": 1.24,
        "coins": 680,
        "xp": 450,
        "level": 3,
        "rank": "Sugar Star",
        "prices": prices,
        "prev_prices": prices.copy(),
        "holdings": {
            "AAPL": {"shares": 0.45, "avg_cost": 185.20},
            "GOOGL": {"shares": 1.2, "avg_cost": 168.40},
            "DIS": {"shares": 0.98, "avg_cost": 108.90},
        },
        "pending": [
            {"id": str(uuid.uuid4()), "ticker": "AAPL", "candy_name": "Lolly Pop Co.", "icon": "🍭",
             "candies": 80, "coin_cost": 960, "usd_cost": 9.48,
             "created_at": datetime.now(timezone.utc).isoformat()},
            {"id": str(uuid.uuid4()), "ticker": "GOOGL", "candy_name": "Rainbow Drops", "icon": "🌈",
             "candies": 100, "coin_cost": 1800, "usd_cost": 17.58,
             "created_at": datetime.now(timezone.utc).isoformat()},
        ],
        "history": [
            {"id": str(uuid.uuid4()), "type": "fund", "icon": "💰",
             "title": "Allowance — $10.00 added", "detail": "Parent funded wallet",
             "amount_str": "+$10.00", "color": "green",
             "timestamp": datetime.now(timezone.utc).isoformat()},
        ],
        "limits": {"auto_approve_under": 5, "max_per_trade": 25, "max_per_week": 50,
                   "sell_approval": "always", "age_unlock": 13,
                   "wishes_enabled": True, "max_wish_stake": 10},
        "quests": [q.copy() for q in DEFAULT_QUESTS],
        "prizes": [p.copy() for p in DEFAULT_PRIZES],
        "redeemed": [],
        "wishes": [],   # active + recently-resolved Wish & Grow trades
    }


def candy_price_in_coins(ticker: str, real_price: float) -> int:
    divisor = CANDY_BY_TICKER[ticker]["divisor"]
    return max(1, round(real_price / divisor))


async def get_state() -> dict[str, Any]:
    doc = await db.demo_state.find_one({"session_id": SESSION_ID}, {"_id": 0})
    if not doc:
        doc = _initial_state()
        await db.demo_state.insert_one(doc.copy())
        doc.pop("_id", None)
    return doc


async def save_state(state: dict[str, Any]) -> None:
    state.pop("_id", None)
    await db.demo_state.update_one(
        {"session_id": SESSION_ID}, {"$set": state}, upsert=True
    )


def _portfolio_value(state: dict[str, Any]) -> float:
    total = 0.0
    for tk, h in state["holdings"].items():
        total += h["shares"] * state["prices"].get(tk, h["avg_cost"])
    return round(total, 2)


def _enrich(state: dict[str, Any]) -> dict[str, Any]:
    candies_view = []
    for c in CANDIES:
        price = state["prices"][c["ticker"]]
        prev = state["prev_prices"].get(c["ticker"], price)
        change_pct = ((price - prev) / prev * 100) if prev else 0.0
        coin_price = candy_price_in_coins(c["ticker"], price)
        candies_view.append({**c, "price": price, "prev_price": prev,
                             "change_pct": round(change_pct, 2),
                             "coin_price": coin_price})
    state_out = state.copy()
    state_out["candies"] = candies_view
    state_out["portfolio_value"] = _portfolio_value(state)
    return state_out


# Socket.IO
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
fastapi_app = FastAPI()

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("stockquest")


@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")


@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")


@sio.event
async def join_room(sid, data):
    room_id = (data or {}).get("room_id") or SESSION_ID
    await sio.enter_room(sid, room_id)
    logger.info(f"Client {sid} joined room {room_id}")
    state = await get_state()
    await sio.emit("state_update", _enrich(state), room=sid)


async def broadcast_state(state: dict[str, Any], event: str = "state_update",
                          extra: Optional[dict] = None):
    payload = _enrich(state)
    if extra:
        payload["_event_extra"] = extra
    await sio.emit(event, payload, room=SESSION_ID)


async def price_ticker_loop():
    await asyncio.sleep(2)
    while True:
        try:
            state = await get_state()
            state["prev_prices"] = state["prices"].copy()
            new_prices = {}
            for c in CANDIES:
                cur = state["prices"][c["ticker"]]
                base = c["base_price"]
                drift = (base - cur) * 0.002
                jitter = cur * random.uniform(-0.006, 0.006)
                new = max(0.01, cur + drift + jitter)
                new_prices[c["ticker"]] = round(new, 2)
            state["prices"] = new_prices
            await save_state(state)
            await sio.emit("price_tick",
                           {"prices": new_prices,
                            "prev_prices": state["prev_prices"],
                            "candies": _enrich(state)["candies"]},
                           room=SESSION_ID)
        except Exception as e:
            logger.exception(f"price ticker error: {e}")
        await asyncio.sleep(2)


@fastapi_app.on_event("startup")
async def on_startup():
    await get_state()
    asyncio.create_task(price_ticker_loop())
    asyncio.create_task(wish_resolver_loop())
    asyncio.create_task(finnhub_fetch_loop())
    logger.info("StockQuest backend started")


async def finnhub_fetch_loop():
    """Every 60 seconds, refresh base prices from Finnhub (real stock prices)."""
    import httpx
    if not FINNHUB_API_KEY:
        logger.warning("FINNHUB_API_KEY missing — skipping real price fetch")
        return
    await asyncio.sleep(5)  # let app fully start
    while True:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                state = await get_state()
                fetched = {}
                for c in CANDIES:
                    try:
                        r = await client.get(
                            "https://finnhub.io/api/v1/quote",
                            params={"symbol": c["ticker"], "token": FINNHUB_API_KEY},
                        )
                        if r.status_code == 200:
                            data = r.json()
                            cur = data.get("c")  # current price
                            if cur and cur > 0:
                                fetched[c["ticker"]] = round(float(cur), 2)
                                # also update base_price so jitter mean-reverts to real
                                c["base_price"] = float(cur)
                    except Exception as e:
                        logger.warning(f"Finnhub fetch {c['ticker']}: {e}")
                if fetched:
                    state["prev_prices"] = state["prices"].copy()
                    state["prices"].update(fetched)
                    state["last_real_fetch"] = datetime.now(timezone.utc).isoformat()
                    await save_state(state)
                    await broadcast_state(state, event="real_prices_synced",
                                          extra={"toast": f"📡 Live prices synced ({len(fetched)} stocks)"})
                    logger.info(f"Finnhub sync: {fetched}")
        except Exception as e:
            logger.exception(f"finnhub fetch loop: {e}")
        await asyncio.sleep(60)


api = APIRouter(prefix="/api")


class FundReq(BaseModel):
    amount_usd: float = Field(gt=0, le=10000)


class BuyReq(BaseModel):
    ticker: str
    candies: int = Field(gt=0, le=1000)


class LimitsReq(BaseModel):
    auto_approve_under: float
    max_per_trade: float
    max_per_week: float
    sell_approval: str
    age_unlock: int
    wishes_enabled: bool = True
    max_wish_stake: int = 10


class WishReq(BaseModel):
    ticker: str
    direction: str  # "grow" (up) or "shrink" (down)
    stake: int = Field(gt=0, le=20)
    duration_sec: int = Field(default=30, ge=10, le=120)


class AIStoryReq(BaseModel):
    ticker: str
    change_pct: float


@api.get("/")
async def root():
    return {"app": "StockQuest / Candy Kingdom", "status": "ok"}


@api.get("/state")
async def state_endpoint():
    state = await get_state()
    return _enrich(state)


@api.post("/reset")
async def reset():
    fresh = _initial_state()
    await save_state(fresh)
    await broadcast_state(fresh, extra={"toast": "Demo reset!"})
    return _enrich(fresh)


@api.post("/fund")
async def fund(req: FundReq):
    state = await get_state()
    state["cash_balance"] = round(state["cash_balance"] + req.amount_usd, 2)
    state["coins"] += int(req.amount_usd * 100)
    state["history"].insert(0, {
        "id": str(uuid.uuid4()), "type": "fund", "icon": "💰",
        "title": f"Allowance — ${req.amount_usd:.2f} added",
        "detail": "Parent funded wallet",
        "amount_str": f"+${req.amount_usd:.2f}", "color": "green",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await save_state(state)
    await broadcast_state(state, extra={"toast": f"🍬 +{int(req.amount_usd*100)} candy coins!"})
    return _enrich(state)


def _execute_buy(state, ticker, candies, total_coins, usd_cost, auto=False):
    candy = CANDY_BY_TICKER[ticker]
    real_price = state["prices"][ticker]
    shares_bought = round(usd_cost / real_price, 4)
    state["coins"] -= total_coins
    h = state["holdings"].get(ticker, {"shares": 0, "avg_cost": real_price})
    total_shares = h["shares"] + shares_bought
    new_avg = ((h["shares"] * h["avg_cost"]) + (shares_bought * real_price)) / total_shares if total_shares else real_price
    state["holdings"][ticker] = {"shares": round(total_shares, 4),
                                 "avg_cost": round(new_avg, 2)}
    state["xp"] += 20
    state["history"].insert(0, {
        "id": str(uuid.uuid4()), "type": "buy", "icon": candy["icon"],
        "title": f"Bought {ticker} · {shares_bought} shares",
        "detail": ("Auto-approved (under limit)" if auto else "Parent approved"),
        "amount_str": f"-${usd_cost:.2f}", "color": "red",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@api.post("/buy-request")
async def buy_request(req: BuyReq):
    if req.ticker not in CANDY_BY_TICKER:
        raise HTTPException(400, "Unknown ticker")
    state = await get_state()
    candy = CANDY_BY_TICKER[req.ticker]
    real_price = state["prices"][req.ticker]
    coin_price = candy_price_in_coins(req.ticker, real_price)
    total_coins = coin_price * req.candies
    if state["coins"] < total_coins:
        raise HTTPException(400, "Not enough candy coins")
    usd_cost = round(total_coins / 100, 2)

    if usd_cost <= state["limits"]["auto_approve_under"]:
        _execute_buy(state, req.ticker, req.candies, total_coins, usd_cost, auto=True)
        await save_state(state)
        await broadcast_state(state, event="trade_executed",
                              extra={"ticker": req.ticker, "candies": req.candies,
                                     "icon": candy["icon"], "auto": True,
                                     "xp_gained": 20})
        return {"status": "auto_approved", "state": _enrich(state)}
    else:
        pending = {
            "id": str(uuid.uuid4()), "ticker": req.ticker,
            "candy_name": candy["candy_name"], "icon": candy["icon"],
            "candies": req.candies, "coin_cost": total_coins,
            "usd_cost": usd_cost,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        state["pending"].append(pending)
        await save_state(state)
        await broadcast_state(state, event="pending_added",
                              extra={"pending_id": pending["id"],
                                     "ticker": req.ticker, "icon": candy["icon"]})
        return {"status": "pending", "pending_id": pending["id"],
                "state": _enrich(state)}


@api.post("/approve/{tx_id}")
async def approve(tx_id: str):
    state = await get_state()
    tx = next((p for p in state["pending"] if p["id"] == tx_id), None)
    if not tx:
        raise HTTPException(404, "Pending not found")
    if state["coins"] < tx["coin_cost"]:
        raise HTTPException(400, "Insufficient coins")
    _execute_buy(state, tx["ticker"], tx["candies"], tx["coin_cost"], tx["usd_cost"], auto=False)
    state["pending"] = [p for p in state["pending"] if p["id"] != tx_id]
    await save_state(state)
    await broadcast_state(state, event="trade_approved",
                          extra={"ticker": tx["ticker"], "icon": tx["icon"],
                                 "candies": tx["candies"], "xp_gained": 20})
    return _enrich(state)


@api.post("/deny/{tx_id}")
async def deny(tx_id: str):
    state = await get_state()
    tx = next((p for p in state["pending"] if p["id"] == tx_id), None)
    if not tx:
        raise HTTPException(404, "Pending not found")
    state["pending"] = [p for p in state["pending"] if p["id"] != tx_id]
    state["history"].insert(0, {
        "id": str(uuid.uuid4()), "type": "deny", "icon": "✗",
        "title": f"Denied: {tx['icon']} {tx['ticker']}",
        "detail": "Parent declined request",
        "amount_str": "—", "color": "muted",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await save_state(state)
    await broadcast_state(state, event="trade_denied",
                          extra={"ticker": tx["ticker"], "icon": tx["icon"]})
    return _enrich(state)


@api.post("/redeem/{prize_id}")
async def redeem(prize_id: str):
    state = await get_state()
    prize = next((p for p in state["prizes"] if p["id"] == prize_id), None)
    if not prize:
        raise HTTPException(404, "Unknown prize")
    if state["xp"] < prize["cost"]:
        raise HTTPException(400, "Not enough XP stars")
    state["xp"] -= prize["cost"]
    state["redeemed"].insert(0, {**prize, "at": datetime.now(timezone.utc).isoformat()})
    state["history"].insert(0, {
        "id": str(uuid.uuid4()), "type": "redeem", "icon": prize["icon"],
        "title": f"Reward redeemed: {prize['name']}",
        "detail": f"{prize['cost']} XP spent · Parent notified",
        "amount_str": f"-{prize['cost']} XP", "color": "gold",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await save_state(state)
    await broadcast_state(state, event="prize_redeemed",
                          extra={"icon": prize["icon"], "name": prize["name"]})
    return _enrich(state)


@api.post("/quest-complete/{quest_id}")
async def quest_complete(quest_id: str):
    state = await get_state()
    q = next((x for x in state["quests"] if x["id"] == quest_id), None)
    if not q:
        raise HTTPException(404, "Unknown quest")
    if q["done"]:
        return _enrich(state)
    q["done"] = True
    q["progress"] = q["target"]
    state["xp"] += q["xp"]
    state["history"].insert(0, {
        "id": str(uuid.uuid4()), "type": "quest", "icon": q.get("icon", "⭐"),
        "title": f"Quest complete: {q['title']}",
        "detail": f"Earned {q['xp']} XP",
        "amount_str": f"+{q['xp']} XP", "color": "purple",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await save_state(state)
    await broadcast_state(state, event="quest_done",
                          extra={"icon": q.get("icon", "⭐"), "xp": q["xp"]})
    return _enrich(state)


@api.post("/wish")
async def make_wish(req: WishReq):
    """Wish & Grow — kid-friendly options. Predict GROW (up) or SHRINK (down) for a stock."""
    if req.ticker not in CANDY_BY_TICKER:
        raise HTTPException(400, "Unknown ticker")
    if req.direction not in ("grow", "shrink"):
        raise HTTPException(400, "Direction must be 'grow' or 'shrink'")
    state = await get_state()
    if not state["limits"].get("wishes_enabled", True):
        raise HTTPException(403, "Wish & Grow disabled by parent")
    max_stake = state["limits"].get("max_wish_stake", 10)
    if req.stake > max_stake:
        raise HTTPException(400, f"Stake exceeds parent's max ({max_stake} coins)")
    if state["coins"] < req.stake:
        raise HTTPException(400, "Not enough candy coins")

    candy = CANDY_BY_TICKER[req.ticker]
    start_price = state["prices"][req.ticker]
    now = datetime.now(timezone.utc)
    wish = {
        "id": str(uuid.uuid4()),
        "ticker": req.ticker,
        "candy_name": candy["candy_name"],
        "icon": candy["icon"],
        "direction": req.direction,
        "stake": req.stake,
        "start_price": start_price,
        "duration_sec": req.duration_sec,
        "created_at": now.isoformat(),
        "expires_at": (now.timestamp() + req.duration_sec),
        "status": "active",  # active | won | lost
        "end_price": None,
        "payout": 0,
    }
    state["coins"] -= req.stake
    state["wishes"].insert(0, wish)
    state["history"].insert(0, {
        "id": str(uuid.uuid4()), "type": "wish", "icon": "🌱" if req.direction == "grow" else "🍃",
        "title": f"Wish placed: {candy['icon']} {candy['candy_name']} → {req.direction.upper()}",
        "detail": f"Staked 🍬{req.stake} · {req.duration_sec}s wish",
        "amount_str": f"-🍬{req.stake}", "color": "purple",
        "timestamp": now.isoformat(),
    })
    await save_state(state)
    await broadcast_state(state, event="wish_placed",
                          extra={"wish_id": wish["id"], "ticker": req.ticker,
                                 "direction": req.direction, "icon": candy["icon"]})
    return {"status": "active", "wish": wish, "state": _enrich(state)}


async def wish_resolver_loop():
    """Every 1s, resolve any active wishes whose timer expired."""
    await asyncio.sleep(3)
    while True:
        try:
            state = await get_state()
            now_ts = datetime.now(timezone.utc).timestamp()
            changed = False
            for w in state.get("wishes", []):
                if w["status"] != "active":
                    continue
                if now_ts < w["expires_at"]:
                    continue
                # Resolve
                end_price = state["prices"].get(w["ticker"], w["start_price"])
                grew = end_price > w["start_price"]
                won = (w["direction"] == "grow" and grew) or (w["direction"] == "shrink" and not grew)
                w["end_price"] = end_price
                w["status"] = "won" if won else "lost"
                if won:
                    payout = w["stake"] * 2
                    w["payout"] = payout
                    state["coins"] += payout
                    state["xp"] += 50
                    state["history"].insert(0, {
                        "id": str(uuid.uuid4()), "type": "wish_won", "icon": "🦄",
                        "title": f"🦄 Wish came true! {w['icon']} {w['candy_name']}",
                        "detail": f"Won 🍬{payout} (2x stake) +50 XP",
                        "amount_str": f"+🍬{payout}", "color": "green",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                else:
                    state["xp"] = max(0, state["xp"] - 10)
                    state["history"].insert(0, {
                        "id": str(uuid.uuid4()), "type": "wish_lost", "icon": "💧",
                        "title": f"💧 Wish didn't come true: {w['icon']} {w['candy_name']}",
                        "detail": f"Lost 🍬{w['stake']} · -10 XP. Try again!",
                        "amount_str": f"-🍬{w['stake']}", "color": "muted",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                changed = True
                await sio.emit("wish_resolved", {
                    "wish_id": w["id"], "ticker": w["ticker"], "icon": w["icon"],
                    "candy_name": w["candy_name"], "direction": w["direction"],
                    "won": won, "payout": w["payout"], "stake": w["stake"],
                    "start_price": w["start_price"], "end_price": end_price,
                }, room=SESSION_ID)
            # Trim resolved wishes older than 10 (keep last 10 for history)
            active = [w for w in state["wishes"] if w["status"] == "active"]
            resolved = [w for w in state["wishes"] if w["status"] != "active"][:10]
            state["wishes"] = active + resolved
            if changed:
                await save_state(state)
                await broadcast_state(state)
        except Exception as e:
            logger.exception(f"wish resolver error: {e}")
        await asyncio.sleep(1)


@api.post("/limits")
async def set_limits(req: LimitsReq):
    state = await get_state()
    state["limits"] = req.model_dump()
    await save_state(state)
    await broadcast_state(state, extra={"toast": "Limits saved"})
    return _enrich(state)


@api.post("/ai/story")
async def ai_story(req: AIStoryReq):
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    candy = CANDY_BY_TICKER.get(req.ticker)
    if not candy:
        raise HTTPException(400, "Unknown ticker")
    direction = "up" if req.change_pct >= 0 else "down"
    sysmsg = (
        "You are a magical narrator in 'Candy Kingdom' explaining the stock market to a 6-year-old. "
        "Use whimsical candy/fairy-tale language. NEVER mention dollars, stocks, shares, or financial terms. "
        "Use 'candy coins', 'sparkles', or company products instead. Keep it 2-3 short sentences, joyful and curious."
    )
    user_text = (
        f"The candy called '{candy['candy_name']}' (which is really {candy['company']}) went {direction} "
        f"by {abs(req.change_pct):.1f}% today. Tell the kid a tiny imaginative story about why, "
        f"mentioning a real product or thing this company makes (e.g., iPhones, search, electric cars, "
        f"movies, burgers, shows). Add one fun emoji."
    )
    try:
        chat = (LlmChat(api_key=EMERGENT_LLM_KEY,
                        session_id=f"story-{uuid.uuid4()}",
                        system_message=sysmsg)
                .with_model("anthropic", "claude-sonnet-4-5-20250929"))
        story = await chat.send_message(UserMessage(text=user_text))
        return {"story": str(story).strip(), "ticker": req.ticker,
                "candy_name": candy["candy_name"], "icon": candy["icon"]}
    except Exception as e:
        logger.exception(f"AI story failed: {e}")
        fb = {
            "AAPL": f"{candy['icon']} The Lolly Pop Co. baked extra magic phones today — the kingdom's mailbox is full of orders! ✨",
            "GOOGL": f"{candy['icon']} Rainbow Drops painted answers across the sky — every wizard asked it a question! 🌈",
            "TSLA": f"{candy['icon']} Gummy Bears built super-fast candy cars that drive themselves to school! ⚡",
            "DIS": f"{candy['icon']} Ice Cream Castle opened a brand-new movie palace — princesses showed up! 🏰",
            "MCD": f"{candy['icon']} Choco Mountain served a million happy snacks to the kingdom today! 🍔",
            "NFLX": f"{candy['icon']} Birthday Cakes turned every TV into a magical show — pajama parties everywhere! 🎬",
        }
        return {"story": fb.get(req.ticker, f"{candy['icon']} Magic happened!"),
                "ticker": req.ticker, "candy_name": candy["candy_name"], "icon": candy["icon"]}


@api.post("/ai/quests")
async def ai_quests():
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    sysmsg = (
        "You generate 5 short daily quests for a kids investing game called Candy Kingdom. "
        "Return ONLY a JSON array, no prose. Each quest has fields: "
        "id (q1-q5), title (max 4 words, playful), desc (one short sentence), "
        "xp (int 50-500), target (int 1-10), icon (single emoji)."
    )
    try:
        chat = (LlmChat(api_key=EMERGENT_LLM_KEY,
                        session_id=f"quests-{uuid.uuid4()}",
                        system_message=sysmsg)
                .with_model("anthropic", "claude-sonnet-4-5-20250929"))
        result = await chat.send_message(UserMessage(
            text="Generate 5 fresh daily quests for today. Mix easy and challenging. Return ONLY JSON array."))
        import json, re
        text = str(result)
        m = re.search(r"\[.*\]", text, re.S)
        if not m:
            raise ValueError("no json array")
        quests = json.loads(m.group(0))
        clean = []
        for i, q in enumerate(quests[:5]):
            clean.append({
                "id": f"q{i+1}",
                "title": str(q.get("title", "Quest"))[:40],
                "desc": str(q.get("desc", ""))[:120],
                "xp": int(q.get("xp", 100)),
                "target": int(q.get("target", 1)),
                "progress": 0,
                "done": False,
                "icon": str(q.get("icon", "⭐"))[:4],
            })
        state = await get_state()
        state["quests"] = clean
        await save_state(state)
        await broadcast_state(state, extra={"toast": "✨ New quests arrived!"})
        return {"quests": clean}
    except Exception as e:
        logger.exception(f"AI quests failed: {e}")
        state = await get_state()
        state["quests"] = [q.copy() for q in DEFAULT_QUESTS]
        await save_state(state)
        await broadcast_state(state)
        return {"quests": DEFAULT_QUESTS, "fallback": True}


fastapi_app.include_router(api)


# ───────────────────────── Pitch Deck PDF ─────────────────────────
@fastapi_app.get("/api/pitch-deck")
async def pitch_deck():
    """Generate a 1-page PDF pitch deck of Lily's investing journey."""
    import io
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from fastapi.responses import StreamingResponse

    state = await get_state()
    portfolio_val = _portfolio_value(state)
    total_xp = state["xp"]
    total_coins = state["coins"]
    wishes = state.get("wishes", [])
    wishes_won = sum(1 for w in wishes if w["status"] == "won")
    wishes_lost = sum(1 for w in wishes if w["status"] == "lost")
    buy_history = [h for h in state["history"] if h["type"] == "buy"]
    biggest_buy = max(buy_history, key=lambda h: 1, default=None)

    # AI narrative
    narrative = ""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        sysmsg = ("You write a 2-sentence, parent-friendly journey summary for a kid investor's "
                  "pitch deck. Be specific with numbers, warm, professional. No emojis. Max 50 words.")
        usr = (f"Kid name: Lily, age 6. Portfolio value: ${portfolio_val:.2f}. XP earned: {total_xp}. "
               f"Candy coins held: {total_coins}. Wishes won: {wishes_won}/{wishes_won+wishes_lost}. "
               f"Stocks owned: {list(state['holdings'].keys())}. Write the narrative.")
        chat = (LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"pitch-{uuid.uuid4()}",
                        system_message=sysmsg)
                .with_model("anthropic", "claude-sonnet-4-5-20250929"))
        narrative = str(await chat.send_message(UserMessage(text=usr))).strip()
    except Exception as e:
        logger.exception(f"pitch ai fail: {e}")
        narrative = (f"Lily, age 6, has built a ${portfolio_val:.2f} portfolio across "
                     f"{len(state['holdings'])} real fractional shares, earned {total_xp} XP, "
                     f"and made {wishes_won} winning predictions while learning to invest through play.")

    # Build holdings chart (bar)
    chart_buf = io.BytesIO()
    if state["holdings"]:
        fig, ax = plt.subplots(figsize=(6, 2.2), dpi=120)
        tickers = list(state["holdings"].keys())
        values = [state["holdings"][t]["shares"] * state["prices"][t] for t in tickers]
        colors = ["#EC4899", "#8B5CF6", "#10B981", "#0EA5E9", "#B45309", "#EF4444"][: len(tickers)]
        bars = ax.bar(tickers, values, color=colors)
        ax.set_facecolor("#0B0F19")
        fig.patch.set_facecolor("#0B0F19")
        ax.tick_params(colors="#94A3B8")
        for spine in ax.spines.values():
            spine.set_color("#1F2937")
        ax.set_title("Holdings by value ($)", color="#FFFFFF", fontsize=11, pad=8)
        for b, v in zip(bars, values):
            ax.text(b.get_x() + b.get_width() / 2, v, f"${v:.0f}",
                    ha="center", va="bottom", color="#FFFFFF", fontsize=8)
        plt.tight_layout()
        plt.savefig(chart_buf, format="png", facecolor="#0B0F19")
        plt.close(fig)
        chart_buf.seek(0)

    # Build the PDF
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=letter)
    W, H = letter
    bg = HexColor("#0B0F19")
    cyan = HexColor("#06B6D4")
    gold = HexColor("#FBBF24")
    green = HexColor("#10B981")
    purple = HexColor("#C4B5FD")
    white = HexColor("#FFFFFF")
    muted = HexColor("#94A3B8")

    # Dark background
    c.setFillColor(bg)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Header
    c.setFillColor(cyan)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(0.6 * inch, H - 0.55 * inch, "STOCKQUEST · CANDY KINGDOM · INVESTOR PITCH")
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(0.6 * inch, H - 0.85 * inch, "Lily's Investing Journey")
    c.setFillColor(muted)
    c.setFont("Helvetica", 10)
    c.drawString(0.6 * inch, H - 1.05 * inch,
                 f"Custodial Account · UTMA · Generated {datetime.now(timezone.utc).strftime('%B %d, %Y')}")

    # Stats row
    stats = [
        ("Portfolio Value", f"${portfolio_val:.2f}", green),
        ("Candy Coins", f"{total_coins}", gold),
        ("XP Earned", f"{total_xp}", purple),
        ("Wishes Won", f"{wishes_won}/{wishes_won + wishes_lost or 1}", cyan),
    ]
    x = 0.6 * inch
    y = H - 1.95 * inch
    box_w = (W - 1.2 * inch) / 4 - 0.1 * inch
    for label, val, color in stats:
        c.setStrokeColor(HexColor("#1F2937"))
        c.setFillColor(HexColor("#11192B"))
        c.roundRect(x, y, box_w, 0.85 * inch, 8, fill=1, stroke=1)
        c.setFillColor(muted)
        c.setFont("Helvetica", 8)
        c.drawString(x + 0.15 * inch, y + 0.62 * inch, label.upper())
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(x + 0.15 * inch, y + 0.22 * inch, val)
        x += box_w + 0.12 * inch

    # AI Narrative box
    ny = y - 1.2 * inch
    c.setFillColor(HexColor("#0F1A2E"))
    c.setStrokeColor(cyan)
    c.roundRect(0.6 * inch, ny, W - 1.2 * inch, 1.0 * inch, 8, fill=1, stroke=1)
    c.setFillColor(cyan)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(0.75 * inch, ny + 0.78 * inch, "✦ LILY'S STORY (AI-NARRATED)")
    c.setFillColor(white)
    c.setFont("Helvetica", 10)
    # wrap narrative
    from textwrap import wrap
    lines = wrap(narrative, width=110)[:3]
    for i, line in enumerate(lines):
        c.drawString(0.75 * inch, ny + 0.55 * inch - i * 0.18 * inch, line)

    # Chart
    if chart_buf.getbuffer().nbytes > 0:
        chart_buf.seek(0)
        cy = ny - 2.6 * inch
        c.drawImage(ImageReader(chart_buf), 0.6 * inch, cy,
                    width=W - 1.2 * inch, height=2.3 * inch,
                    preserveAspectRatio=True, mask='auto')

    # Recent activity (last 5)
    ay = 1.6 * inch
    c.setFillColor(cyan)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(0.6 * inch, ay + 0.6 * inch, "RECENT ACTIVITY")
    c.setFillColor(white)
    c.setFont("Helvetica", 9)
    for i, h in enumerate(state["history"][:4]):
        c.setFillColor(white)
        c.drawString(0.6 * inch, ay + 0.4 * inch - i * 0.16 * inch,
                     f"{h['icon']}  {h['title'][:75]}")
        c.setFillColor(muted)
        c.setFont("Helvetica", 7)
        c.drawString(W - 1.4 * inch, ay + 0.4 * inch - i * 0.16 * inch,
                     h.get("amount_str", ""))
        c.setFont("Helvetica", 9)

    # Footer
    c.setFillColor(muted)
    c.setFont("Helvetica", 7)
    c.drawString(0.6 * inch, 0.4 * inch,
                 "Powered by StockQuest · Real fractional shares via UTMA custodial brokerage · "
                 "Parent-controlled limits and approvals")
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(gold)
    c.drawRightString(W - 0.6 * inch, 0.4 * inch, "stockquest.app")

    c.showPage()
    c.save()
    pdf_buf.seek(0)
    fname = f"lily-pitch-deck-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}.pdf"
    return StreamingResponse(pdf_buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


fastapi_app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@fastapi_app.on_event("shutdown")
async def on_shutdown():
    mongo_client.close()


socket_app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app,
                              socketio_path="/api/socket.io")
app = socket_app
