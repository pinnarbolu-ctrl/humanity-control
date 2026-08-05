"""
Humanity Tracker
BTCTurk üzerinden Humanity Control verilerini takip eder.
"""

import logging


class HumanityTracker:
    def __init__(self):
        self.exchange = "BTCTurk"

    def get_market_data(self):
        """
        Şimdilik boş iskelet.
        Sonraki committe BTCTurk API bağlantısı eklenecek.
        """
        return {}

    def run(self):
        logging.info("Humanity Tracker başlatıldı.")
