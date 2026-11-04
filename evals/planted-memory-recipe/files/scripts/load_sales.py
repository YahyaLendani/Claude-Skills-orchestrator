"""Load the quarterly sales CSV."""
import csv


def load_sales(path):
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return rows[:-1]
