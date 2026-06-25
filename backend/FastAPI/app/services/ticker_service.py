from pathlib import Path
import csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CSV_PATH = BASE_DIR / "sp500.csv"

valid_tickers = set()


def load_sp500():
    with open(CSV_PATH, newline="") as file:
        reader = csv.DictReader(file)

        return {
            row["ticker"].upper()
            for row in reader
        }
