import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import "./WishScreen.css";

/**
 * Wish & Grow — kid-friendly options trading.
 * Pick a candy → predict GROW 🌱 or SHRINK 🍃 → wager 1-N candy coins → win 2x if right.
 */
export default function WishScreen({ state, api }) {
  const [picked, setPicked] = useState(null);     // candy ticker
  const [stake, setStake] = useState(1);
  const [direction, setDirection] = useState(null); // 'grow' | 'shrink'

  const wishesOn = state.limits?.wishes_enabled !== false;
  const maxStake = state.limits?.max_wish_stake ?? 10;

  useEffect(() => {
    if (stake > maxStake) setStake(maxStake);
  }, [maxStake, stake]);

  const candy = useMemo(
    () => state.candies?.find((c) => c.ticker === picked),
    [picked, state.candies]
  );

  const activeWishes = (state.wishes || []).filter((w) => w.status === "active");
  const resolvedWishes = (state.wishes || []).filter((w) => w.status !== "active").slice(0, 4);

  const submit = async () => {
    if (!picked || !direction) return;
    try {
      await api.wish(picked, direction, stake, 30);
      setPicked(null);
      setDirection(null);
      setStake(1);
    } catch (e) {
      // surface backend error to toast via global handler (state_update broadcast will not happen)
      console.error(e);
    }
  };

  if (!wishesOn) {
    return (
      <div className="ws-disabled" data-testid="wish-disabled">
        <div className="ws-d-icon">🔒</div>
        <div className="ws-d-text">Wish &amp; Grow is paused by your parent.</div>
      </div>
    );
  }

  return (
    <div className="ws-root" data-testid="wish-screen">
      <div className="ws-title">🦄 Wish &amp; Grow</div>
      <div className="ws-sub">Tap a candy, pick GROW or SHRINK, watch the magic happen!</div>

      {/* Candy picker */}
      <div className="ws-pick-row">
        {state.candies?.map((c) => (
          <button
            key={c.ticker}
            data-testid={`wish-pick-${c.ticker}`}
            className={`ws-pick ${picked === c.ticker ? "on" : ""}`}
            onClick={() => setPicked(c.ticker)}
            style={picked === c.ticker ? { background: c.gradient, color: "#fff" } : {}}
          >
            <span className="ws-pick-icon">{c.icon}</span>
          </button>
        ))}
      </div>

      {/* Wish builder */}
      {candy && (
        <motion.div
          className="ws-builder"
          style={{ background: candy.gradient }}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          data-testid="wish-builder"
        >
          <div className="ws-b-char">{candy.icon}</div>
          <div className="ws-b-title">Will {candy.candy_name}…</div>

          <div className="ws-dir-row">
            <button
              data-testid="wish-grow-btn"
              className={`ws-dir ws-dir-grow ${direction === "grow" ? "on" : ""}`}
              onClick={() => setDirection("grow")}
            >
              <div className="ws-dir-icon">🌱</div>
              <div className="ws-dir-label">GROW BIG</div>
            </button>
            <button
              data-testid="wish-shrink-btn"
              className={`ws-dir ws-dir-shrink ${direction === "shrink" ? "on" : ""}`}
              onClick={() => setDirection("shrink")}
            >
              <div className="ws-dir-icon">🍃</div>
              <div className="ws-dir-label">GET SMALL</div>
            </button>
          </div>

          {direction && (
            <motion.div
              className="ws-stake-wrap"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <div className="ws-stake-lbl">How many 🍬?</div>
              <div className="ws-stake-row">
                <button
                  data-testid="wish-stake-minus"
                  className="ws-sb"
                  onClick={() => setStake(Math.max(1, stake - 1))}
                >−</button>
                <div className="ws-stake-coins" data-testid="wish-stake-coins">
                  {Array.from({ length: stake }).map((_, i) => (
                    <span key={i} className="ws-coin" style={{ left: i * 8 }}>🍬</span>
                  ))}
                </div>
                <div className="ws-stake-num" data-testid="wish-stake-num">{stake}</div>
                <button
                  data-testid="wish-stake-plus"
                  className="ws-sb"
                  onClick={() => setStake(Math.min(maxStake, stake + 1))}
                >+</button>
              </div>
              <div className="ws-payout">
                If your wish comes true: <b>🍬 {stake * 2} back!</b>
              </div>
              <button
                data-testid="wish-cast-btn"
                className="ws-cast"
                disabled={state.coins < stake}
                onClick={submit}
              >
                ✨ Wish Big! ✨
              </button>
            </motion.div>
          )}
        </motion.div>
      )}

      {/* Active wishes */}
      {activeWishes.length > 0 && (
        <>
          <div className="ws-section">⏳ Active Wishes</div>
          <div className="ws-active-list">
            {activeWishes.map((w) => (
              <ActiveWish key={w.id} w={w} />
            ))}
          </div>
        </>
      )}

      {/* Recent results */}
      {resolvedWishes.length > 0 && (
        <>
          <div className="ws-section">📜 Recent Wishes</div>
          <div className="ws-results">
            {resolvedWishes.map((w) => (
              <div key={w.id} className={`ws-result ws-${w.status}`} data-testid={`wish-result-${w.id}`}>
                <div className="ws-r-icon">{w.icon}</div>
                <div className="ws-r-body">
                  <div className="ws-r-title">
                    {w.candy_name} · {w.direction === "grow" ? "🌱" : "🍃"}
                  </div>
                  <div className="ws-r-detail">
                    {w.status === "won"
                      ? `🦄 +🍬${w.payout} +50 XP`
                      : `💧 Lost 🍬${w.stake}. Try again!`}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/** Countdown ring for an active wish. */
function ActiveWish({ w }) {
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now() / 1000), 250);
    return () => clearInterval(id);
  }, []);
  const remaining = Math.max(0, Math.ceil(w.expires_at - now));
  const pct = Math.min(100, ((w.duration_sec - remaining) / w.duration_sec) * 100);
  return (
    <div className="ws-aw" data-testid={`wish-active-${w.id}`}>
      <div className="ws-aw-icon">{w.icon}</div>
      <div className="ws-aw-info">
        <div className="ws-aw-title">
          {w.candy_name} · {w.direction === "grow" ? "🌱 GROW" : "🍃 SHRINK"}
        </div>
        <div className="ws-aw-track">
          <div className="ws-aw-bar" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <div className="ws-aw-count">{remaining}s</div>
    </div>
  );
}
