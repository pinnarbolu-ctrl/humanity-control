import logging
from pathlib import Path

APP_NAME = "H AI"
VERSION = "1.0.0"

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def main():
    logging.info("=" * 50)
    logging.info(f"{APP_NAME} v{VERSION} başlatıldı")
    logging.info("Foundation Commit 1")
    logging.info("Veri klasörü hazır.")
    logging.info("Yapay zeka modülleri daha sonra eklenecek.")
    logging.info("=" * 50)

if __name__ == "__main__":
    main()
