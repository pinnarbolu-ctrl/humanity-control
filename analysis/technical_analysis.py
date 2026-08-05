"""
Humanity Teknik Analiz Modülü

H/TRY mum verileri üzerinden teknik göstergeleri hesaplar.
"""


class TechnicalAnalysis:
    @staticmethod
    def calculate_ema(values, period):
        """
        Verilen fiyat listesinin EMA değerini hesaplar.
        """

        if not values or period <= 0:
            return None

        if len(values) < period:
            return None

        multiplier = 2 / (period + 1)

        # İlk EMA başlangıcı için basit hareketli ortalama
        ema = sum(values[:period]) / period

        for price in values[period:]:
            ema = (
                price * multiplier
                + ema * (1 - multiplier)
            )

        return ema

    def analyze_ema(self, candles):
        """
        Mum kapanışlarından EMA 20 ve EMA 50 hesaplar.
        Trend sonucunu döndürür.
        """

        if not candles:
            return {
                "ema_20": None,
                "ema_50": None,
                "trend": "UNKNOWN",
                "reason": "Mum verisi bulunamadı.",
            }

        closes = [
            candle["close"]
            for candle in candles
            if candle.get("close") is not None
        ]

        if len(closes) < 50:
            return {
                "ema_20": None,
                "ema_50": None,
                "trend": "UNKNOWN",
                "reason": "EMA hesabı için en az 50 mum gerekli.",
            }

        ema_20 = self.calculate_ema(closes, 20)
        ema_50 = self.calculate_ema(closes, 50)

        current_price = closes[-1]

        if ema_20 is None or ema_50 is None:
            return {
                "ema_20": ema_20,
                "ema_50": ema_50,
                "trend": "UNKNOWN",
                "reason": "EMA değerleri hesaplanamadı.",
            }

        if current_price > ema_20 > ema_50:
            trend = "BULLISH"
            reason = (
                "Fiyat EMA 20 üzerinde ve "
                "EMA 20, EMA 50 üzerinde."
            )

        elif current_price < ema_20 < ema_50:
            trend = "BEARISH"
            reason = (
                "Fiyat EMA 20 altında ve "
                "EMA 20, EMA 50 altında."
            )

        else:
            trend = "NEUTRAL"
            reason = "EMA değerleri net bir trend göstermiyor."

        return {
            "current_price": current_price,
            "ema_20": round(ema_20, 8),
            "ema_50": round(ema_50, 8),
            "trend": trend,
            "reason": reason,
        }
