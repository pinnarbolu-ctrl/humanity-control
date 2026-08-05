"""
Humanity Control Telegram Bildirim Modülü

Botun ürettiği BUY, SELL ve WAIT sonuçlarını
Telegram üzerinden göndermek için kullanılır.
"""

import logging
import os

import requests


class TelegramNotifier:
    def __init__(self):
        """
        Telegram bilgilerini ortam değişkenlerinden okur.

        Gerekli değişkenler:
        BOT_TOKEN = "8855467313:AAHYdR1ts-liJ0hMwxxPGpgmrPne6ydFOpI"
        CHAT_IDS = [2097448038]
        """

        self.bot_token = os.getenv(
            "TELEGRAM_BOT_TOKEN",
            "",
        ).strip()

        self.chat_id = os.getenv(
            "TELEGRAM_CHAT_ID",
            "",
        ).strip()

        self.enabled = bool(
            self.bot_token and self.chat_id
        )

        if not self.enabled:
            logging.warning(
                "Telegram devre dışı: "
                "TELEGRAM_BOT_TOKEN veya "
                "TELEGRAM_CHAT_ID tanımlı değil."
            )

    def send_message(self, message):
        """
        Telegram'a metin mesajı gönderir.
        """

        if not self.enabled:
            logging.info(
                "Telegram mesajı gönderilmedi: "
                "Telegram ayarları eksik."
            )
            return False

        if not message:
            logging.warning(
                "Telegram mesajı boş olduğu için "
                "gönderilmedi."
            )
            return False

        url = (
            f"https://api.telegram.org/"
            f"bot{self.bot_token}/sendMessage"
        )

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=15,
            )

            response.raise_for_status()

            result = response.json()

            if not result.get("ok"):
                logging.error(
                    "Telegram mesajı reddedildi: %s",
                    result,
                )
                return False

            logging.info(
                "Telegram mesajı başarıyla gönderildi."
            )
            return True

        except requests.RequestException as error:
            logging.error(
                "Telegram bağlantı hatası: %s",
                error,
            )
            return False

        except (TypeError, ValueError) as error:
            logging.error(
                "Telegram cevap işleme hatası: %s",
                error,
            )
            return False

    @staticmethod
    def format_signal_message(
        market_data,
        technical_result,
        signal_result,
    ):
        """
        Analiz sonuçlarından okunabilir Telegram mesajı üretir.
        """

        market_data = market_data or {}
        technical_result = technical_result or {}
        signal_result = signal_result or {}

        ema_result = technical_result.get(
            "ema",
            {},
        )

        volume_result = technical_result.get(
            "volume",
            {},
        )

        signal = signal_result.get(
            "signal",
            "WAIT",
        )

        score = signal_result.get(
            "score",
            0,
        )

        signal_icon = {
            "BUY": "🟢",
            "SELL": "🔴",
            "WAIT": "🟡",
        }.get(signal, "⚪")

        price = market_data.get("price")
        change_24h = market_data.get("change_24h")

        ema_20 = ema_result.get("ema_20")
        ema_50 = ema_result.get("ema_50")
        ema_trend = ema_result.get(
            "trend",
            "UNKNOWN",
        )

        rsi = technical_result.get("rsi")
        rsi_status = technical_result.get(
            "rsi_status",
            "UNKNOWN",
        )

        macd_trend = technical_result.get(
            "macd_trend",
            "UNKNOWN",
        )

        volume_ratio = volume_result.get(
            "volume_ratio"
        )

        volume_status = volume_result.get(
            "status",
            "UNKNOWN",
        )

        reason = signal_result.get(
            "reason",
            "Açıklama bulunamadı.",
        )

        return (
            f"{signal_icon} <b>H/TRY ANALİZİ</b>\n\n"
            f"<b>Karar:</b> {signal}\n"
            f"<b>Skor:</b> {score}/100\n\n"
            f"💰 <b>Fiyat:</b> {price} TRY\n"
            f"📊 <b>24s değişim:</b> "
            f"%{change_24h}\n\n"
            f"📈 <b>EMA trendi:</b> {ema_trend}\n"
            f"• EMA 20: {ema_20}\n"
            f"• EMA 50: {ema_50}\n\n"
            f"📉 <b>RSI:</b> {rsi} "
            f"({rsi_status})\n"
            f"〽️ <b>MACD:</b> {macd_trend}\n"
            f"📦 <b>Hacim:</b> {volume_ratio}x "
            f"({volume_status})\n\n"
            f"📝 <b>Açıklama:</b>\n"
            f"{reason}"
        )
