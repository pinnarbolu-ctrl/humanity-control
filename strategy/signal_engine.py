"""
Humanity Signal Engine

Bu modül H/TRY piyasa verisini analiz eder
ve BUY, SELL veya WAIT kararı üretir.
"""


class SignalEngine:
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"

    def analyze(self, market_data):
        """
        Market verisini analiz eder.

        Gerçek strateji kuralları daha sonra eklenecek.
        Şimdilik güvenli şekilde WAIT döndürür.
        """

        if not market_data:
            return {
                "signal": self.WAIT,
                "reason": "Piyasa verisi alınamadı.",
            }

        price = market_data.get("price")

        if price is None or price <= 0:
            return {
                "signal": self.WAIT,
                "reason": "Geçerli fiyat verisi bulunamadı.",
            }

        return {
            "signal": self.WAIT,
            "reason": "Yeterli analiz verisi henüz oluşmadı.",
        }
