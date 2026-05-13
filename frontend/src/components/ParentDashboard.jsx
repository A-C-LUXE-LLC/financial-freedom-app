import { useMemo, useState } from "react";
import "./ParentDashboard.css";

const TABS = [
  { id: "overview", label: "Overview", icon: "📊" },
  { id: "approve", label: "Approvals", icon: "⏳" },
  { id: "fund", label: "Fund", icon: "💳" },
  { id: "holdings", label: "Holdings", icon: "📈" },
  { id: "rewards", label: "Rewards", icon: "🎁" },
  { id: "limits", label: "Limits", icon: "⚙️" },
  { id: "history", label: "History", icon: "📋" },
];

export default function ParentDashboard({ state, api }) {
  const [tab, setTab] = useState("overview");
  const [customAmt, setCustomAmt] = useState("");
  const [limits, setLimits] = useState(state.limits);
  const pendingCount = state.pending?.length || 0;
  const portfolio = state.portfolio_value || 0;
  const cash = state.cash_balance || 0;

  const holdingsList = useMemo(() => {
    return Object.entries(state.holdings || {}).map(([tk, h]) => {
      const candy = state.candies.find((c) => c.ticker === tk);
      const price = state.prices[tk];
      const value = h.shares * price;
      const gain = value - h.shares * h.avg_cost;
      return { tk, ...h, candy, price, value, gain };
    });
  }, [state]);

  return (
    <div className="pd-root" data-testid="parent-dashboard">
      {/* Header */}
      <div className="pd-header">
        <div>
          <div className="pd-eyebrow">STOCKQUEST · CUSTODIAL PLATFORM</div>
          <div className="pd-title">Johnson Family</div>
          <div className="pd-sub">Lily · Age 6 · UTMA Account · Powered by real fractional shares</div>
        </div>
        <div className="pd-status">
          <span className="pd-status-dot" />
          <span>Custodial Active</span>
        </div>
      </div>

      {/* Tabs */}
      <nav className="pd-tabs" data-testid="parent-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            data-testid={`parent-tab-${t.id}`}
            className={`pd-tab ${tab === t.id ? "on" : ""}`}
            onClick={() => setTab(t.id)}
          >
            <span className="pd-tab-icon">{t.icon}</span>
            <span>{t.label}</span>
            {t.id === "approve" && pendingCount > 0 && (
              <span className="pd-badge" data-testid="parent-approval-badge">{pendingCount}</span>
            )}
          </button>
        ))}
      </nav>

      <div className="pd-body">
        {/* OVERVIEW */}
        {tab === "overview" && (
          <div className="pd-section">
            <div className="pd-stats">
              <StatCard label="Portfolio Value" value={`$${portfolio.toFixed(2)}`} delta="+$32.40 · +6.5%" accent="green" testid="stat-portfolio" />
              <StatCard label="Cash Balance" value={`$${cash.toFixed(2)}`} delta="Ready to invest" testid="stat-cash" />
              <StatCard label="Candy Coins" value={`🍬${state.coins}`} delta="100 coins = $1.00" accent="gold" testid="stat-coins" />
              <StatCard label="XP Stars" value={`⭐${state.xp}`} delta={`Level ${state.level} · ${state.rank}`} accent="purple" testid="stat-xp" />
            </div>
            <SectionTitle>How it works</SectionTitle>
            <div className="how-grid">
              {[
                ["1", "#06B6D4", "You fund Lily's wallet", "Add allowance as Candy Coins. $1 = 🍬100."],
                ["2", "#8B5CF6", "Lily picks a candy", "Each candy = a real stock (Apple, Google, Tesla…)"],
                ["3", "#FBBF24", "Auto or you approve", `Trades under $${state.limits.auto_approve_under} auto-execute.`],
                ["4", "#10B981", "Real fractional shares", "Actual shares held in Lily's UTMA custodial account."],
                ["5", "#F43F5E", "XP earned, real rewards", "Gift cards, cash, toys, experiences."],
              ].map(([n, color, t, d]) => (
                <div className="how-row" key={n}>
                  <div className="how-num" style={{ background: color }}>{n}</div>
                  <div>
                    <div className="how-title">{t}</div>
                    <div className="how-desc">{d}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* APPROVALS */}
        {tab === "approve" && (
          <div className="pd-section">
            <SectionTitle>Pending Trades</SectionTitle>
            {state.pending.length === 0 && (
              <div className="empty" data-testid="parent-pending-empty">All caught up. No pending trades.</div>
            )}
            {state.pending.map((p) => (
              <div className="pend-card" key={p.id} data-testid={`pending-${p.id}`}>
                <div className="pend-icon">{p.icon}</div>
                <div className="pend-info">
                  <div className="pend-title">Lily wants to buy {p.ticker}</div>
                  <div className="pend-detail">{p.candies} candies · ~${p.usd_cost.toFixed(2)} · "{p.candy_name}"</div>
                </div>
                <div className="pend-actions">
                  <button data-testid={`approve-btn-${p.id}`} className="btn-approve" onClick={() => api.approve(p.id)}>✓ Yes</button>
                  <button data-testid={`deny-btn-${p.id}`} className="btn-deny" onClick={() => api.deny(p.id)}>✗</button>
                </div>
              </div>
            ))}
            <div className="pd-notice">
              🔒 Trades above your auto-approve limit (${state.limits.auto_approve_under}) require approval. Shares purchased through your linked custodial brokerage.
            </div>
          </div>
        )}

        {/* FUND */}
        {tab === "fund" && (
          <div className="pd-section">
            <SectionTitle>Add Allowance</SectionTitle>
            <div className="fund-card">
              <div className="fund-desc">Send Candy Coins to Lily. Funds appear instantly. $1 = 🍬100 coins.</div>
              <div className="fund-presets">
                {[5, 10, 20, 50].map((amt) => (
                  <button key={amt} data-testid={`fund-${amt}-btn`} className="btn-gold" onClick={() => api.fund(amt)}>${amt}</button>
                ))}
              </div>
              <div className="fund-custom">
                <input
                  type="number"
                  value={customAmt}
                  onChange={(e) => setCustomAmt(e.target.value)}
                  placeholder="Custom $"
                  data-testid="fund-custom-input"
                />
                <button
                  data-testid="fund-custom-btn"
                  className="btn-cyan"
                  onClick={() => {
                    const v = parseFloat(customAmt);
                    if (v > 0) { api.fund(v); setCustomAmt(""); }
                  }}
                >Send 💸</button>
              </div>
            </div>
          </div>
        )}

        {/* HOLDINGS */}
        {tab === "holdings" && (
          <div className="pd-section">
            <div className="hold-hero">
              <div className="hold-eyebrow">CUSTODIAL PORTFOLIO VALUE</div>
              <div className="hold-val">${portfolio.toFixed(2)}</div>
              <div className="hold-gain">▲ Real fractional shares</div>
            </div>
            <SectionTitle>Real Holdings</SectionTitle>
            {holdingsList.map((h) => (
              <div className="h-row" key={h.tk} data-testid={`holding-${h.tk}`}>
                <div className="h-icon">{h.candy?.icon || "🍬"}</div>
                <div className="h-sym">{h.tk}</div>
                <div className="h-meta">
                  <div className="h-name">{h.candy?.company}</div>
                  <div className="h-qty">{h.shares} shares · avg ${h.avg_cost}</div>
                </div>
                <div className="h-vals">
                  <div className="h-val">${h.value.toFixed(2)}</div>
                  <div className={`h-gain ${h.gain >= 0 ? "up" : "down"}`}>
                    {h.gain >= 0 ? "▲" : "▼"} ${Math.abs(h.gain).toFixed(2)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* REWARDS */}
        {tab === "rewards" && (
          <div className="pd-section">
            <SectionTitle>Prize Pool</SectionTitle>
            <div className="pd-notice">Kids redeem XP Stars for real rewards. You control what's available — and approve every redemption.</div>
            <div className="reward-grid">
              {state.prizes.map((p) => (
                <div className="reward-card" key={p.id} data-testid={`prize-${p.id}`}>
                  <div className="reward-icon">{p.icon}</div>
                  <div className="reward-name">{p.name}</div>
                  <div className="reward-cost">⭐ {p.cost} XP</div>
                  <div className="reward-type">{p.type}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* LIMITS */}
        {tab === "limits" && (
          <div className="pd-section">
            <SectionTitle>Trading Controls</SectionTitle>
            <div className="limits-card">
              <LimitRow label="Auto-approve under ($)" desc="Trades below this need no approval">
                <input type="number" data-testid="limit-auto-approve" value={limits.auto_approve_under}
                  onChange={(e) => setLimits({ ...limits, auto_approve_under: +e.target.value })} />
              </LimitRow>
              <LimitRow label="Max per trade ($)" desc="Lily cannot request trades above this">
                <input type="number" data-testid="limit-max-per-trade" value={limits.max_per_trade}
                  onChange={(e) => setLimits({ ...limits, max_per_trade: +e.target.value })} />
              </LimitRow>
              <LimitRow label="Max per week ($)" desc="Total weekly investment cap">
                <input type="number" data-testid="limit-max-per-week" value={limits.max_per_week}
                  onChange={(e) => setLimits({ ...limits, max_per_week: +e.target.value })} />
              </LimitRow>
              <LimitRow label="Sell approval" desc="Require approval before Lily can sell">
                <select data-testid="limit-sell-approval" value={limits.sell_approval}
                  onChange={(e) => setLimits({ ...limits, sell_approval: e.target.value })}>
                  <option value="always">Always require</option>
                  <option value="under_10">Auto under $10</option>
                  <option value="kid">Lily decides</option>
                </select>
              </LimitRow>
              <LimitRow label="Age unlock" desc="Full trading control at this age" last>
                <select data-testid="limit-age-unlock" value={limits.age_unlock}
                  onChange={(e) => setLimits({ ...limits, age_unlock: +e.target.value })}>
                  <option value={13}>Age 13</option>
                  <option value={16}>Age 16</option>
                  <option value={18}>Age 18</option>
                </select>
              </LimitRow>
              <button data-testid="save-limits-btn" className="btn-green" onClick={() => api.setLimits(limits)}>💾 Save Limits</button>
            </div>
          </div>
        )}

        {/* HISTORY */}
        {tab === "history" && (
          <div className="pd-section">
            <SectionTitle>Transaction Log</SectionTitle>
            {state.history.map((h) => (
              <div className="tx" key={h.id} data-testid={`tx-${h.id}`}>
                <div className="tx-ico">{h.icon}</div>
                <div className="tx-body">
                  <div className="tx-title">{h.title}</div>
                  <div className="tx-date">{new Date(h.timestamp).toLocaleString()} · {h.detail}</div>
                </div>
                <div className={`tx-amt tx-${h.color}`}>{h.amount_str}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const StatCard = ({ label, value, delta, accent, testid }) => (
  <div className={`stat-card stat-${accent || ""}`} data-testid={testid}>
    <div className="stat-label">{label}</div>
    <div className="stat-value">{value}</div>
    <div className="stat-delta">{delta}</div>
  </div>
);

const SectionTitle = ({ children }) => <div className="pd-section-title">{children}</div>;

const LimitRow = ({ label, desc, children, last }) => (
  <div className={`lim-row ${last ? "last" : ""}`}>
    <div>
      <div className="lim-label">{label}</div>
      <div className="lim-desc">{desc}</div>
    </div>
    <div>{children}</div>
  </div>
);
