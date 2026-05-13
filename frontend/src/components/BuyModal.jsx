import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import "./BuyModal.css";

export default function BuyModal({ candy, coins, onClose, onBuy }) {
  const [qty, setQty] = useState(1);
  const total = candy.coin_price * qty;
  const affordable = coins >= total;

  return (
    <AnimatePresence>
      <motion.div
        className="bm-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        data-testid="buy-modal"
      >
        <motion.div
          className="bm-card"
          style={{ background: candy.gradient }}
          initial={{ scale: 0.6, y: 30 }}
          animate={{ scale: 1, y: 0 }}
          exit={{ scale: 0.6, y: 30 }}
          transition={{ type: "spring", damping: 18 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="bm-badge">Tap & Buy!</div>
          <div className="bm-icon">{candy.icon}</div>
          <div className="bm-name">{candy.candy_name}</div>
          <div className="bm-real">{candy.ticker} · {candy.company}</div>

          <div className="bm-qty-row">
            <button className="bm-qb" data-testid="buy-modal-minus" onClick={() => setQty(Math.max(1, qty - 1))}>−</button>
            <div className="bm-qty" data-testid="buy-modal-qty">{qty}</div>
            <button className="bm-qb" data-testid="buy-modal-plus" onClick={() => setQty(qty + 1)}>+</button>
          </div>

          <div className="bm-total">Cost: 🍬 {total}</div>
          {!affordable && <div className="bm-warn">Not enough coins!</div>}

          <div className="bm-actions">
            <button className="bm-cancel" data-testid="buy-modal-cancel" onClick={onClose}>Nope</button>
            <button
              className="bm-buy"
              data-testid="buy-modal-confirm"
              disabled={!affordable}
              onClick={() => onBuy(qty)}
            >🛒 Buy!</button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
