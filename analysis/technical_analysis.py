"""
Humanity Teknik Analiz Modülü

H/TRY mum verileri üzerinden:
- EMA 20 ve EMA 50
- RSI 14
- MACD
- Hacim analizi

hesaplar.
"""


class TechnicalAnalysis:
    @staticmethod
    def calculate_ema(values, period):
        """
        Verilen sayı listesinin son EMA değerini hesaplar.
        """

        if not values or period <= 0:
            return None

        if len(values) < period:
            return None

        multiplier = 2 / (period + 1)

        ema = sum(values[:period]) / period

        for value in values[period:]:
            ema = (
                value * multiplier
                + ema * (1 - multiplier)
            )

        return ema

    @staticmethod
    def calculate_ema_series(values, period):
        """
        EMA değerlerini liste halinde hesaplar.
        MACD sinyal çizgisi için kullanılır.
        """

        if not values or period <= 0:
            return []

        if len(values) < period:
            return []

        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period

        ema_values = [ema]

        for value in values[period:]:
            ema = (
                value * multiplier
                + ema * (1 - multiplier)
            )
            ema_values.append(ema)

        return ema_values

    @staticmethod
    def calculate_rsi(values, period=14):
        """
        RSI değerini hesaplar.
        """

        if not values or period <= 0:
            return None

        if len(values) < period + 1:
            return None

        changes = []

        for index in range(1, len(values)):
            changes.append(
                values[index] - values[index - 1]
            )

        initial_changes = changes[:period]

        gains = [
            change if change > 0 else 0
            for change in initial_changes
        ]

        losses = [
            abs(change) if change < 0 else 0
            for change in initial_changes
        ]

        average_gain = sum(gains) / period
        average_loss = sum(losses) / period

        for change in changes[period:]:
            gain = change if change > 0 else 0
            loss = abs(change) if change < 0 else 0

            average_gain = (
                (average_gain * (period - 1)) + gain
            ) / period

            average_loss = (
                (average_loss * (period - 1)) + loss
            ) / period

        if average_loss == 0:
            return 100.0

        relative_strength = average_gain / average_loss

        rsi = 100 - (
            100 / (1 + relative_strength)
        )

        return rsi

    def calculate_macd(
        self,
        values,
        fast_period=12,
        slow_period=26,
        signal_period=9,
    ):
        """
        MACD, sinyal çizgisi ve histogramı hesaplar.
        """

        minimum_length = (
            slow_period + signal_period
        )

        if not values or len(values) < minimum_length:
            return {
                "macd": None,
                "signal": None,
                "histogram": None,
            }

        fast_ema_series = self.calculate_ema_series(
            values,
            fast_period,
        )

        slow_ema_series = self.calculate_ema_series(
            values,
            slow_period,
        )

        offset = slow_period - fast_period

        aligned_fast_series = fast_ema_series[offset:]

        usable_length = min(
            len(aligned_fast_series),
            len(slow_ema_series),
        )

        macd_series = []

        for index in range(usable_length):
            macd_series.append(
                aligned_fast_series[index]
                - slow_ema_series[index]
            )

        if len(macd_series) < signal_period:
            return {
                "macd": None,
                "signal": None,
                "histogram": None,
            }

        signal_series = self.calculate_ema_series(
            macd_series,
            signal_period,
        )

        if not signal_series:
            return {
                "macd": None,
                "signal": None,
                "histogram": None,
            }

        macd_value = macd_series[-1]
        signal_value = signal_series[-1]
        histogram = macd_value - signal_value

        return {
            "macd": macd_value,
            "signal": signal_value,
            "histogram": histogram,
        }

    @staticmethod
    def analyze_volume(candles, period=20):
        """
        Son mum hacmini önceki mumların ortalamasıyla karşılaştırır.
        """

        if not candles or period <= 0:
            return {
                "current_volume": None,
                "average_volume": None,
                "volume_ratio": None,
                "status": "UNKNOWN",
            }

        volumes = [
            float(candle["volume"])
            for candle in candles
            if candle.get("volume") is not None
        ]

        if len(volumes) < period + 1:
            return {
                "current_volume": None,
                "average_volume": None,
                "volume_ratio": None,
                "status": "UNKNOWN",
            }

        current_volume = volumes[-1]
        previous_volumes = volumes[-(period + 1):-1]

        average_volume = (
            sum(previous_volumes)
            / len(previous_volumes)
        )

        if average_volume <= 0:
            volume_ratio = 0
        else:
            volume_ratio = (
                current_volume / average_volume
            )

        if volume_ratio >= 1.5:
            status = "STRONG"

        elif volume_ratio >= 1.0:
            status = "NORMAL"

        else:
            status = "WEAK"

        return {
            "current_volume": round(
                current_volume,
                8,
            ),
            "average_volume": round(
                average_volume,
                8,
            ),
            "volume_ratio": round(
                volume_ratio,
                4,
            ),
            "status": status,
        }

    def analyze_ema(self, candles):
        """
        Mum kapanışlarından EMA 20 ve EMA 50 hesaplar.
        """

        if not candles:
            return {
                "current_price": None,
                "ema_20": None,
                "ema_50": None,
                "trend": "UNKNOWN",
                "reason": "Mum verisi bulunamadı.",
            }

        closes = [
            float(candle["close"])
            for candle in candles
            if candle.get("close") is not None
        ]

        if len(closes) < 50:
            return {
                "current_price": None,
                "ema_20": None,
                "ema_50": None,
                "trend": "UNKNOWN",
                "reason": (
                    "EMA hesabı için en az "
                    "50 mum gerekli."
                ),
            }

        ema_20 = self.calculate_ema(
            closes,
            20,
        )

        ema_50 = self.calculate_ema(
            closes,
            50,
        )

        current_price = closes[-1]

        if ema_20 is None or ema_50 is None:
            return {
                "current_price": current_price,
                "ema_20": ema_20,
                "ema_50": ema_50,
                "trend": "UNKNOWN",
                "reason": (
                    "EMA değerleri hesaplanamadı."
                ),
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
            reason = (
                "EMA değerleri net bir trend "
                "göstermiyor."
            )

        return {
            "current_price": round(
                current_price,
                8,
            ),
            "ema_20": round(
                ema_20,
                8,
            ),
            "ema_50": round(
                ema_50,
                8,
            ),
            "trend": trend,
            "reason": reason,
        }

    def analyze(self, candles):
        """
        Bütün teknik göstergeleri tek sonuçta birleştirir.
        """

        ema_analysis = self.analyze_ema(
            candles
        )

        closes = [
            float(candle["close"])
            for candle in candles
            if candle.get("close") is not None
        ]

        rsi = self.calculate_rsi(
            closes,
            period=14,
        )

        macd = self.calculate_macd(
            closes
        )

        volume = self.analyze_volume(
            candles,
            period=20,
        )

        if rsi is None:
            rsi_status = "UNKNOWN"

        elif rsi >= 70:
            rsi_status = "OVERBOUGHT"

        elif rsi <= 30:
            rsi_status = "OVERSOLD"

        else:
            rsi_status = "NEUTRAL"

        macd_value = macd.get("macd")
        signal_value = macd.get("signal")

        if (
            macd_value is None
            or signal_value is None
        ):
            macd_trend = "UNKNOWN"

        elif macd_value > signal_value:
            macd_trend = "BULLISH"

        elif macd_value < signal_value:
            macd_trend = "BEARISH"

        else:
            macd_trend = "NEUTRAL"

        return {
            "ema": ema_analysis,
            "rsi": (
                round(rsi, 2)
                if rsi is not None
                else None
            ),
            "rsi_status": rsi_status,
            "macd": (
                round(macd_value, 8)
                if macd_value is not None
                else None
            ),
            "macd_signal": (
                round(signal_value, 8)
                if signal_value is not None
                else None
            ),
            "macd_histogram": (
                round(macd.get("histogram"), 8)
                if macd.get("histogram") is not None
                else None
            ),
            "macd_trend": macd_trend,
            "volume": volume,
        }
