"""
Humanity Assistant V3.5 - Assistant Kontrollü AL Sürümü

Amaç
-----
H/TRY'yi 60 saniyede bir izler. Coin Radar, AI Coin Assistant ve Humanity
Control deneyimlerinden alınan en faydalı parçaları tek coin için birleştirir:

- WAIT/BEKLE sessizdir.
- Nihai AL kararının sahibi Assistant'tır; eski SignalEngine yalnızca teyit katmanıdır.
- Erken hareketi 1m / 3m / 5m / 15m fiyat ivmesinden yakalar.
- Hacim tek başına yeterli değildir; momentum eşleşmesi aranır.
- Hacim ve momentum güçlenmesi ayrı ayrı izlenir.
- EMA / RSI / MACD ana trend ve teyit katmanıdır.
- Aşırı ısınmış hareketleri cezalandırır; geç giriş riskini işaretler.
- Aynı uyarıyı tekrar tekrar göndermez; sadece seviye yükselmesi veya anlamlı\n  yeni güçlenmede haber verir.\n- BUY/AL tekrar filtresi TelegramNotifier hafızasından ayrılmıştır.\n- Eşikler değiştirilmeden her tarama gözlem günlüğüne kaydedilir.
- Durumu JSON'da tutar, yeniden deploy/restart sonrası hafızasını korur.

Not: Bu dosya mevcut proje modüllerini değiştirmez. HumanityTracker,
TechnicalAnalysis, SignalEngine ve TelegramNotifier ile uyumludur.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

from analysis.technical_analysis import TechnicalAnalysis
from market.humanity_tracker import HumanityTracker
from strategy.signal_engine import SignalEngine
from telegram.telegram_notifier import TelegramNotifier


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# -----------------------------------------------------------------------------
# Telegram / Railway ayarları
# -----------------------------------------------------------------------------
# Gizli bilgileri GitHub koduna yazmıyoruz. Railway > Variables bölümünde:
#   TELEGRAM_BOT_TOKEN = BotFather'dan alınan bot tokenı
#   TELEGRAM_CHAT_ID   = Humanity Control sohbet / kanal ID'si
# tanımlanmalıdır. TelegramNotifier da aynı değişken isimlerini kullanır.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def validate_telegram_config():
    """Telegram ayarlarını başlangıçta açıkça doğrula; gizli değerleri loglama."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")

    if missing:
        raise RuntimeError(
            "Telegram ayarları eksik: "
            + ", ".join(missing)
            + ". Railway > Variables bölümüne ekleyin."
        )

    logging.info("Telegram ayarları hazır (token ve chat ID bulundu).")


SCAN_INTERVAL_SECONDS = 60
TECH_REFRESH_SECONDS = 15 * 60  # 200 adet 1h mum 15 dakikada bir yenilenir
STATE_FILE = "humanity_assistant_state.json"
# ÖNEMLİ: telegram_notifier.py de last_signal.json kullanıyor.
# Aynı dosyanın iki ayrı tekrar filtresi tarafından kullanılması BUY mesajını
# her dakika yeniden "yeni" gibi gösterebiliyordu. Bu nedenle main kendi
# AL geçiş hafızasını tamamen ayrı dosyada tutar.
BUY_STATE_FILE = "humanity_buy_state.json"

# Her 60 sn taramanın hareket öncesi verisini saklayan gözlem günlüğü.
OBSERVATION_FILE = "humanity_observation_log.jsonl"

# Yaklaşık 4 saatlik 1 dakikalık snapshot hafızası.
MAX_HISTORY = 240

# Mesaj eşikleri. İlk günlerde bunları değiştirmeden veri biriktirmek daha doğru.
EARLY_SCORE = 55
STRONG_SCORE = 70
VERY_STRONG_SCORE = 82

# Mikro Aday mevcut 55/70/82 eşiklerini DEĞİŞTİRMEZ.
# Amaç: güçlü adaydan önce kısa vadeli uyanışı haber vermek.
MICRO_M1_MIN = 0.30
MICRO_M3_MIN = 0.20
MICRO_STAIR_TOTAL_MIN = 0.25

# Aynı kategoride gereksiz Telegram tekrarını engeller.
ALERT_COOLDOWN_SECONDS = 12 * 60
VOLUME_RENOTIFY_MULTIPLIER = 1.35
MOMENTUM_RENOTIFY_STEP = 0.80


