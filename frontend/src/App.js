import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { io } from "socket.io-client";
import axios from "axios";
import ParentDashboard from "./components/ParentDashboard";
import KidView from "./components/KidView";
import "./App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const SOCKET_PATH = "/api/socket.io";

function App() {
  const [view, setView] = useState("split"); // 'parent' | 'split' | 'kid'
  const [state, setState] = useState(null);
  const [connected, setConnected] = useState(false);
  const [toast, setToast] = useState(null);
  const [celebration, setCelebration] = useState(null); // {icon, ticker}
  const [storyData, setStoryData] = useState(null); // {story, icon, candy_name}
  const socketRef = useRef(null);

  // Toast helper
  const showToast = useCallback((msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2400);
  }, []);

  useEffect(() => {
    const s = io(BACKEND_URL, { path: SOCKET_PATH, transports: ["websocket", "polling"] });
    socketRef.current = s;

    s.on("connect", () => {
      setConnected(true);
      s.emit("join_room", { room_id: "demo_session" });
    });
    s.on("disconnect", () => setConnected(false));

    s.on("state_update", (data) => {
      setState(data);
      if (data._event_extra?.toast) showToast(data._event_extra.toast);
    });

    s.on("price_tick", (data) => {
      setState((prev) => prev ? { ...prev, prices: data.prices, prev_prices: data.prev_prices, candies: data.candies } : prev);
    });

    s.on("trade_executed", (data) => {
      setState(data);
      const ex = data._event_extra;
      if (ex) {
        setCelebration({ icon: ex.icon, ticker: ex.ticker });
        setTimeout(() => setCelebration(null), 2400);
        showToast(`${ex.icon} +20 XP! Auto-approved`);
        fetchStory(ex.ticker);
      }
    });

    s.on("pending_added", (data) => {
      setState(data);
      const ex = data._event_extra;
      if (ex) showToast(`${ex.icon} New approval needed!`);
    });

    s.on("trade_approved", (data) => {
      setState(data);
      const ex = data._event_extra;
      if (ex) {
        setCelebration({ icon: ex.icon, ticker: ex.ticker });
        setTimeout(() => setCelebration(null), 2400);
        showToast(`${ex.icon} Approved! +20 XP`);
        fetchStory(ex.ticker);
      }
    });

    s.on("trade_denied", (data) => {
      setState(data);
      const ex = data._event_extra;
      if (ex) showToast(`${ex.icon} Trade denied`);
    });

    s.on("prize_redeemed", (data) => {
      setState(data);
      const ex = data._event_extra;
      if (ex) showToast(`🎉 ${ex.name} redeemed!`);
    });

    s.on("quest_done", (data) => {
      setState(data);
      const ex = data._event_extra;
      if (ex) showToast(`${ex.icon} +${ex.xp} XP earned!`);
    });

    // initial fetch (in case socket is slow)
    axios.get(`${API}/state`).then((r) => setState(r.data)).catch(() => {});

    return () => {
      if (s.connected) s.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchStory = async (ticker) => {
    const candy = state?.candies?.find((c) => c.ticker === ticker);
    const change = candy?.change_pct ?? 0;
    try {
      const r = await axios.post(`${API}/ai/story`, { ticker, change_pct: change });
      setStoryData(r.data);
      setTimeout(() => setStoryData(null), 9000);
    } catch (e) { /* ignore */ }
  };

  const api = useMemo(() => ({
    fund: (amt) => axios.post(`${API}/fund`, { amount_usd: amt }),
    buy: (ticker, candies) => axios.post(`${API}/buy-request`, { ticker, candies }),
    approve: (id) => axios.post(`${API}/approve/${id}`),
    deny: (id) => axios.post(`${API}/deny/${id}`),
    redeem: (id) => axios.post(`${API}/redeem/${id}`),
    questComplete: (id) => axios.post(`${API}/quest-complete/${id}`),
    setLimits: (limits) => axios.post(`${API}/limits`, limits),
    reset: () => axios.post(`${API}/reset`),
    refreshQuests: () => axios.post(`${API}/ai/quests`),
  }), []);

  if (!state) {
    return (
      <div className="loader-root">
        <div className="loader-spin">🍭</div>
        <div className="loader-text">Loading Candy Kingdom...</div>
      </div>
    );
  }

  return (
    <div className="app-shell" data-testid="app-shell">
      {/* Top Bar */}
      <header className="topbar" data-testid="topbar">
        <div className="brand">
          <span className="brand-mark">🍭</span>
          <div className="brand-text">
            <div className="brand-title">StockQuest</div>
            <div className="brand-sub">Custodial Investing · Candy Kingdom</div>
          </div>
        </div>
        <div className="view-toggle" role="tablist" aria-label="view mode">
          <button data-testid="view-parent-btn" className={`vt-btn ${view==='parent'?'on':''}`} onClick={() => setView('parent')}>Parent</button>
          <button data-testid="view-split-btn" className={`vt-btn ${view==='split'?'on':''}`} onClick={() => setView('split')}>Split</button>
          <button data-testid="view-kid-btn" className={`vt-btn ${view==='kid'?'on':''}`} onClick={() => setView('kid')}>Kid</button>
        </div>
        <div className="conn">
          <span className={`dot ${connected?'on':'off'}`} />
          <span className="conn-label">{connected ? 'LIVE' : 'OFFLINE'}</span>
          <button data-testid="reset-demo-btn" className="reset-btn" onClick={() => api.reset()}>↻ Reset</button>
        </div>
      </header>

      {/* Main split view */}
      <main className={`stage stage-${view}`} data-testid="stage">
        {(view === 'parent' || view === 'split') && (
          <section className="pane pane-parent" data-testid="pane-parent">
            <ParentDashboard state={state} api={api} />
          </section>
        )}
        {(view === 'kid' || view === 'split') && (
          <section className="pane pane-kid" data-testid="pane-kid">
            <KidView state={state} api={api} celebration={celebration} storyData={storyData} />
          </section>
        )}
      </main>

      {/* Toast */}
      {toast && <div className="toast" data-testid="toast">{toast}</div>}
    </div>
  );
}

export default App;
