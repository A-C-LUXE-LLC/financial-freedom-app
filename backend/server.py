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
                   "sell_approval": "always", "age_unlock": 13},
        "quests": [q.copy() for q in DEFAULT_QUESTS],
        "prizes": [p.copy() for p in DEFAULT_PRIZES],
        "redeemed": [],
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
    logger.info("StockQuest backend started")


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
