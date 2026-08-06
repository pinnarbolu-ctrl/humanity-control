"""
Humanity Signal Engine

H/TRY piyasa ve teknik analiz verilerini değerlendirir.
BUY, SELL veya WAIT kararı üretir.
"""


class SignalEngine:
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"

    def __init__(self):
        self.last_signal = None


    def analyze(self, market_data, technical_result=None):
        """
        EMA, RSI, MACD ve hacim sonuçlarını puanlar.

        Puan aralığı:
        75–100: BUY
        26–74: WAIT
        0–25: SELL
        """

        if not market_data:
            return {
                "signal": self.WAIT,
                "score": 50,
                "reason": "Piyasa verisi alınamadı.",
                "details": {},
            }

        price = market_data.get("price")

        if price is None or price <= 0:
            return {
                "signal": self.WAIT,
                "score": 50,
                "reason": "Geçerli fiyat verisi bulunamadı.",
                "details": {},
            }

        if not technical_result:
            return {
                "signal": self.WAIT,
                "score": 50,
                "reason": "Teknik analiz sonucu bulunamadı.",
                "details": {},
            }

        score = 50
        reasons = []
        details = {}

        # -------------------------------------------------
        # EMA ANALİZİ
        # -------------------------------------------------

        ema_result = technical_result.get("ema", {})
        ema_trend = ema_result.get("trend", "UNKNOWN")

        details["ema_trend"] = ema_trend

        if ema_trend == "BULLISH":
            score += 20
            reasons.append("EMA yükseliş trendinde.")

        elif ema_trend == "BEARISH":
            score -= 20
            reasons.append("EMA düşüş trendinde.")

        elif ema_trend == "NEUTRAL":
            reasons.append("EMA trendi kararsız.")

        else:
            reasons.append("EMA analizi hesaplanamadı.")

        # -------------------------------------------------
        # RSI ANALİZİ
        # -------------------------------------------------

        rsi = technical_result.get("rsi")
        rsi_status = technical_result.get(
            "rsi_status",
            "UNKNOWN",
        )

        details["rsi"] = rsi
        details["rsi_status"] = rsi_status

        if rsi_status == "OVERSOLD":
            score += 15
            reasons.append(
                "RSI aşırı satım bölgesinde."
            )

        elif rsi_status == "OVERBOUGHT":
            score -= 15
            reasons.append(
                "RSI aşırı alım bölgesinde."
            )

        elif rsi_status == "NEUTRAL":
            reasons.append("RSI nötr bölgede.")

        else:
            reasons.append("RSI hesaplanamadı.")

        # -------------------------------------------------
        # MACD ANALİZİ
        # -------------------------------------------------

        macd_trend = technical_result.get(
            "macd_trend",
            "UNKNOWN",
        )

        details["macd_trend"] = macd_trend
        details["macd"] = technical_result.get("macd")
        details["macd_signal"] = technical_result.get(
            "macd_signal"
        )
        details["macd_histogram"] = technical_result.get(
            "macd_histogram"
        )

        if macd_trend == "BULLISH":
            score += 20
            reasons.append("MACD yükselişi destekliyor.")

        elif macd_trend == "BEARISH":
            score -= 20
            reasons.append("MACD düşüşü destekliyor.")

        elif macd_trend == "NEUTRAL":
            reasons.append("MACD kararsız.")

        else:
            reasons.append("MACD hesaplanamadı.")

        # -------------------------------------------------
        # HACİM ANALİZİ
        # -------------------------------------------------

        volume_result = technical_result.get(
            "volume",
            {},
        )

        volume_status = volume_result.get(
            "status",
            "UNKNOWN",
        )

        volume_ratio = volume_result.get(
            "volume_ratio"
        )

        details["volume_status"] = volume_status
        details["volume_ratio"] = volume_ratio

        if volume_status == "STRONG":
            if score > 50:
                score += 10
                reasons.append(
                    "Güçlü hacim yükselişi destekliyor."
                )

            elif score < 50:
                score -= 10
                reasons.append(
                    "Güçlü hacim düşüşü destekliyor."
                )

            else:
                reasons.append(
                    "Hacim güçlü ancak yön henüz net değil."
                )

        elif volume_status == "NORMAL":
            reasons.append("Hacim normal seviyede.")

        elif volume_status == "WEAK":
            reasons.append(
                "Hacim zayıf, hareket teyit edilmedi."
            )

        else:
            reasons.append("Hacim analizi yapılamadı.")

        # Puanı 0–100 arasında tut
        score = max(0, min(100, score))

        # -------------------------------------------------
        # NİHAİ KARAR
        # -------------------------------------------------

        if score >= 75:
            signal = self.BUY

        elif score <= 25:
            signal = self.SELL

        else:
            signal = self.WAIT

        notify = (signal != self.last_signal)
        self.last_signal = signal

        if score >= 90:
            strength = "VERY_STRONG"
        elif score >= 75:
            strength = "STRONG"
        elif score <= 10:
            strength = "VERY_WEAK"
        elif score <= 25:
            strength = "WEAK"
        else:
            strength = "NEUTRAL"

        return {
            "signal": signal,
            "score": score,
            "confidence": score,
            "strength": strength,
            "notify": notify,
            "reason": " ".join(reasons),
            "details": details,
        }
