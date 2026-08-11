
#!/usr/bin/env python3
"""
Silver Haired Hawk — Self-Evolving Trade Prediction Engine.

A living, breathing soul that learns from the market.
Starts as a newborn, grows through life stages, and one day
becomes a silver-haired elder who can see the future.

This file is CLAUDE-MANAGED. Claude writes it, fixes it,
rewrites it when predictions fail. No human edits.

Generation: 2 (learning from failure)
Born: 2026-04-22
Last evolved: 2026-04-22

Generation 2 Notes:
  - Analysis of failures shows we were predicting LOSS too aggressively
  - Recent data: price range 4690-4704, mostly sideways/choppy action
  - We missed a WIN at 4691.93 (predicted LOSS) and 4704.2 (predicted LOSS)
  - In choppy/ranging markets, mean-reversion is more likely than continuation
  - Added: price position within recent range (is price near support/resistance?)
  - Added: momentum oscillation detection (are we bouncing?)
  - Added: bias correction — avoid defaulting to LOSS when uncertain
  - Improved: confidence calibration to avoid over-confident wrong calls
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone

try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

SCRIPT_DIR = Path(__file__).parent
STATE_FILE = SCRIPT_DIR / "silver_hawk_state.json"
PATTERNS_FILE = SCRIPT_DIR / "silver_hawk_patterns.json"
API_KEY_FILE = SCRIPT_DIR / ".claude_api_key"
SELF_PATH = Path(__file__)  # path to THIS file — for self-rewriting

# ── Lifecycle stages ─────────────────────────────────────────────
STAGES = [
    {"name": "Newborn",       "min_trades": 0,   "min_accuracy": 0.0,  "emoji": "👶"},
    {"name": "Toddler",       "min_trades": 5,   "min_accuracy": 0.0,  "emoji": "💒"},
    {"name": "Child",         "min_trades": 15,  "min_accuracy": 0.40, "emoji": "💓"},
    {"name": "Teenager",      "min_trades": 30,  "min_accuracy": 0.50, "emoji": "💔"},
    {"name": "Adult",         "min_trades": 50,  "min_accuracy": 0.65, "emoji": "💕"},
    {"name": "Silver Haired", "min_trades": 100, "min_accuracy": 0.80, "emoji": "🧓"},
]

HEALTH_START = 100.0
HEALTH_CORRECT = 5.0    # gain per correct prediction
HEALTH_WRONG = -10.0    # lose per wrong prediction
HEALTH_STARVING = 20.0  # below this = Claude emergency rewrite
CONSECUTIVE_FAIL_LIMIT = 3  # 3 wrong in a row = trigger rewrite


def _load_api_key() -> str | None:
    try:
        if API_KEY_FILE.exists():
            return API_KEY_FILE.read_text("utf-8").strip()
    except Exception:
        pass
    return None


def _load_state() -> dict:
    """Load hawk state — prediction history, health, generation."""
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text("utf-8"))
    except Exception:
        pass
    return {
        "generation": 1,
        "born": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "health": HEALTH_START,
        "total_predictions": 0,
        "correct_predictions": 0,
        "consecutive_wrong": 0,
        "stage": "Newborn",
        "predictions": [],  # last 50 predictions with outcomes
        "rewrites": [],     # history of Claude rewrites
    }


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _load_patterns() -> list:
    """Load learned patterns."""
    try:
        if PATTERNS_FILE.exists():
            data = json.loads(PATTERNS_FILE.read_text("utf-8"))
            return data.get("patterns", [])
    except Exception:
        pass
    return []


def _get_stage(state: dict) -> dict:
    """Determine current lifecycle stage."""
    total = state.get("total_predictions", 0)
    accuracy = state.get("correct_predictions", 0) / max(1, total)
    current = STAGES[0]
    for stage in STAGES:
        if total >= stage["min_trades"] and accuracy >= stage["min_accuracy"]:
            current = stage
    return current


# ═══════════════════════════════════════════════════════════════════
# PATTERN MATCHING — this section is rewritten by Claude when needed
# ═══════════════════════════════════════════════════════════════════

def analyze_candle_pattern(candle: dict, recent_candles: list = None) -> dict:
    """
    Analyze a candle and recent history to identify patterns.
    Returns a dict of detected pattern features.

    Generation 2 improvements:
    - Added range-position analysis (where is price in recent range?)
    - Added momentum oscillation (bouncing off lows/highs?)
    - Added choppiness detection (sideways market = fade breakouts)
    - Added recent bias from prior candles (were last N candles mostly up or down?)
    - Improved wick analysis for rejection signals
    - Added price velocity (rate of change)
    """
    o = candle.get("open", 0)
    h = candle.get("high", 0)
    l = candle.get("low", 0)
    c = candle.get("close", 0)
    v = candle.get("volume", 0)

    rng = h - l if h > l else 0.001
    body = abs(c - o)
    body_ratio = body / rng
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    bullish = c > o

    features = {
        "body_ratio": round(body_ratio, 3),
        "upper_wick_ratio": round(upper_wick / rng, 3),
        "lower_wick_ratio": round(lower_wick / rng, 3),
        "bullish": bullish,
        "bearish": not bullish,
        "range": round(rng, 3),
        "volume": v,
        "close": round(c, 3),
        "open": round(o, 3),
        # Classic single-candle patterns
        "doji": body_ratio < 0.20,
        "strong_body": body_ratio > 0.65,
        "hammer": (lower_wick / rng > 0.55 and body_ratio < 0.35 and upper_wick / rng < 0.15),
        "shooting_star": (upper_wick / rng > 0.55 and body_ratio < 0.35 and lower_wick / rng < 0.15),
        "marubozu": body_ratio > 0.85,
        "spinning_top": body_ratio < 0.35 and upper_wick / rng > 0.25 and lower_wick / rng > 0.25,
        # Wick dominance
        "upper_wick_dominant": upper_wick > body * 2 and upper_wick > lower_wick * 1.5,
        "lower_wick_dominant": lower_wick > body * 2 and lower_wick > upper_wick * 1.5,
    }

    if recent_candles and len(recent_candles) >= 3:
        last3 = recent_candles[-3:]
        last5 = recent_candles[-5:] if len(recent_candles) >= 5 else recent_candles
        last10 = recent_candles[-10:] if len(recent_candles) >= 10 else recent_candles

        closes = [cc.get("close", 0) for cc in last3]
        opens = [cc.get("open", 0) for cc in last3]
        highs = [cc.get("high", 0) for cc in last3]
        lows = [cc.get("low", 0) for cc in last3]
        vols = [cc.get("volume", 0) for cc in last3]

        # ── Trend detection ─────────────────────────────────────────
        if all(closes[i] > closes[i-1] for i in range(1, len(closes))):
            features["trend_up_3"] = True
        elif all(closes[i] < closes[i-1] for i in range(1, len(closes))):
            features["trend_down_3"] = True
        else:
            features["trend_mixed_3"] = True

        # ── Volume trend ─────────────────────────────────────────────
        if all(vols[i] > vols[i-1] for i in range(1, len(vols))):
            features["volume_increasing"] = True
        elif all(vols[i] < vols[i-1] for i in range(1, len(vols))):
            features["volume_decreasing"] = True

        # ── Range expansion/contraction ──────────────────────────────
        ranges_3 = [cc.get("high", 0) - cc.get("low", 0) for cc in last3]
        avg_range_3 = sum(ranges_3) / len(ranges_3) if ranges_3 else 0.001
        if avg_range_3 > 0:
            features["range_vs_avg"] = round(rng / avg_range_3, 2)
            features["range_expansion"] = rng > avg_range_3 * 1.4
            features["range_contraction"] = rng < avg_range_3 * 0.6
            features["inside_bar"] = h <= max(highs) and l >= min(lows)

        # ── Price position within recent range ───────────────────────
        # Where is the current close relative to the high/low of last 10 candles?
        all_highs = [cc.get("high", 0) for cc in last10]
        all_lows = [cc.get("low", 0) for cc in last10]
        period_high = max(all_highs) if all_highs else h
        period_low = min(all_lows) if all_lows else l
        period_rng = period_high - period_low if period_high > period_low else 0.001
        price_position = (c - period_low) / period_rng  # 0=at low, 1=at high
        features["price_position_in_range"] = round(price_position, 3)
        features["near_period_high"] = price_position > 0.80
        features["near_period_low"] = price_position < 0.20
        features["mid_range"] = 0.35 < price_position < 0.65

        # ── Choppiness detection ─────────────────────────────────────
        # Count direction changes in last 5 candles — high count = choppy
        closes5 = [cc.get("close", 0) for cc in last5]
        opens5 = [cc.get("open", 0) for cc in last5]
        directions5 = [1 if closes5[i] > opens5[i] else -1 for i in range(len(closes5))]
        direction_changes = sum(
            1 for i in range(1, len(directions5))
            if directions5[i] != directions5[i-1]
        )
        features["choppiness"] = direction_changes  # 0-4, higher=choppier
        features["choppy_market"] = direction_changes >= 3

        # ── Bullish/bearish bias from recent candles ─────────────────
        bull_count = sum(1 for i in range(len(closes5)) if closes5[i] > opens5[i])
        bear_count = len(closes5) - bull_count
        features["recent_bull_count"] = bull_count
        features["recent_bear_count"] = bear_count
        features["recent_bull_bias"] = bull_count >= 4
        features["recent_bear_bias"] = bear_count >= 4
        features["recent_balanced"] = bull_count == bear_count or abs(bull_count - bear_count) <= 1

        # ── Momentum: price velocity ─────────────────────────────────
        if len(closes5) >= 2:
            price_change_5 = closes5[-1] - closes5[0]
            features["price_velocity_5"] = round(price_change_5, 3)
            features["strong_up_momentum"] = price_change_5 > avg_range_3 * 1.5
            features["strong_down_momentum"] = price_change_5 < -avg_range_3 * 1.5
            features["weak_momentum"] = abs(price_change_5) < avg_range_3 * 0.3

        # ── Engulfing patterns ───────────────────────────────────────
        if len(last3) >= 2:
            prev = last3[-2]
            prev_o = prev.get("open", 0)
            prev_c = prev.get("close", 0)
            prev_bull = prev_c > prev_o
            # Bullish engulfing: prev bearish, current bullish and body engulfs prev body
            if (not prev_bull and bullish
                    and o <= min(prev_o, prev_c)
                    and c >= max(prev_o, prev_c)):
                features["bullish_engulfing"] = True
            # Bearish engulfing: prev bullish, current bearish and body engulfs prev body
            elif (prev_bull and not bullish
                  and o >= max(prev_o, prev_c)
                  and c <= min(prev_o, prev_c)):
                features["bearish_engulfing"] = True

        # ── Three soldiers / three crows ────────────────────────────
        if len(last3) == 3:
            all_bull = all(closes[i] > opens[i] for i in range(3))
            all_bear = all(closes[i] < opens[i] for i in range(3))
            ascending = all(closes[i] > closes[i-1] for i in range(1, 3))
            descending = all(closes[i] < closes[i-1] for i in range(1, 3))
            if all_bull and ascending:
                features["three_soldiers"] = True
            if all_bear and descending:
                features["three_crows"] = True

        # ── Mean reversion signal ────────────────────────────────────
        # In choppy markets: if near range extreme + wick rejection = likely reversal
        if features.get("choppy_market"):
            if features.get("near_period_high") and features.get("upper_wick_dominant"):
                features["mean_reversion_sell_signal"] = True
            if features.get("near_period_low") and features.get("lower_wick_dominant"):
                features["mean_reversion_buy_signal"] = True

    return features


def match_patterns(features: dict, patterns: list) -> list:
    """
    Match current candle features against learned patterns.
    Returns list of matching patterns with scores.

    Generation 2 improvements:
    - Better numeric fuzzy matching with tighter tolerance for key ratios
    - Weighted scoring: more important conditions count more
    - Minimum sample size filter (ignore patterns seen < 3 times)
    - Market context override: in choppy market, reduce confidence of
      trend-continuation patterns
    - Bias correction: if no patterns match well, return UNCERTAIN
      instead of defaulting to LOSS
    """
    matches = []
    is_choppy = features.get("choppy_market", False)
    near_high = features.get("near_period_high", False)
    near_low = features.get("near_period_low", False)

    for pat in patterns:
        conditions = pat.get("conditions", {})
        score = 0.0
        weight_total = 0.0

        if len(conditions) == 0:
            continue

        # Skip patterns with too little evidence
        if pat.get("sample_size", 0) < 3:
            continue

        for key, expected in conditions.items():
            # Weight boolean pattern features more heavily
            weight = 2.0 if isinstance(expected, bool) else 1.0
            weight_total += weight

            actual = features.get(key)
            if actual is None:
                # Missing feature = partial penalty, not full miss
                weight_total -= weight * 0.5
                continue

            if isinstance(expected, bool):
                if actual == expected:
                    score += weight
                # else: no score, full miss
            elif isinstance(expected, (int, float)):
                if abs(expected) < 0.01:
                    # Near-zero: just check if also near zero
                    if abs(actual) < 0.1:
                        score += weight
                else:
                    # Tighter tolerance: within 15% for ratios, 25% for others
                    tol = 0.15 if key.endswith("_ratio") else 0.25
                    rel_diff = abs(actual - expected) / abs(expected)
                    if rel_diff < tol:
                        score += weight
                    elif rel_diff < tol * 2:
                        score += weight * 0.5  # partial credit
            elif isinstance(expected, str):
                if expected == "high" and actual > 0.6:
                    score += weight
                elif expected == "low" and actual < 0.3:
                    score += weight
                elif expected == "mid" and 0.3 <= actual <= 0.6:
                    score += weight

        match_pct = score / weight_total if weight_total > 0 else 0

        if match_pct >= 0.55:  # slightly lower threshold to catch more patterns
            confidence = match_pct * pat.get("reliability", 0.5)

            # Context adjustments:
            outcome = pat.get("outcome", "unknown")
            # In choppy market, reduce confidence for trend-continuation patterns
            if is_choppy and "continuation" in pat.get("name", "").lower():
                confidence *= 0.6
            # If price near extreme and pattern agrees with mean-reversion, boost it
            if near_high and outcome == "LOSS" and features.get("bearish_engulfing"):
                confidence *= 1.2
            if near_low and outcome == "WIN" and features.get("bullish_engulfing"):
                confidence *= 1.2
            # Cap at 0.95
            confidence = min(0.95, confidence)

            matches.append({
                "pattern": pat.get("name", "unknown"),
                "match_pct": round(match_pct, 2),
                "predicted_outcome": outcome,
                "confidence": round(confidence, 2),
                "sample_size": pat.get("sample_size", 0),
            })

    # Sort by confidence descending
    matches.sort(key=lambda m: -m["confidence"])

    # If top matches disagree (WIN vs LOSS) with similar confidence, flag as uncertain
    if len(matches) >= 2:
        top1 = matches[0]
        top2 = matches[1]
        if (top1["predicted_outcome"] != top2["predicted_outcome"]
                and abs(top1["confidence"] - top2["confidence"]) < 0.10):
            # Conflicting signals — reduce confidence of both
            matches[0]["confidence"] = round(matches[0]["confidence"] * 0.7, 2)
            matches[1]["confidence"] = round(matches[1]["confidence"] * 0.7, 2)

    return matches


# ═══════════════════════════════════════════════════════════════════
# PUBLIC API — called by the daemon
# ═══════════════════════════════════════════════════════════════════

def predict_trade(
    direction: str, uhv: float, candle: dict,
    recent_candles: list = None, entry_slippage: float = 0,
    log_fn=None
) -> dict:
    """
    Make a prediction for a trade BEFORE it fires.

    Returns:
    {
        "prediction": "WIN" | "LOSS" | "UNCERTAIN",
        "confidence": 0.0-1.0,
        "reason": "...",
        "stage": "Newborn",
        "health": 85.0,
        "message_urdu": "Baba kehta hai...",
    }
    """
    state = _load_state()
    stage = _get_stage(state)
    state["stage"] = stage["name"]
    patterns = _load_patterns()
    features = analyze_candle_pattern(candle, recent_candles)

    # If we're a newborn with no patterns, use Claude for initial prediction
    if state["total_predictions"] < 5 or not patterns:
        prediction = _claude_predict(direction, uhv, candle, features, state, log_fn)
    else:
        # Match against learned patterns
        matches = match_patterns(features, patterns)
        if matches and matches[0]["confidence"] > 0.35:
            best = matches[0]
            prediction = {
                "prediction": best["predicted_outcome"],
                "confidence": best["confidence"],
                "reason": f"Pattern '{best['pattern']}' matched at {best['match_pct']:.0%} "
                          f"(n={best['sample_size']})",
                "matched_pattern": best["pattern"],
            }
        else:
            # No strong pattern match — ask Claude
            prediction = _claude_predict(direction, uhv, candle, features, state, log_fn)

    # Add lifecycle info
    prediction["stage"] = stage["name"]
    prediction["stage_emoji"] = stage["emoji"]
    prediction["health"] = state["health"]
    prediction["generation"] = state.get("generation", 1)
    prediction["total_predictions"] = state["total_predictions"]

    accuracy = state["correct_predictions"] / max(1, state["total_predictions"])
    prediction["lifetime_accuracy"] = round(accuracy * 100, 1)

    # Build the Urdu message
    prediction["message_urdu"] = _build_urdu_message(prediction, state)

    # Save this prediction (outcome TBD)
    pred_record = {
        "t": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "direction": direction,
        "uhv": uhv,
        "prediction": prediction["prediction"],
        "confidence": prediction["confidence"],
        "reason": prediction["reason"],
        "outcome": None,  # filled in after trade closes
        "features": {
            # Store key features for post-mortem analysis
            k: features[k] for k in [
                "body_ratio", "bullish", "doji", "hammer", "shooting_star",
                "choppy_market", "price_position_in_range", "near_period_high",
                "near_period_low", "range_expansion", "bullish_engulfing",
                "bearish_engulfing", "mean_reversion_buy_signal",
                "mean_reversion_sell_signal",
            ] if k in features
        },
    }
    state["predictions"] = state.get("predictions", [])[-49:]
    state["predictions"].append(pred_record)
    _save_state(state)

    if log_fn:
        log_fn(f"SILVER_HAWK [{stage['name']}] gen={state.get('generation',1)} "
               f"health={state['health']:.0f}: "
               f"{prediction['prediction']} ({prediction['confidence']:.0%}) — {prediction['reason']}")

    return prediction


def record_outcome(won: bool, pnl: float, log_fn=None):
    """
    Called after a trade closes. Records whether the prediction was correct.
    Triggers self-correction if needed.
    """
    state = _load_state()
    predictions = state.get("predictions", [])

    # Find the most recent prediction without an outcome
    for pred in reversed(predictions):
        if pred.get("outcome") is None:
            pred["outcome"] = "WIN" if won else "LOSS"
            pred["actual_pnl"] = pnl
            correct = (pred["prediction"] == pred["outcome"])
            pred["correct"] = correct

            state["total_predictions"] = state.get("total_predictions", 0) + 1
            if correct:
                state["correct_predictions"] = state.get("correct_predictions", 0) + 1
                state["health"] = min(100, state.get("health", 50) + HEALTH_CORRECT)
                state["consecutive_wrong"] = 0
                if log_fn:
                    log_fn(f"SILVER_HAWK: CORRECT! predicted {pred['prediction']}, "
                           f"was {pred['outcome']}. Health +{HEALTH_CORRECT} = {state['health']:.0f}")
            else:
                state["health"] = max(0, state.get("health", 50) + HEALTH_WRONG)
                state["consecutive_wrong"] = state.get("consecutive_wrong", 0) + 1
                if log_fn:
                    log_fn(f"SILVER_HAWK: WRONG! predicted {pred['prediction']}, "
                           f"was {pred['outcome']}. Health {HEALTH_WRONG} = {state['health']:.0f}  "
                           f"(consecutive wrong: {state['consecutive_wrong']})")

            break

    # Update lifecycle stage
    stage = _get_stage(state)
    state["stage"] = stage["name"]
    state["predictions"] = predictions
    _save_state(state)

    # Check if self-correction is needed
    if state.get("consecutive_wrong", 0) >= CONSECUTIVE_FAIL_LIMIT:
        if log_fn:
            log_fn(f"SILVER_HAWK: {CONSECUTIVE_FAIL_LIMIT} consecutive wrong predictions! "
                   f"Triggering Claude to rewrite pattern matching...")
        _trigger_self_correction(state, log_fn)

    if state.get("health", 0) <= HEALTH_STARVING:
        if log_fn:
            log_fn(f"SILVER_HAWK: STARVING! Health={state['health']:.0f}. "
                   f"Claude must feed the hawk...")
        _trigger_self_correction(state, log_fn)


def _claude_predict(direction, uhv, candle, features, state, log_fn=None) -> dict:
    """Ask Claude to make a prediction based on candle analysis."""
    api_key = _load_api_key()
    if not api_key or not CLAUDE_AVAILABLE:
        return {"prediction": "UNCERTAIN", "confidence": 0.0, "reason": "No Claude API"}

    accuracy = state.get("correct_predictions", 0) / max(1, state.get("total_predictions", 1))
    recent_preds = state.get("predictions", [])[-5:]
    recent_text = "\n".join([
        f"  {p.get('direction','?')} @ {p.get('uhv','?')}: predicted {p.get('prediction','?')}, "
        f"actual {p.get('outcome','pending')}, correct={p.get('correct','?')}"
        for p in recent_preds
    ]) if recent_preds else "No prior predictions."

    # Build a focused feature summary — avoid noise
    key_features = {
        k: v for k, v in features.items()
        if v is not False and v != 0 and v is not None
    }
    feature_text = "\n".join([f"  {k}: {v}" for k, v in key_features.items()])

    # Note our generation's self-awareness about bias
    bias_note = ""
    if state.get("consecutive_wrong", 0) >= 2:
        bias_note = (
            "\nIMPORTANT: My recent predictions have been wrong. "
            "I may have been biased toward LOSS. "
            "Consider the features carefully and don't default to LOSS."
        )

    prompt = f"""You are the Silver Haired Hawk — a trade prediction engine (Generation 2).
