"""
Notion 갓빈 매매일지 연동

환경변수 또는 token.txt:
  NOTION_TOKEN        : Notion Integration 토큰
  GODBIN_NOTION_DB_ID : 갓빈 매매일지 DB ID
"""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path


def _token() -> str | None:
    token = os.getenv("NOTION_TOKEN")
    if token:
        return token
    token_file = Path(__file__).parent / "notion_token.txt"
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    return None


DB_ID = os.getenv("GODBIN_NOTION_DB_ID", "379b0987-e58b-8163-a694-f79575a62aaa")


def _request(method: str, path: str, body: dict | None = None) -> dict | None:
    token = _token()
    if not token:
        print("  [notion] 토큰 없음 — token.txt 또는 NOTION_TOKEN 환경변수 설정 필요")
        return None
    if not DB_ID:
        print("  [notion] DB ID 없음 — GODBIN_NOTION_DB_ID 환경변수 또는 notion_logger.py DB_ID 설정 필요")
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
    req = urllib.request.Request(
        f"https://api.notion.com/v1{path}",
        data=data, headers=headers, method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  [notion] API 오류 {e.code}: {e.read().decode()}")
        return None


def create_entry(trade: dict) -> str | None:
    """진입 시 Notion DB에 새 행 생성. 반환: page_id"""
    symbol = trade["symbol"].split("/")[0]  # BTC/USDT:USDT → BTC
    side = trade["side"].upper()
    open_time = trade["open_time"][:16].replace("T", " ")  # 2026-06-08T03:15 → 2026-06-08 03:15
    title = f"{symbol} {side} {open_time}"

    props = {
        "종목":    {"title": [{"text": {"content": title}}]},
        "방향":    {"select": {"name": side}},
        "진입일시": {"date": {"start": trade["open_time"]}},
        "진입가":  {"number": float(trade["entry"])},
        "손절가":  {"number": float(trade["sl"])},
        "목표가":  {"number": float(trade["tp"])},
        "결과":    {"select": {"name": "홀딩중"}},
    }

    result = _request("POST", "/pages", {"parent": {"database_id": DB_ID}, "properties": props})
    if result:
        page_id = result["id"]
        print(f"  [notion] 등록: {title}  (page_id={page_id[:8]}...)")
        return page_id
    return None


def update_exit(trade: dict) -> bool:
    """청산 시 해당 행에 청산 정보 업데이트."""
    page_id = trade.get("notion_page_id")
    if not page_id:
        return False

    result_label = {"TP": "TP", "SL": "SL", "CLOSE": "봉마감청산"}.get(trade["result"], trade["result"])

    props = {
        "청산일시":  {"date": {"start": trade["close_time"]}},
        "청산가":   {"number": float(trade["exit"])},
        "수익률":   {"number": round(trade["pnl_pct"], 3)},
        "PnL_USDT": {"number": round(trade["pnl_usdt"], 2)},
        "결과":     {"select": {"name": result_label}},
    }

    result = _request("PATCH", f"/pages/{page_id}", {"properties": props})
    if result:
        marker = "WIN" if trade["pnl_usdt"] > 0 else "LOSS"
        print(f"  [notion] 청산 업데이트: {trade['symbol']} → {result_label} {trade['pnl_pct']:+.3f}% [{marker}]")
        return True
    return False