# -----------------------------------------------------------------------------
# Genel yardımcılar
# -----------------------------------------------------------------------------

def _to_float(value, default=None):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", ".").strip()
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(path, default=None):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        logging.exception("Durum dosyası okunamadı: %s", path)
    if default is None:
        return {}
    return default


def _save_json(path, data):
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        logging.exception("Durum dosyası yazılamadı: %s", path)
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def _positive_text(value):
    text = str(value or "").strip().lower()
    words = ("bull", "up", "yuk", "pozitif", "güçlü", "artan", "buy", "al")
    return any(word in text for word in words)


def _negative_text(value):
    text = str(value or "").strip().lower()
    words = ("bear", "down", "aşa", "negatif", "zayıf", "düş", "sell", "sat")
    return any(word in text for word in words)


def _pct_change(current, old):
    if current is None or old in (None, 0):
        return None
    return ((current / old) - 1.0) * 100.0


def _fmt_pct(value):
    return "—" if value is None else f"%{value:+.2f}"


def _fmt_num(value, digits=2):
    return "—" if value is None else f"{value:.{digits}f}"


def _now_ts():
    return int(time.time())


def _append_observation(record):
    """Her taramanın kısa vadeli hareket verisini JSONL olarak sakla."""
    try:
        with open(OBSERVATION_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logging.exception("Gözlem günlüğü yazılamadı.")


# -----------------------------------------------------------------------------
# AL mesaj kontrolü: WAIT/SAT sessiz, yalnızca yeni AL Telegram'a gider.
# -----------------------------------------------------------------------------

def should_send_assistant_buy(analysis):
    """
    Nihai AL kararını Assistant verir.

    Şart:
      - level == AL_ONCESI_GUCLU
      - yani mevcut kurala göre Assistant >= 82,
        en az 5 teyit ve pozitif momentum.

    Tekrar koruması:
      - Aynı güçlü hareket boyunca yalnızca 1 AL gönderilir.
      - Sistem ancak 10 ardışık tarama boyunca ERKEN_ADAY altına dönerse
        yeni bir AL döngüsüne hazırlanır.
    """
    state = _load_json(BUY_STATE_FILE, {})
    active = bool(state.get("assistant_buy_active", False))
    calm_streak = int(state.get("calm_streak", 0) or 0)

    level = analysis.get("level", "IZLEME")
    rank = LEVEL_RANK.get(level, 0)
    early_rank = LEVEL_RANK.get("ERKEN_ADAY", 2)
    is_buy = level == "AL_ONCESI_GUCLU"

    if is_buy:
        should_send = not active
        _save_json(
            BUY_STATE_FILE,
            {
                "assistant_buy_active": True,
                "calm_streak": 0,
                "last_level": level,
                "last_score": analysis.get("score"),
                "last_buy_ts": _now_ts() if should_send else state.get("last_buy_ts"),
                "updated_at": _now_ts(),
            },
        )
        return should_send

    # Güçlü hareketin kısa süreli dalgalanmasında AL kilidini hemen açma.
    if rank < early_rank:
        calm_streak += 1
    else:
        calm_streak = 0

    if active and calm_streak >= 10:
        active = False

    _save_json(
        BUY_STATE_FILE,
        {
            "assistant_buy_active": active,
            "calm_streak": calm_streak,
            "last_level": level,
            "last_score": analysis.get("score"),
            "last_buy_ts": state.get("last_buy_ts"),
            "updated_at": _now_ts(),
        },
    )
    return False


def format_assistant_buy_message(market_data, technical_result, signal_result, analysis):
    """Assistant'ın nihai AL mesajı."""
    m = analysis.get("momentum", {}) or {}
    engine_signal = str(signal_result.get("signal") or "—").upper()
    engine_score = signal_result.get("score")

    lines = [
        "🟢 H/TRY AL",
        f"💰 Fiyat: {_fmt_num(market_data.get('price'))} TRY",
        (
            "⚡ Momentum: "
            f"1dk {_fmt_pct(m.get('m1'))} • "
            f"3dk {_fmt_pct(m.get('m3'))} • "
            f"5dk {_fmt_pct(m.get('m5'))}"
        ),
        f"📊 Hacim: {_fmt_num(analysis.get('volume_ratio'))}x",
    ]

    if analysis.get("micro_staircase"):
        lines.append(
            f"🪜 Mikro basamak ✅ • 4 taramada %{analysis.get('micro_stair_move', 0):+.2f}"
        )

    rsi = analysis.get("rsi")
    if rsi is not None:
        lines.append(f"📉 RSI: {rsi:.1f}")

    lines.append(
        f"🎯 Assistant: {analysis.get('score', 0):.0f}/100"
        f" • Teyit: {analysis.get('confirmation_count', 0)}"
    )
    lines.append(
        f"🧠 Eski motor teyidi: {engine_signal}"
        + (f" • {engine_score}/100" if engine_score is not None else "")
    )
    lines.append("✅ Nihai karar: AL — Assistant güçlü giriş şartlarını tamamladı.")

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# 60 saniyelik snapshot geçmişi
# -----------------------------------------------------------------------------

def _append_history(state, market_data, technical_result):
    history = state.get("history") or []

    volume = technical_result.get("volume", {}) or {}
    ema = technical_result.get("ema", {}) or {}

    snapshot = {
        "ts": _now_ts(),
        "price": _to_float((market_data or {}).get("price")),
        "bid": _to_float((market_data or {}).get("bid")),
        "ask": _to_float((market_data or {}).get("ask")),
        "high_24h": _to_float((market_data or {}).get("high_24h")),
        "change_24h": _to_float((market_data or {}).get("change_24h")),
        "rsi": _to_float(technical_result.get("rsi")),
        "macd_hist": _to_float(technical_result.get("macd_histogram")),
        "macd_trend": technical_result.get("macd_trend"),
        "ema_trend": ema.get("trend"),
        "volume_ratio": _to_float(volume.get("volume_ratio")),
        "volume_status": volume.get("status"),
    }

    # Fiyat yoksa bozuk snapshot eklemeyelim.
    if snapshot["price"] is not None:
        history.append(snapshot)

    # Süreden bağımsız emniyet: hem adet hem yaş temizliği.
    cutoff = _now_ts() - (6 * 60 * 60)
    history = [h for h in history if h.get("ts", 0) >= cutoff]
    history = history[-MAX_HISTORY:]

    state["history"] = history
    return state, snapshot


def _snapshot_ago(history, minutes):
    if not history:
        return None

    target = _now_ts() - minutes * 60
    eligible = [h for h in history if h.get("ts", 0) <= target]
    if eligible:
        return eligible[-1]

    # İstenen süre henüz dolmadıysa yanlış yüzde üretmeyelim.
    return None


def _price_momentum(history, current_price):
    result = {}
    for minute in (1, 3, 5, 15, 30, 60):
        old = _snapshot_ago(history, minute)
        result[f"m{minute}"] = _pct_change(
            current_price,
            _to_float((old or {}).get("price")),
        )
    return result


def _micro_staircase(history):
    """
    Son 4 adet yaklaşık 60 sn snapshot içinde mikro basamak arar.

    Amaç mum formasyonu taklidi yapmak değil; fiyatın birkaç tarama boyunca
    yukarı doğru küçük adımlar üretip üretmediğini görmek.
    """
    if len(history) < 4:
        return False, 0.0, 0

    prices = [_to_float(x.get("price")) for x in history[-4:]]
    if any(p is None or p <= 0 for p in prices):
        return False, 0.0, 0

    steps = []
    for old, new in zip(prices, prices[1:]):
        steps.append(((new / old) - 1.0) * 100.0)

    positive_steps = sum(1 for step in steps if step >= 0.03)
    deep_pullback = any(step <= -0.25 for step in steps)
    total_move = ((prices[-1] / prices[0]) - 1.0) * 100.0

    staircase = (
        positive_steps >= 2
        and total_move >= MICRO_STAIR_TOTAL_MIN
        and not deep_pullback
    )
    return staircase, total_move, positive_steps


# -----------------------------------------------------------------------------
# Tek coin Assistant skoru
# -----------------------------------------------------------------------------

def build_assistant_analysis(state, market_data, technical_result, signal_result):
    history = state.get("history") or []
    current = history[-1] if history else {}
    previous = history[-2] if len(history) >= 2 else {}

    price = _to_float(current.get("price"))
    volume_ratio = _to_float(current.get("volume_ratio"))
    prev_volume = _to_float(previous.get("volume_ratio"))
    rsi = _to_float(current.get("rsi"))
    prev_rsi = _to_float(previous.get("rsi"))
    macd_hist = _to_float(current.get("macd_hist"))
    prev_macd_hist = _to_float(previous.get("macd_hist"))
    high_24h = _to_float(current.get("high_24h"))
    bid = _to_float(current.get("bid"))
    ask = _to_float(current.get("ask"))

    momentum = _price_momentum(history, price)
    m1 = momentum.get("m1")
    m3 = momentum.get("m3")
    m5 = momentum.get("m5")
    m15 = momentum.get("m15")

    micro_staircase, micro_stair_move, micro_positive_steps = _micro_staircase(history)

    ema_positive = _positive_text(current.get("ema_trend"))
    macd_positive = _positive_text(current.get("macd_trend")) or (
        macd_hist is not None and macd_hist > 0
    )
    macd_strengthening = (
        macd_hist is not None
        and prev_macd_hist is not None
        and macd_hist > prev_macd_hist
    )
    rsi_strengthening = (
        rsi is not None and prev_rsi is not None and rsi >= prev_rsi + 0.8
    )
    rsi_healthy = rsi is not None and 48 <= rsi <= 70

    volume_strengthening = (
        volume_ratio is not None
        and prev_volume not in (None, 0)
        and volume_ratio >= prev_volume * 1.15
    )

    # 3 dakikalık momentum ivmesi: son 1 dk, önceki ortalamadan güçlü mü?
    acceleration = None
    if m1 is not None and m3 is not None:
        older_two_min_avg = (m3 - m1) / 2.0
        acceleration = m1 - older_two_min_avg

    near_high_pct = None
    if price is not None and high_24h not in (None, 0):
        near_high_pct = ((price / high_24h) - 1.0) * 100.0

    spread_pct = None
    if bid not in (None, 0) and ask is not None:
        spread_pct = ((ask - bid) / bid) * 100.0

    score = 0.0
    reasons = []
    warnings = []

    # 1) Momentum - en önemli katman.
    if m1 is not None:
        if m1 >= 0.60:
            score += 13
            reasons.append("1 dk momentum güçlü")
        elif m1 >= 0.25:
            score += 8
            reasons.append("1 dk fiyat hareketleniyor")
        elif m1 <= -0.50:
            score -= 10
            warnings.append("1 dk momentum negatif")

    if m3 is not None:
        if m3 >= 1.50:
            score += 18
            reasons.append("3 dk momentum güçlü")
        elif m3 >= 0.70:
            score += 12
            reasons.append("3 dk momentum pozitif")
        elif m3 <= 0:
            score -= 8

    if m5 is not None:
        if 1.20 <= m5 <= 4.50:
            score += 9
            reasons.append("5 dk hareket sağlıklı")
        elif m5 > 6.0:
            score -= 10
            warnings.append("5 dk hareket fazla ısınmış")

    if acceleration is not None:
        if acceleration >= 0.30:
            score += 9
            reasons.append("momentum güçleniyor")
        elif acceleration <= -0.35:
            score -= 8
            warnings.append("momentum ivmesi zayıflıyor")

    # 2) Hacim - tek başına sinyal değildir.
    if volume_ratio is not None:
        if 1.5 <= volume_ratio < 3:
            score += 8
            reasons.append("hacim destekliyor")
        elif 3 <= volume_ratio < 8:
            score += 12
            reasons.append("hacim güçlü")
        elif volume_ratio >= 8:
            score += 8
            reasons.append("hacim çok güçlü")

    if volume_strengthening:
        score += 10
        reasons.append("hacim güçleniyor")

    # Coin Radar'dan öğrenilen kritik filtre: dev hacim + zayıf momentum = alarm değil.
    volume_without_momentum = (
        volume_ratio is not None
        and volume_ratio >= 8
        and (m3 is None or m3 < 0.70)
    )
    if volume_without_momentum:
        score -= 18
        warnings.append("yüksek hacim var ama momentum teyidi zayıf")

    # 3) Teknik teyit.
    if ema_positive:
        score += 8
        reasons.append("EMA trendi pozitif")
    elif _negative_text(current.get("ema_trend")):
        score -= 8

    if macd_positive:
        score += 8
        reasons.append("MACD pozitif")
    if macd_strengthening:
        score += 5
        reasons.append("MACD güçleniyor")

    if rsi_healthy:
        score += 7
        reasons.append("RSI sağlıklı bölgede")
    elif rsi is not None and rsi >= 75:
        score -= 10
        warnings.append("RSI aşırı ısınmış")
    elif rsi is not None and rsi < 40:
        score -= 5

    if rsi_strengthening and rsi is not None and rsi < 72:
        score += 4
        reasons.append("RSI güçleniyor")

    # 4) Giriş kalitesi / geç kalma riski.
    if near_high_pct is not None:
        if -3.0 <= near_high_pct <= -0.30:
            score += 4
        elif near_high_pct > -0.20 and m5 is not None and m5 > 3.0:
            score -= 8
            warnings.append("24s zirveye çok yakın, geç giriş riski")

    if m15 is not None and m15 > 9.0:
        score -= 12
        warnings.append("15 dk hareket çok hızlı, geç kalma riski")

    if spread_pct is not None and spread_pct > 0.80:
        score -= 8
        warnings.append("alış-satış makası geniş")

    # Mevcut Humanity karar motoru yardımcı teyit olarak kullanılır, patron değildir.
    engine_score = _to_float(signal_result.get("score"), 50.0) or 50.0
    if engine_score >= 70:
        score += 6
    elif engine_score <= 30:
        score -= 6

    score = max(0.0, min(100.0, score))

    enough_history = m3 is not None
    positive_momentum = (
        (m1 is not None and m1 >= 0.20)
        or (m3 is not None and m3 >= 0.60)
    )
    confirmation_count = sum(
        [
            bool(positive_momentum),
            bool(volume_strengthening or (volume_ratio is not None and volume_ratio >= 1.5)),
            bool(ema_positive),
            bool(macd_positive),
            bool(macd_strengthening),
            bool(rsi_healthy),
        ]
    )

    # Mikro Aday: skordan bağımsız, çok erken momentum uyanışı.
    # Hacim bonus/teyittir; zorunlu değildir.
    micro_direct = (
        m1 is not None and m3 is not None
        and m1 >= MICRO_M1_MIN
        and m3 >= MICRO_M3_MIN
    )
    micro_stair_trigger = (
        micro_staircase
        and m1 is not None and m3 is not None
        and m1 >= 0.15
        and m3 >= 0.25
    )
    micro_technical_support = (
        ema_positive
        or macd_positive
        or rsi_healthy
        or engine_score >= 70
    )
    micro_candidate = (
        enough_history
        and not volume_without_momentum
        and micro_technical_support
        and (micro_direct or micro_stair_trigger)
    )

    if micro_candidate:
        if micro_staircase:
            reasons.append("mikro basamak oluşuyor")
        reasons.append("kısa momentum uyanıyor")

    # Mevcut 55/70/82 eşikleri aynen korunur.
    if not enough_history or volume_without_momentum:
        level = "IZLEME"
    elif score >= VERY_STRONG_SCORE and confirmation_count >= 5 and positive_momentum:
        level = "AL_ONCESI_GUCLU"
    elif score >= STRONG_SCORE and confirmation_count >= 4 and positive_momentum:
        level = "GUCLENEN_ADAY"
    elif score >= EARLY_SCORE and confirmation_count >= 3 and positive_momentum:
        level = "ERKEN_ADAY"
    elif micro_candidate:
        level = "MIKRO_ADAY"
    else:
        level = "IZLEME"

    # Giriş kalitesi: ne kadar güçlü + ne kadar az geç kalmış.
    entry_quality = score
    if m15 is not None and m15 > 7:
        entry_quality -= 10
    if rsi is not None and rsi > 72:
        entry_quality -= 8
    if near_high_pct is not None and near_high_pct > -0.20:
        entry_quality -= 5
    entry_quality = max(0.0, min(100.0, entry_quality))

    return {
        "level": level,
        "score": round(score, 1),
        "entry_quality": round(entry_quality, 1),
        "momentum": momentum,
        "acceleration": acceleration,
        "micro_candidate": micro_candidate,
        "micro_staircase": micro_staircase,
        "micro_stair_move": round(micro_stair_move, 3),
        "micro_positive_steps": micro_positive_steps,
        "volume_ratio": volume_ratio,
        "prev_volume_ratio": prev_volume,
        "volume_strengthening": volume_strengthening,
        "rsi": rsi,
        "prev_rsi": prev_rsi,
        "rsi_strengthening": rsi_strengthening,
        "macd_strengthening": macd_strengthening,
        "ema_positive": ema_positive,
        "macd_positive": macd_positive,
        "near_high_pct": near_high_pct,
        "spread_pct": spread_pct,
        "reasons": reasons,
        "warnings": warnings,
        "confirmation_count": confirmation_count,
        "engine_score": engine_score,
    }


# -----------------------------------------------------------------------------
# Akıllı Telegram mesajı ve spam kontrolü
# -----------------------------------------------------------------------------

LEVEL_RANK = {
    "IZLEME": 0,
    "MIKRO_ADAY": 1,
    "ERKEN_ADAY": 2,
    "GUCLENEN_ADAY": 3,
    "AL_ONCESI_GUCLU": 4,
}

LEVEL_TITLE = {
    "MIKRO_ADAY": "🔎 H/TRY MİKRO ADAY",
    "ERKEN_ADAY": "👀 H/TRY ERKEN ADAY",
    "GUCLENEN_ADAY": "🚀 H/TRY GÜÇLENEN ADAY",
    "AL_ONCESI_GUCLU": "🟢 H/TRY AL",
}


def _should_send_assistant_alert(state, analysis):
    level = analysis["level"]
    if level == "IZLEME":
        return False, None

    last_level = state.get("last_alert_level", "IZLEME")
    last_ts = int(state.get("last_alert_ts") or 0)
    last_volume = _to_float(state.get("last_alert_volume"))
    last_m3 = _to_float(state.get("last_alert_m3"))

    current_rank = LEVEL_RANK.get(level, 0)
    last_rank = LEVEL_RANK.get(last_level, 0)

    # En değerli bildirim: kategori yükselmesi.
    if current_rank > last_rank:
        return True, "LEVEL_UP"

    elapsed = _now_ts() - last_ts
    m3 = analysis["momentum"].get("m3")
    volume = analysis.get("volume_ratio")

    meaningful_volume = (
        analysis.get("volume_strengthening")
        and volume is not None
        and (
            last_volume is None
            or volume >= last_volume * VOLUME_RENOTIFY_MULTIPLIER
        )
    )

    meaningful_momentum = (
        m3 is not None
        and last_m3 is not None
        and m3 >= last_m3 + MOMENTUM_RENOTIFY_STEP
    )

    # Aynı seviyede ancak cooldown sonrası belirgin yeni güçlenme varsa tekrar haber ver.
    if elapsed >= ALERT_COOLDOWN_SECONDS and (meaningful_volume or meaningful_momentum):
        return True, "STRENGTHENING"

    return False, None


def _build_assistant_message(market_data, analysis, reason):
    title = LEVEL_TITLE.get(analysis["level"], "H/TRY TAKİP")
    price = _to_float((market_data or {}).get("price"))
    m = analysis["momentum"]

    lines = [title]
    if price is not None:
        lines.append(f"💰 Fiyat: {price:g} TRY")

    lines.append(
        "⚡ Momentum: "
        f"1dk {_fmt_pct(m.get('m1'))} • "
        f"3dk {_fmt_pct(m.get('m3'))} • "
        f"5dk {_fmt_pct(m.get('m5'))}"
    )

    volume = analysis.get("volume_ratio")
    prev_volume = analysis.get("prev_volume_ratio")
    if volume is not None:
        if analysis.get("volume_strengthening") and prev_volume is not None:
            lines.append(f"📈 Hacim güçleniyor: {prev_volume:.2f}x → {volume:.2f}x")
        else:
            lines.append(f"📊 Hacim: {volume:.2f}x")

    if analysis.get("micro_staircase"):
        lines.append(
            f"🪜 Mikro basamak ✅ • 4 taramada %{analysis.get('micro_stair_move', 0):+.2f}"
        )

    if analysis.get("acceleration") is not None and analysis["acceleration"] >= 0.30:
        lines.append("⚡ Momentum güçleniyor")
    elif analysis.get("micro_candidate"):
        lines.append("⚡ Kısa momentum uyanıyor")

    rsi = analysis.get("rsi")
    prev_rsi = analysis.get("prev_rsi")
    if rsi is not None:
        if analysis.get("rsi_strengthening") and prev_rsi is not None:
            lines.append(f"📶 RSI: {prev_rsi:.1f} → {rsi:.1f}")
        else:
            lines.append(f"📶 RSI: {rsi:.1f}")

    teyit = []
    if analysis.get("ema_positive"):
        teyit.append("EMA ✅")
    if analysis.get("macd_positive"):
        teyit.append("MACD ✅")
    if teyit:
        lines.append(" • ".join(teyit))

    lines.append(
        f"🎯 Assistant: {analysis['score']:.0f}/100 • "
        f"Giriş Kalitesi: {analysis['entry_quality']:.0f}/100"
    )

    if analysis.get("warnings"):
        lines.append("⚠️ " + " • ".join(analysis["warnings"][:2]))

    if analysis["level"] == "MIKRO_ADAY":
        lines.append("ℹ️ Çok erken takip — AL değil, hareket uyanışı.")
    elif reason == "LEVEL_UP":
        lines.append("ℹ️ Seviye yükseldi — henüz nihai AL değil.")
    else:
        lines.append("ℹ️ Aday güçlenmeye devam ediyor — henüz nihai AL değil.")

    return "\n".join(lines)


def process_assistant_alert(state, market_data, analysis, telegram_notifier):
    should_send, reason = _should_send_assistant_alert(state, analysis)

    # Adaylık sönerse seviye hafızasını sıfırla; yeniden doğarsa tekrar haber verilebilir.
    if analysis["level"] == "IZLEME":
        state["last_alert_level"] = "IZLEME"
        return state

    if not should_send:
        return state

    message = _build_assistant_message(market_data, analysis, reason)
    sent = telegram_notifier.send_message(message)

    logging.info(
        "Assistant Telegram sonucu: %s | %s | skor %.1f",
        "Başarılı" if sent else "Gönderilmedi",
        analysis["level"],
        analysis["score"],
    )

    if sent:
        state["last_alert_level"] = analysis["level"]
        state["last_alert_ts"] = _now_ts()
        state["last_alert_volume"] = analysis.get("volume_ratio")
        state["last_alert_m3"] = analysis["momentum"].get("m3")

    return state


# -----------------------------------------------------------------------------
# Ana tarama
# -----------------------------------------------------------------------------

def run_scan(tracker, technical_analysis, signal_engine, telegram_notifier, tech_cache):
    market_data = tracker.get_market_data()
    if not market_data:
        logging.warning("H/TRY piyasa verisi alınamadı; tarama sessiz geçildi.")
        return

    # 200 adet 1 saatlik mum yalnızca ANA TREND için tutulur.
    # Her 60 saniyede yeniden çekilmez; 15 dakikada bir yenilenir.
    now = time.time()
    technical_result = tech_cache.get("technical_result")
    last_refresh = float(tech_cache.get("last_refresh") or 0)

    refresh_needed = (
        technical_result is None
        or (now - last_refresh) >= TECH_REFRESH_SECONDS
    )

    if refresh_needed:
        candles = tracker.get_candles(resolution="1h", limit=200)
        if candles:
            technical_result = technical_analysis.analyze(candles)
            tech_cache["technical_result"] = technical_result
            tech_cache["last_refresh"] = now
            logging.info("🔄 200 adet H/TRY 1h mum ana trend için yenilendi.")
        elif technical_result is None:
            logging.warning("H/TRY mum verisi alınamadı ve teknik önbellek boş; tarama sessiz geçildi.")
            return
        else:
            logging.warning("1h mum yenileme başarısız; son geçerli ana trend kullanılmaya devam ediyor.")

    # Anlık fiyat her 60 saniyede yenidir; teknik ana trend son geçerli 15 dakikalık
    # önbellekten gelir. Kısa momentum 1/3/5/15 dk snapshot geçmişinden hesaplanır.
    signal_result = signal_engine.analyze(market_data, technical_result)

    state = _load_json(STATE_FILE, {})
    state, _ = _append_history(state, market_data, technical_result)

    analysis = build_assistant_analysis(
        state,
        market_data,
        technical_result,
        signal_result,
    )

    logging.info(
        "H/TRY %s | assistant %.1f | %s | engine=%s | "
        "m1=%s m3=%s m5=%s m15=%s | hacim=%s | teyit=%s",
        market_data.get("price"),
        analysis["score"],
        analysis["level"],
        signal_result.get("score"),
        _fmt_pct(analysis["momentum"].get("m1")),
        _fmt_pct(analysis["momentum"].get("m3")),
        _fmt_pct(analysis["momentum"].get("m5")),
        _fmt_pct(analysis["momentum"].get("m15")),
        _fmt_num(analysis.get("volume_ratio")),
        analysis.get("confirmation_count"),
    )

    # Eşikleri değiştirmeden gerçek hareket örneklerini biriktir.
    _append_observation(
        {
            "ts": _now_ts(),
            "iso": datetime.now(timezone.utc).isoformat(),
            "price": _to_float(market_data.get("price")),
            "change_24h": _to_float(market_data.get("change_24h")),
            "assistant_score": analysis["score"],
            "entry_quality": analysis["entry_quality"],
            "level": analysis["level"],
            "engine_signal": signal_result.get("signal"),
            "engine_score": signal_result.get("score"),
            "m1": analysis["momentum"].get("m1"),
            "m3": analysis["momentum"].get("m3"),
            "m5": analysis["momentum"].get("m5"),
            "m15": analysis["momentum"].get("m15"),
            "volume_ratio": analysis.get("volume_ratio"),
            "volume_strengthening": analysis.get("volume_strengthening"),
            "acceleration": analysis.get("acceleration"),
            "confirmation_count": analysis.get("confirmation_count"),
            "micro_candidate": analysis.get("micro_candidate"),
            "micro_staircase": analysis.get("micro_staircase"),
            "micro_stair_move": analysis.get("micro_stair_move"),
            "micro_positive_steps": analysis.get("micro_positive_steps"),
            "reasons": analysis.get("reasons", []),
            "warnings": analysis.get("warnings", []),
        }
    )

    # 1) Nihai AL kararının sahibi artık Assistant.
    # Mevcut eşikler değişmedi:
    # Assistant >= 82 + en az 5 teyit + pozitif momentum => AL.
    if analysis.get("level") == "AL_ONCESI_GUCLU":
        if should_send_assistant_buy(analysis):
            telegram_message = format_assistant_buy_message(
                market_data,
                technical_result,
                signal_result,
                analysis,
            )
            sent = telegram_notifier.send_message(telegram_message)
            logging.info(
                "ASSISTANT AL Telegram sonucu: %s | assistant=%.1f | engine=%s",
                "Başarılı" if sent else "Gönderilmedi",
                analysis.get("score", 0),
                signal_result.get("signal"),
            )

            if sent:
                state["last_alert_level"] = "AL_ONCESI_GUCLU"
                state["last_alert_ts"] = _now_ts()
                state["last_alert_volume"] = analysis.get("volume_ratio")
                state["last_alert_m3"] = analysis["momentum"].get("m3")
        else:
            # Aynı hareket içindeki AL tekrarlarını sessizce bastır.
            logging.info(
                "Assistant AL şartları devam ediyor; tekrar mesaj bastırıldı."
            )
    else:
        # Assistant henüz nihai AL seviyesinde değilse erken aday katmanları çalışır.
        should_send_assistant_buy(analysis)  # reset/calm-streak hafızasını güncelle
        state = process_assistant_alert(
            state,
            market_data,
            analysis,
            telegram_notifier,
        )

    state["last_analysis"] = {
        "ts": _now_ts(),
        "level": analysis["level"],
        "score": analysis["score"],
        "entry_quality": analysis["entry_quality"],
        "momentum": analysis["momentum"],
        "volume_ratio": analysis.get("volume_ratio"),
        "signal": signal_result.get("signal"),
        "engine_score": signal_result.get("score"),
    }
    _save_json(STATE_FILE, state)


def main():
    logging.info("Humanity Assistant V3.5 ASSISTANT-AL başlatılıyor | tarama: %ss | 1h trend yenileme: %ss | eşikler: %s/%s/%s", SCAN_INTERVAL_SECONDS, TECH_REFRESH_SECONDS, EARLY_SCORE, STRONG_SCORE, VERY_STRONG_SCORE)

    # Telegram ayarı yoksa bot sessizce çalışmasın; deploy logunda net hata versin.
    validate_telegram_config()

    # Nesneleri her dakika yeniden yaratmak yerine bir kez oluşturuyoruz.
    tracker = HumanityTracker()
    technical_analysis = TechnicalAnalysis()
    signal_engine = SignalEngine()
    telegram_notifier = TelegramNotifier()

    # 1h teknik analiz önbelleği: ilk taramada doldurulur, sonra 15 dakikada bir yenilenir.
    tech_cache = {
        "technical_result": None,
        "last_refresh": 0,
    }

    while True:
        started = time.time()
        try:
            run_scan(
                tracker,
                technical_analysis,
                signal_engine,
                telegram_notifier,
                tech_cache,
            )
        except Exception:
            logging.exception("Ana tarama hatası")

        # Tarama süresi 60 saniyeye eklenmesin; yaklaşık her 60 saniyede bir başlasın.
        elapsed = time.time() - started
        sleep_for = max(5, SCAN_INTERVAL_SECONDS - elapsed)
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
