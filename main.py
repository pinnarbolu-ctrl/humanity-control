

# ===== Kalıcı son sinyal kontrolü =====
LAST_SIGNAL_FILE = "last_signal.json"

def should_send_signal(signal_result):
    try:
        if os.path.exists(LAST_SIGNAL_FILE):
            with open(LAST_SIGNAL_FILE,"r",encoding="utf-8") as f:
                last=json.load(f)
        else:
            last=None
    except Exception:
        last=None

    current=signal_result.get("signal")

    # Her kararı hafızaya al. Böylece WAIT/BEKLE Telegram'a gitmese bile
    # WAIT -> AL veya WAIT -> SAT geçişi yeni sinyal olarak algılanır.
    changed = not (last and last.get("signal") == current)

    with open(LAST_SIGNAL_FILE,"w",encoding="utf-8") as f:
        json.dump({
            "signal":current,
            "score":signal_result.get("score")
        },f,ensure_ascii=False,indent=2)

    if not changed:
        return False

    # Telegram yalnızca gerçek AL/SAT sinyallerini göndersin.
    # WAIT/BEKLE kararları arka planda izlenir, mesaj olarak gönderilmez.
    normalized = str(current or "").strip().upper()
    return normalized in {"BUY", "AL", "SELL", "SAT"}

"""
Humanity Control Bot
Ana çalışma dosyası
"""

import logging
import json
import os

from analysis.technical_analysis import TechnicalAnalysis
from market.humanity_tracker import HumanityTracker
from strategy.signal_engine import SignalEngine
from telegram.telegram_notifier import TelegramNotifier


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def main():
    logging.info("Humanity Control Bot başlatılıyor...")

    tracker = HumanityTracker()
    technical_analysis = TechnicalAnalysis()
    signal_engine = SignalEngine()
    telegram_notifier = TelegramNotifier()

    # BTCTurk anlık H/TRY verisini al
    market_data = tracker.get_market_data()

    # Son 200 adet 1 saatlik mumu al
    candles = tracker.get_candles(
        resolution="1h",
        limit=200,
    )

    # EMA, RSI, MACD ve hacim analizlerini yap
    technical_result = technical_analysis.analyze(
        candles
    )

    # Teknik analizleri karar motoruna gönder
    signal_result = signal_engine.analyze(
        market_data,
        technical_result,
    )

    logging.info("--------------------------------")

    if market_data:
        logging.info(
            "H/TRY fiyatı: %s TRY",
            market_data.get("price"),
        )

        logging.info(
            "24 saatlik değişim: %s%%",
            market_data.get("change_24h"),
        )

        logging.info(
            "24 saatlik en yüksek: %s",
            market_data.get("high_24h"),
        )

        logging.info(
            "24 saatlik en düşük: %s",
            market_data.get("low_24h"),
        )

        logging.info(
            "Alış fiyatı: %s",
            market_data.get("bid"),
        )

        logging.info(
            "Satış fiyatı: %s",
            market_data.get("ask"),
        )

    else:
        logging.warning(
            "H/TRY piyasa verisi alınamadı."
        )

    logging.info(
        "Alınan mum sayısı: %s",
        len(candles),
    )

    logging.info("--------------------------------")

    ema_result = technical_result.get(
        "ema",
        {},
    )

    logging.info(
        "EMA 20: %s",
        ema_result.get("ema_20"),
    )

    logging.info(
        "EMA 50: %s",
        ema_result.get("ema_50"),
    )

    logging.info(
        "EMA trendi: %s",
        ema_result.get("trend"),
    )

    logging.info(
        "RSI: %s",
        technical_result.get("rsi"),
    )

    logging.info(
        "RSI durumu: %s",
        technical_result.get("rsi_status"),
    )

    logging.info(
        "MACD: %s",
        technical_result.get("macd"),
    )

    logging.info(
        "MACD sinyal çizgisi: %s",
        technical_result.get("macd_signal"),
    )

    logging.info(
        "MACD histogramı: %s",
        technical_result.get("macd_histogram"),
    )

    logging.info(
        "MACD trendi: %s",
        technical_result.get("macd_trend"),
    )

    volume_result = technical_result.get(
        "volume",
        {},
    )

    logging.info(
        "Hacim oranı: %s",
        volume_result.get("volume_ratio"),
    )

    logging.info(
        "Hacim durumu: %s",
        volume_result.get("status"),
    )

    logging.info("--------------------------------")

    logging.info(
        "Nihai karar: %s",
        signal_result.get("signal"),
    )

    logging.info(
        "Karar skoru: %s/100",
        signal_result.get("score"),
    )

    logging.info(
        "Karar açıklaması: %s",
        signal_result.get("reason"),
    )

    # Telegram mesajını hazırla
    telegram_message = (
        telegram_notifier.format_signal_message(
            market_data,
            technical_result,
            signal_result,
        )
    )

    # Telegram'a yalnızca değişen AL/SAT sinyalini gönder
    if should_send_signal(signal_result):
        telegram_sent = telegram_notifier.send_message(
            telegram_message
        )

        logging.info(
            "Telegram gönderim sonucu: %s",
            "Başarılı" if telegram_sent else "Gönderilmedi",
        )
    else:
        logging.info(
            "AL/SAT sinyali yok veya sinyal değişmedi. Telegram mesajı gönderilmedi."
        )

    logging.info("--------------------------------")


import time

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception:
            logging.exception("Ana döngü hatası")
        time.sleep(300)

