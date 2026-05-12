"""Pull QuickBooks Online deposits filtered by vendor on line items, to CSV."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
PROD_BASE = "https://quickbooks.api.intuit.com"
SANDBOX_BASE = "https://sandbox-quickbooks.api.intuit.com"
PAGE_SIZE = 1000


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def load_env() -> dict[str, str]:
    if not ENV_PATH.exists():
        die(f"{ENV_PATH} not found — copy .env.example to .env and fill it in")
    load_dotenv(ENV_PATH)
    required = ["QBO_CLIENT_ID", "QBO_CLIENT_SECRET", "QBO_REFRESH_TOKEN", "QBO_REALM_ID"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        die(f"missing required env vars in .env: {', '.join(missing)}")
    return {
        "client_id": os.environ["QBO_CLIENT_ID"],
        "client_secret": os.environ["QBO_CLIENT_SECRET"],
        "refresh_token": os.environ["QBO_REFRESH_TOKEN"],
        "realm_id": os.environ["QBO_REALM_ID"],
        "environment": os.environ.get("QBO_ENVIRONMENT", "production").lower(),
    }


def base_url(environment: str) -> str:
    return SANDBOX_BASE if environment == "sandbox" else PROD_BASE


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> tuple[str, str]:
    resp = requests.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        headers={"Accept": "application/json"},
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=30,
    )
    if resp.status_code != 200:
        die(f"token refresh failed ({resp.status_code}): {resp.text}")
    body = resp.json()
    new_access = body["access_token"]
    new_refresh = body.get("refresh_token", refresh_token)
    return new_access, new_refresh


def persist_refresh_token(new_refresh: str) -> None:
    """Rewrite .env in place, updating QBO_REFRESH_TOKEN and leaving everything else."""
    lines = ENV_PATH.read_text().splitlines()
    found = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("QBO_REFRESH_TOKEN="):
            lines[i] = f"QBO_REFRESH_TOKEN={new_refresh}"
            found = True
            break
    if not found:
        lines.append(f"QBO_REFRESH_TOKEN={new_refresh}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


def qbo_query(base: str, realm_id: str, access_token: str, query: str) -> dict[str, Any]:
    resp = requests.get(
        f"{base}/v3/company/{realm_id}/query",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        params={"query": query, "minorversion": "73"},
        timeout=60,
    )
    if resp.status_code != 200:
        die(f"QBO query failed ({resp.status_code}): {resp.text}\nquery: {query}")
    return resp.json().get("QueryResponse", {})


def escape_qbo_string(s: str) -> str:
    # QBO query language: backslash-escape single quotes.
    return s.replace("\\", "\\\\").replace("'", "\\'")


def resolve_vendor(base: str, realm_id: str, access_token: str, name: str) -> tuple[str, str]:
    safe = escape_qbo_string(name)
    qr = qbo_query(
        base,
        realm_id,
        access_token,
        f"SELECT Id, DisplayName FROM Vendor WHERE DisplayName = '{safe}'",
    )
    vendors = qr.get("Vendor", [])
    if not vendors:
        die(
            f"no vendor found with DisplayName == {name!r}. "
            "Vendor names must match exactly — check Vendors list in QBO."
        )
    if len(vendors) > 1:
        names = ", ".join(repr(v["DisplayName"]) for v in vendors)
        die(f"multiple vendors matched {name!r}: {names}")
    return vendors[0]["Id"], vendors[0]["DisplayName"]


def fetch_deposits(
    base: str, realm_id: str, access_token: str, date_from: str, date_to: str
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    start = 1
    while True:
        query = (
            f"SELECT * FROM Deposit "
            f"WHERE TxnDate >= '{date_from}' AND TxnDate <= '{date_to}' "
            f"STARTPOSITION {start} MAXRESULTS {PAGE_SIZE}"
        )
        qr = qbo_query(base, realm_id, access_token, query)
        batch = qr.get("Deposit", [])
        out.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return out


def extract_matching_lines(
    deposits: list[dict[str, Any]], vendor_id: str, vendor_name: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dep in deposits:
        deposit_id = dep.get("Id", "")
        deposit_date = dep.get("TxnDate", "")
        deposit_to = (dep.get("DepositToAccountRef") or {}).get("name", "")
        for line in dep.get("Line", []) or []:
            if line.get("DetailType") != "DepositLineDetail":
                continue
            detail = line.get("DepositLineDetail") or {}
            entity = detail.get("Entity") or {}
            if entity.get("value") != vendor_id:
                continue
            rows.append(
                {
                    "deposit_id": deposit_id,
                    "deposit_date": deposit_date,
                    "deposit_to_account": deposit_to,
                    "line_num": line.get("LineNum", ""),
                    "amount": line.get("Amount", ""),
                    "from_account": (detail.get("AccountRef") or {}).get("name", ""),
                    "payment_method": (detail.get("PaymentMethodRef") or {}).get("name", ""),
                    "check_num": detail.get("CheckNum", ""),
                    "memo": line.get("Description", ""),
                    "vendor": vendor_name,
                }
            )
    return rows


CSV_COLUMNS = [
    "deposit_id",
    "deposit_date",
    "deposit_to_account",
    "line_num",
    "amount",
    "from_account",
    "payment_method",
    "check_num",
    "memo",
    "vendor",
]


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pull QBO deposits filtered by vendor to CSV.")
    p.add_argument("--vendor", required=True, help="Exact Vendor DisplayName in QBO")
    p.add_argument("--from", dest="date_from", required=True, help="Start date YYYY-MM-DD (inclusive)")
    p.add_argument("--to", dest="date_to", required=True, help="End date YYYY-MM-DD (inclusive)")
    p.add_argument("--out", default="deposits.csv", help="Output CSV path (default: deposits.csv)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_env()
    base = base_url(cfg["environment"])

    access_token, new_refresh = refresh_access_token(
        cfg["client_id"], cfg["client_secret"], cfg["refresh_token"]
    )
    if new_refresh != cfg["refresh_token"]:
        persist_refresh_token(new_refresh)

    vendor_id, vendor_name = resolve_vendor(base, cfg["realm_id"], access_token, args.vendor)
    deposits = fetch_deposits(base, cfg["realm_id"], access_token, args.date_from, args.date_to)
    rows = extract_matching_lines(deposits, vendor_id, vendor_name)

    out_path = Path(args.out)
    write_csv(rows, out_path)

    total = sum(float(r["amount"] or 0) for r in rows)
    if not rows:
        print(
            f"{len(deposits)} deposit(s) in range, 0 matching lines for vendor "
            f"{vendor_name!r}. Wrote empty CSV (header only) → {out_path}"
        )
    else:
        print(
            f"{len(deposits)} deposit(s) in range, {len(rows)} matching line(s) "
            f"for vendor {vendor_name!r}, total ${total:,.2f} → {out_path}"
        )


if __name__ == "__main__":
    main()
