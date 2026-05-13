import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import "./Walkthrough.css";

/**
 * Auto-play 60-second demo walkthrough for grant reviewers.
 * Drives view switches + API calls in sequence, with overlay captions.
 */
const STEPS = [
  { sec: 0,  view: "split",  caption: "Welcome to StockQuest — a custodial investing platform for kids that pairs real fractional shares with a Candy Kingdom game.", action: null },
  { sec: 5,  view: "parent", caption: "Step 1: Parent funds Lily's wallet with $20 of allowance.", action: "fund_20" },
  { sec: 11, view: "split",  caption: "Funds land instantly as 🍬 Candy Coins in Lily's wallet — she sees coins, never dollars.", action: null },
  { sec: 16, view: "kid",    caption: "Step 2: Lily picks a candy in the market. Each candy = a real stock.", action: "switch_shop" },
  { sec: 21, view: "kid",    caption: "She buys 'Lolly Pop Co.' — that's actually Apple stock (AAPL). Under the auto-approve limit, so it executes instantly.", action: "buy_aapl_small" },
  { sec: 27, view: "kid",    caption: "Step 3: Lily makes a Wish — predicting the candy will grow! This is options trading, made magical.", action: "place_wish" },
  { sec: 35, view: "kid",    caption: "30-second timer. Real-time prices drive the outcome. Bounded loss, controlled by parents.", action: null },
  { sec: 42, view: "parent", caption: "Step 4: Bigger trades require parent approval. Real-time approval queue.", action: "switch_approvals" },
  { sec: 49, view: "split",  caption: "Approve → instant confetti in the kid's view via WebSocket. AI generates a kid-friendly story.", action: "approve_one" },
  { sec: 56, view: "split",  caption: "✨ Real fractional shares · Parent controls every dollar · Kid learns by playing. That's StockQuest.", action: null },
];

export default function Walkthrough({ onStop, setView, api, state }) {
  const [stepIdx, setStepIdx] = useState(0);
  const [progress, setProgress] = useState(0);  // 0-100 within current step
  const startedAt = useRef(Date.now());
  const fired = useRef(new Set());

  useEffect(() => {
    const dur = 62; // total seconds
    const iv = setInterval(() => {
      const elapsed = (Date.now() - startedAt.current) / 1000;
      if (elapsed >= dur) { onStop(); return; }
      // find current step
      let idx = 0;
      for (let i = STEPS.length - 1; i >= 0; i--) {
        if (elapsed >= STEPS[i].sec) { idx = i; break; }
      }
      const nextSec = STEPS[idx + 1]?.sec ?? dur;
      const stepDur = nextSec - STEPS[idx].sec;
      const stepElapsed = elapsed - STEPS[idx].sec;
      setProgress(Math.min(100, (stepElapsed / stepDur) * 100));
      setStepIdx(idx);

      const s = STEPS[idx];
      // Switch view on step entry
      if (!fired.current.has(`view-${idx}`)) {
        fired.current.add(`view-${idx}`);
        setView(s.view);
      }
      // Trigger action ~0.5s into step
      if (s.action && stepElapsed > 0.4 && !fired.current.has(`act-${idx}`)) {
        fired.current.add(`act-${idx}`);
        runAction(s.action, api, state);
      }
    }, 200);
    return () => clearInterval(iv);
  }, []); // eslint-disable-line

  const step = STEPS[stepIdx];

  return (
    <div className="wt-overlay" data-testid="walkthrough-overlay">
      <div className="wt-band wt-top">
        <div className="wt-badge">
          <span className="wt-rec" /> AUTO-PLAY DEMO · Step {stepIdx + 1}/{STEPS.length}
        </div>
        <button className="wt-stop" onClick={onStop} data-testid="walkthrough-stop">Stop</button>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={stepIdx}
          className="wt-caption"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.4 }}
        >
          {step.caption}
        </motion.div>
      </AnimatePresence>

      <div className="wt-band wt-bottom">
        <div className="wt-progress">
          <div className="wt-progress-bar" style={{ width: `${progress}%` }} />
        </div>
      </div>
    </div>
  );
}

async function runAction(action, api, state) {
  try {
    if (action === "fund_20") {
      await api.fund(20);
    } else if (action === "buy_aapl_small") {
      // small buy (1 candy) -- should auto-approve
      await api.buy("AAPL", 1);
    } else if (action === "place_wish") {
      await api.wish("GOOGL", "grow", 3, 30);
    } else if (action === "approve_one") {
      const first = state?.pending?.[0];
      if (first) await api.approve(first.id);
    } else if (action === "switch_shop" || action === "switch_approvals") {
      // visual-only; view already switched
    }
  } catch (e) {
    // silently continue walkthrough
    console.warn("walkthrough action:", action, e?.message);
  }
}