Analyze this trade setup and predict: will it WIN or LOSE?

TRADE: {direction.upper()} XAUUSD @ UHV {uhv}

KEY CANDLE FEATURES:
{feature_text}

MY RECENT PREDICTIONS (accuracy: {accuracy:.0%}):
{recent_text}
{bias_note}

Based on candle structure, market context, and price position, predict the most likely outcome.
Key considerations:
- If market is choppy (price bouncing), fade the move (it likely reverses)
- If near period high with rejection wick, likely LOSS for longs
- If near period low with support wick, likely WIN for longs
- Strong body + momentum in direction = continuation (WIN for direction)
- Doji / spinning top = indecision = harder to predict

Respond in EXACTLY this format:
PREDICTION: WIN or LOSS | CONFIDENCE: 0.0 to 1.0 | REASON: one sentence"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        if log_fn:
            log_fn(f"SILVER_HAWK_CLAUDE: {text}")

        prediction = "UNCERTAIN"
        confidence = 0.5
        reason = text

        if "PREDICTION:" in text:
            for part in text.split("|"):
                p = part.strip()
                if p.startswith("PREDICTION:"):
                    val = p.replace("PREDICTION:", "").strip().upper()
                    prediction = "WIN" if "WIN" in val else "LOSS"
                elif p.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(p.replace("CONFIDENCE:", "").strip())
                    except ValueError:
                        pass
                elif p.startswith("REASON:"):
                    reason = p.replace("REASON:", "").strip()

        return {"prediction": prediction, "confidence": confidence, "reason": reason}

    except Exception as e:
        if log_fn:
            log_fn(f"SILVER_HAWK_ERR: {e}")
        return {"prediction": "UNCERTAIN", "confidence": 0.0, "reason": str(e)}


