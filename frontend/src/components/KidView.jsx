import { useEffect, useMemo, useState } from "react";
import Confetti from "react-confetti";
import { motion, AnimatePresence } from "framer-motion";
import BuyModal from "./BuyModal";
import "./KidView.css";

const NAV = [
  { id: "shop", label: "SHOP", icon: "🏪" },
  { id: "chest", label: "CHEST", icon: "💎" },
  { id: "prizes", label: "PRIZES", icon: "🎁" },
  { id: "quests", label: "QUESTS", icon: "⭐" },
];

const BUBBLES = [
  "Tap a candy to invest! 🍭✨",
  "Hot candies are growing! 🔥",
  "Your chest is getting sweeter! 💎",
  "More candies = more sparkles! 🌈",
];

export default function KidView({ state, api, celebration, storyData }) {
  const [tab, setTab] = useState("shop");
  const [buyCandy, setBuyCandy] = useState(null);
  const [bubble, setBubble] = useState(BUBBLES[0]);
  const [confettiOn, setConfettiOn] = useState(false);

  useEffect(() => {
    const t = setInterval(() => setBubble(BUBBLES[Math.floor(Math.random() * BUBBLES.length)]), 5000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (celebration) {
      setConfettiOn(true);
      setTimeout(() => setConfettiOn(false), 2400);
    }
  }, [celebration]);

  const xpPct = useMemo(() => {
    const into = state.xp % 500;
    return Math.min(100, (into / 500) * 100);
  }, [state.xp]);

  const totalCandies = useMemo(() => {
    let n = 0;
    for (const [tk, h] of Object.entries(state.holdings || {})) {
      const candy = state.candies.find((c) => c.ticker === tk);
      if (candy) n += Math.round((h.shares * state.prices[tk]) / (state.prices[tk] / candy.divisor));
    }
    return n;
  }, [state]);

  return (
    <div className="kv-frame" data-testid="kid-view">
      {/* PHONE FRAME */}
      <div className="kv-phone">
        {/* Sky background */}
        <div className="kv-sky">
          {Array.from({ length: 14 }).map((_, i) => (
            <div key={i} className="kv-star" style={{
              left: `${Math.random() * 100}%`, top: `${Math.random() * 40}%`,
              width: `${Math.random() * 3 + 1}px`, height: `${Math.random() * 3 + 1}px`,
              animationDelay: `${Math.random() * 2}s`, animationDuration: `${Math.random() * 1.5 + 1}s`,
            }} />
          ))}
          <div className="kv-cloud" style={{ top: 10, animationDuration: "22s" }}>☁️</div>
          <div className="kv-cloud" style={{ top: 38, animationDuration: "28s", animationDelay: "6s" }}>☁️</div>
        </div>

        {/* Confetti */}
        {confettiOn && (
          <div className="kv-confetti">
            <Confetti width={355} height={780} recycle={false} numberOfPieces={150} gravity={0.25} />
          </div>
        )}

        {/* HUD */}
        <div className="kv-hud" data-testid="kid-hud">
          <div className="kv-coins" data-testid="kid-coins">
            <span className="kv-coin-icon">🍬</span>
            <span className="kv-coin-num">{state.coins}</span>
          </div>
          <div className="kv-xp" data-testid="kid-xp">
            <div className="kv-xp-row">
              <span className="kv-xp-icon">⭐</span>
              <span className="kv-xp-lv">Lv.{state.level}</span>
            </div>
            <div className="kv-xp-track"><div className="kv-xp-bar" style={{ width: `${xpPct}%` }} /></div>
          </div>
        </div>

        {/* Unicorn mascot */}
        <div className="kv-uni">
          <span className="kv-uni-char">🦄</span>
          <span className="kv-uni-bubble">{bubble}</span>
        </div>

        {/* Story panel (after buy) */}
        <AnimatePresence>
          {storyData && (
            <motion.div
              className="kv-story"
              initial={{ y: -20, opacity: 0, scale: 0.9 }}
              animate={{ y: 0, opacity: 1, scale: 1 }}
              exit={{ y: -20, opacity: 0 }}
              data-testid="kid-story"
            >
              <div className="kv-story-icon">{storyData.icon}</div>
              <div className="kv-story-body">
                <div className="kv-story-title">{storyData.candy_name} News!</div>
                <div className="kv-story-text">{storyData.story}</div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Bottom nav */}
        <div className="kv-nav" data-testid="kid-nav">
          {NAV.map((n) => (
            <button
              key={n.id}
              data-testid={`kid-nav-${n.id}`}
              className={`kv-ntab ${tab === n.id ? "on" : ""}`}
              onClick={() => setTab(n.id)}
            >
              <span className="kv-ntab-icon">{n.icon}</span>
              <span>{n.label}</span>
            </button>
          ))}
        </div>

        {/* SCREENS */}
        <div className="kv-scr-wrap" data-testid="kid-scr-wrap">
          {tab === "shop" && (
            <div className="kv-scr">
              <div className="kv-sec">✨ Candy Market ✨</div>
              <div className="kv-cgrid" data-testid="kid-shop">
                {state.candies.map((c) => (
                  <button
                    key={c.ticker}
                    data-testid={`candy-${c.ticker}`}
                    className="kv-ccard"
                    style={{ background: c.gradient }}
                    onClick={() => setBuyCandy(c)}
                  >
                    <span className="kv-cc-icon">{c.icon}</span>
                    <div className="kv-cc-name">{c.candy_name}</div>
                    <div className="kv-cc-real">{c.ticker}</div>
                    <div className="kv-cc-price">🍬{c.coin_price}</div>
                    <div className={`kv-cc-chg ${c.change_pct >= 0 ? "up" : "down"}`}>
                      {c.change_pct >= 0 ? "▲" : "▼"}{Math.abs(c.change_pct).toFixed(1)}%
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {tab === "chest" && (
            <div className="kv-scr">
              <div className="kv-chest-hero">
                <div className="kv-ch-lbl">MY CANDY CHEST</div>
                <div className="kv-ch-val">🍬 {state.coins}</div>
                <div className="kv-ch-real">Real value: ${(state.coins / 100).toFixed(2)} + ${state.portfolio_value.toFixed(2)} invested</div>
                <div className="kv-ch-rank">🌟 {state.rank}</div>
              </div>
              <div className="kv-sec">🪙 My Candy Shares</div>
              {Object.entries(state.holdings).map(([tk, h]) => {
                const candy = state.candies.find((c) => c.ticker === tk);
                if (!candy) return null;
                const value = h.shares * state.prices[tk];
                return (
                  <div key={tk} className="kv-hold-row" data-testid={`kid-hold-${tk}`}>
                    <span className="kv-hold-icon">{candy.icon}</span>
                    <div className="kv-hold-info">
                      <div className="kv-hold-name">{candy.candy_name}</div>
                      <div className="kv-hold-shares">🍬{(value * 100).toFixed(0)} worth</div>
                    </div>
                    <div className="kv-hold-val">+{((value / (h.shares * h.avg_cost) - 1) * 100).toFixed(1)}%</div>
                  </div>
                );
              })}
            </div>
          )}

          {tab === "prizes" && (
            <div className="kv-scr">
              <div className="kv-sec">🎁 Spend Your Stars!</div>
              <div className="kv-stars-bar">You have ⭐ <b>{state.xp}</b> stars!</div>
              <div className="kv-prize-grid">
                {state.prizes.map((p) => {
                  const locked = state.xp < p.cost;
                  return (
                    <button
                      key={p.id}
                      data-testid={`kid-prize-${p.id}`}
                      className={`kv-prize-card ${locked ? "locked" : ""}`}
                      onClick={() => !locked && api.redeem(p.id)}
                      disabled={locked}
                    >
                      {locked && <div className="kv-prize-lock">🔒</div>}
                      <div className="kv-prize-icon">{p.icon}</div>
                      <div className="kv-prize-name">{p.name}</div>
                      <div className="kv-prize-cost">⭐ {p.cost}</div>
                      <div className="kv-prize-type">{p.type}</div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {tab === "quests" && (
            <div className="kv-scr">
              <div className="kv-sec-row">
                <div className="kv-sec">🌈 Your Quests</div>
                <button data-testid="kid-refresh-quests" className="kv-mini-btn" onClick={() => api.refreshQuests()}>✨ AI</button>
              </div>
              {state.quests.map((q) => (
                <div key={q.id} className={`kv-quest ${q.done ? "done" : ""}`} data-testid={`kid-quest-${q.id}`}>
                  <div className="kv-quest-icon">{q.icon}</div>
                  <div className="kv-quest-body">
                    <div className="kv-quest-title">{q.title}</div>
                    <div className="kv-quest-desc">{q.desc}</div>
                    <div className="kv-quest-track"><div className="kv-quest-bar" style={{ width: `${Math.min(100, (q.progress / q.target) * 100)}%` }} /></div>
                  </div>
                  <div className="kv-quest-right">
                    <div className="kv-quest-xp">⭐ {q.xp}</div>
                    {!q.done && q.progress >= q.target && (
                      <button data-testid={`kid-claim-${q.id}`} className="kv-quest-claim" onClick={() => api.questComplete(q.id)}>Claim</button>
                    )}
                    {q.done && <div className="kv-quest-done">✓</div>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {buyCandy && (
        <BuyModal
          candy={buyCandy}
          coins={state.coins}
          onClose={() => setBuyCandy(null)}
          onBuy={async (n) => { await api.buy(buyCandy.ticker, n); setBuyCandy(null); }}
        />
      )}
    </div>
  );
}
