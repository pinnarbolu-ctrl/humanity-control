"""
Humanity Signal Engine

H/TRY piyasa ve teknik analiz verilerini değerlendirir.
BUY, SELL veya WAIT kararı üretir.
"""


class SignalEngine:
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"

    def analyze(self, market_data, ema_analysis=None):
        """
        Piyasa verisini ve EMA analizini değerlendirir.

        Şimdilik EMA yalnızca yön puanı verir.
        RSI ve hacim onayı eklenmeden doğrudan
        BUY veya SELL sinyali üretilmez.
        """

        if not market_data:
            return {
                "signal": self.WAIT,
                "score": 0,
                "reason": "Piyasa verisi alınamadı.",
            }

        price = market_data.get("price")

        if price is None or price <= 0:
            return {
                "signal": self.WAIT,
                "score": 0,
                "reason": "Geçerli fiyat verisi bulunamadı.",
            }

        if not ema_analysis:
            return {
                "signal": self.WAIT,
                "score": 0,
                "reason": "EMA analizi bulunamadı.",
            }

        trend = ema_analysis.get("trend", "UNKNOWN")

        score = 0
        reasons = []

        if trend == "BULLISH":
            score += 1
            reasons.append("EMA trendi yükseliş yönünde.")

        elif trend == "BEARISH":
            score -= 1
            reasons.append("EMA trendi düşüş yönünde.")

        elif trend == "NEUTRAL":
            reasons.append("EMA trendi kararsız.")

        else:
            reasons.append("EMA trendi hesaplanamadı.")

        return {
            "signal": self.WAIT,
            "score": score,
            "reason": " ".join(reasons),
        }
