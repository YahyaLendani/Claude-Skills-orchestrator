"""Fill the invoice template."""
from datetime import date
from pathlib import Path

TEMPLATE = Path(__file__).parent / "templates" / "invoice.html"


def format_date(value: date) -> str:
    return value.strftime("%m/%d/%Y")


def render_invoice(number: str, issued: date) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    return html.replace("{{number}}", number).replace("{{issued}}", format_date(issued))
