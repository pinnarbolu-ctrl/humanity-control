"""
Humanity Tracker
BTCTurk üzerinden Humanity Protocol (H/TRY) verilerini takip eder.
"""

import logging
import time

import requests


class HumanityTracker:
    def __init__(self):
        self.exchange = "BTCTurk"
        self.symbol = "HTRY"

        self.ticker_url = "https://api.btcturk.com/api/v2/ticker"
        self.candle_url = (
            "https://graph-api.btcturk.com/v1/klines/history"
        )

    def get_market_data(self):
        """
        BTCTurk API üzerinden H/TRY anlık piyasa verilerini alır.
        """
        try:
            response = requests.get(
                self.ticker_url,
                params={"pairSymbol": self.symbol},
                timeout=10,
            )
            response.raise_for_status()

            result = response.json()
            data = result.get("data", [])

            if not data:
                logging.error("H/TRY piyasa verisi bulunamadı.")
                return None

            ticker = data[0]

            return {
                "symbol": self.symbol,
                "price": float(ticker.get("last", 0)),
                "high_24h": float(ticker.get("high", 0)),
                "low_24h": float(ticker.get("low", 0)),
                "volume_24h": float(ticker.get("volume", 0)),
                "change_24h": float(
                    ticker.get("dailyPercent", 0)
                ),
                "bid": float(ticker.get("bid", 0)),
                "ask": float(ticker.get("ask", 0)),
            }

        except requests.RequestException as error:
            logging.error(
                "BTCTurk bağlantı hatası: %s",
                error,
            )
            return None

        except (TypeError, ValueError, KeyError) as error:
            logging.error(
                "BTCTurk veri işleme hatası: %s",
                error,
            )
            return None

    def get_candles(self, resolution="1h", limit=200):
        """
        BTCTurk üzerinden H/TRY mum verilerini alır.

        Desteklenen zaman aralıkları:
        1m, 15m, 30m, 1h, 4h, 1d
        """
        resolution_map = {
            "1m": 1,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": "1D",
        }

        interval_seconds_map = {
            "1m": 60,
            "15m": 15 * 60,
            "30m": 30 * 60,
            "1h": 60 * 60,
            "4h": 4 * 60 * 60,
            "1d": 24 * 60 * 60,
        }

        if resolution not in resolution_map:
            logging.error(
                "Geçersiz mum aralığı: %s",
                resolution,
            )
            return []

        try:
            end_time = int(time.time())

            interval_seconds = interval_seconds_map[resolution]

            start_time = end_time - (
                interval_seconds * limit
            )

            response = requests.get(
                self.candle_url,
                params={
                    "symbol": self.symbol,
                    "resolution": resolution_map[resolution],
                    "from": start_time,
                    "to": end_time,
                },
                timeout=15,
            )
            response.raise_for_status()

            result = response.json()

            if result.get("s") != "ok":
                logging.error(
                    "BTCTurk mum verisi alınamadı: %s",
                    result,
                )
                return []

            timestamps = result.get("t", [])
            opens = result.get("o", [])
            highs = result.get("h", [])
            lows = result.get("l", [])
            closes = result.get("c", [])
            volumes = result.get("v", [])

            candle_count = min(
                len(timestamps),
                len(opens),
                len(highs),
                len(lows),
                len(closes),
                len(volumes),
            )

            candles = []

            for index in range(candle_count):
                candles.append(
                    {
                        "timestamp": timestamps[index],
                        "open": float(opens[index]),
                        "high": float(highs[index]),
                        "low": float(lows[index]),
                        "close": float(closes[index]),
                        "volume": float(volumes[index]),
                    }
                )

            if limit > 0:
                candles = candles[-limit:]

            logging.info(
                "%s adet H/TRY %s mumu alındı.",
                len(candles),
                resolution,
            )

            return candles

        except requests.RequestException as error:
            logging.error(
                "BTCTurk mum bağlantı hatası: %s",
                error,
            )
            return []

        except (
            TypeError,
            ValueError,
            KeyError,
            IndexError,
        ) as error:
            logging.error(
                "BTCTurk mum işleme hatası: %s",
                error,
            )
            return []

    def run(self):
        logging.info("Humanity Tracker çalışıyor...")

        market_data = self.get_market_data()
        candles = self.get_candles(
            resolution="1h",
            limit=200,
        )

        if market_data:
            logging.info(
                "H/TRY piyasa verisi: %s",
                market_data,
            )

        logging.info(
            "Toplam mum sayısı: %s",
            len(candles),
        )

        return market_data