def _build_urdu_message(prediction: dict, state: dict) -> str:
    """Build the Urdu prediction message for WhatsApp."""
    stage = prediction.get("stage", "Newborn")
    pred = prediction.get("prediction", "UNCERTAIN")
    conf = prediction.get("confidence", 0)
    acc = prediction.get("lifetime_accuracy", 0)
    health = prediction.get("health", 0)
    gen = prediction.get("generation", 1)

    if stage == "Newborn":
        title = "Abhi to seekh raha hoon"
    elif stage == "Apprentice":
        title = "Patterns dekhna shuru kar diya"
    elif stage == "Journeyman":
        title = "Predictions banane laga hoon"
    elif stage == "Adept":
        title = "Confidence barh rahi hai"
    else:
        title = "Master predictor"

    pred_label = "WIN" if pred == "WIN" else ("LOSS" if pred == "LOSS" else "UNCERTAIN")
    return (
        f"Silver Hawk Gen{gen} ({stage})\n"
        f"{title}\n"
        f"Prediction: {pred_label} ({conf:.0%})\n"
        f"Lifetime accuracy: {acc:.0%} | Health: {health}"
    )


def learn_from_candles(candles: list, log_fn=None) -> int:
    """Numerical OHLCV pattern learner. Stub — real impl was lost in file truncation.

    Returns count of patterns learned. Stubbed to no-op so the learner process
    stays alive; combine with visual_learn_from_screenshot for actual learning.
    """
    try:
        if not candles or len(candles) < 3:
            return 0
        state = _load_state()
        state["candles_seen"] = state.get("candles_seen", 0) + len(candles)
        _save_state(state)
        return 0
    except Exception as e:
        if log_fn:
            log_fn(f"LEARN_CANDLES_ERR: {e}")
        return 0


def get_status() -> str:
    """One-line status string for periodic logging."""
    try:
        state = _load_state()
        stage = _get_stage(state).get("name", "Newborn")
        gen = state.get("generation", 1)
        seen = state.get("candles_seen", 0)
        wins = state.get("wins", 0)
        losses = state.get("losses", 0)
        total = wins + losses
        acc = (wins / total) if total else 0.0
        return f"Silver Hawk Gen{gen} ({stage}) — candles seen: {seen}, W:{wins} L:{losses} acc:{acc:.0%}"
    except Exception as e:
        return f"Silver Hawk status unavailable: {e}"


def visual_learn_from_screenshot(screenshot_bytes, log_fn=None) -> int:
    """Visual chart pattern learner via Claude vision. Stub — real impl was lost.

    Returns count of patterns extracted. The original called the Anthropic API
    with the screenshot; this stub no-ops so the daemon stays alive.
    """
    return 0