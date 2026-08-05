"""
Humanity Control Bot
Ana çalışma dosyası
"""

import logging

from analysis.technical_analysis import TechnicalAnalysis
from market.humanity_tracker import HumanityTracker
from strategy.signal_engine import SignalEngine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def main():
    logging.info("Humanity Control Bot başlatılıyor...")

    tracker = HumanityTracker()
    technical_analysis = TechnicalAnalysis()
    signal_engine = SignalEngine()

    # Anlık H/TRY piyasa verisini al
    market_data = tracker.get_market_data()

    # Son 200 adet 1 saatlik mumu al
    candles = tracker.get_candles(
        resolution="1h",
        limit=200,
    )

    # EMA 20 ve EMA 50 trend analizini yap
    ema_analysis = technical_analysis.analyze_ema(candles)

    # Piyasa verisini ve EMA analizini karar motoruna gönder
    signal_result = signal_engine.analyze(
        market_data,
        ema_analysis,
    )

    if market_data:
        logging.info(
            "H/TRY fiyatı: %s TRY",
            market_data.get("price"),
        )
        logging.info(
            "24 saatlik değişim: %s%%",
            market_data.get("change_24h"),
        )
    else:
        logging.warning("H/TRY piyasa verisi alınamadı.")

    logging.info(
        "Alınan mum sayısı: %s",
        len(candles),
    )

    logging.info(
        "EMA 20: %s",
        ema_analysis.get("ema_20"),
    )
    logging.info(
        "EMA 50: %s",
        ema_analysis.get("ema_50"),
    )
    logging.info(
        "EMA trendi: %s",
        ema_analysis.get("trend"),
    )
    logging.info(
        "Trend açıklaması: %s",
        ema_analysis.get("reason"),
    )

    logging.info(
        "Karar: %s",
        signal_result.get("signal"),
    )
    logging.info(
        "Karar skoru: %s",
        signal_result.get("score"),
    )
    logging.info(
        "Karar sebebi: %s",
        signal_result.get("reason"),
    )


if __name__ == "__main__":
    main()
