"""
Humanity Tracker
BTCTurk üzerinden Humanity Protocol (H/TRY) verilerini takip eder.
"""

import logging
import requests


class HumanityTracker:
    def __init__(self):
        self.exchange = "BTCTurk"
        self.symbol = "HTRY"
        self.api_url = "https://api.btcturk.com/api/v2/ticker"

    def get_market_data(self):
        """
        BTCTurk API üzerinden H/TRY piyasa verilerini alır.
        """

        try:
            response = requests.get(
                self.api_url,
                params={"pairSymbol": self.symbol},
                timeout=10,
            )
            response.raise_for_status()

            result = response.json()
            data = result.get("data", [])

            if not data:
                logging.error("H/TRY verisi bulunamadı.")
                return None

            ticker = data[0]

            return {
                "symbol": self.symbol,
                "price": float(ticker.get("last", 0)),
                "high_24h": float(ticker.get("high", 0)),
                "low_24h": float(ticker.get("low", 0)),
                "volume_24h": float(ticker.get("volume", 0)),
                "change_24h": float(ticker.get("dailyPercent", 0)),
                "bid": float(ticker.get("bid", 0)),
                "ask": float(ticker.get("ask", 0)),
            }

        except requests.RequestException as error:
            logging.error("BTCTurk bağlantı hatası: %s", error)
            return None

        except (TypeError, ValueError, KeyError) as error:
            logging.error("BTCTurk veri işleme hatası: %s", error)
            return None

    def run(self):
        logging.info("Humanity Tracker çalışıyor...")

        data = self.get_market_data()

        if data:
            logging.info("H/TRY piyasa verisi: %s", data)

        return data
