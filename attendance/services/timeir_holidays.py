"""Official Iranian holiday sync from time.ir.

The current time.ir annual-calendar page is a Next.js/React Server Components
page. The browser changes year by calling the server action
``fetchEventYearlyCalendarAction`` at POST /event-year. A plain GET with a
``?year=`` query is no longer a reliable API and can return HTTP 403.

This service deliberately mirrors the request observed in the browser:
- GET / first to establish normal site cookies/session
- POST /event-year
- Next-Action: 7f1826b2a370a6dcddacdb9aa92bc13ba09419e2ee
- body: [year]
- Accept: text/x-component

The useful calendar data is the JSON RSC chunk prefixed with ``1:``. The
response may contain mojibake when saved/decoded through a text proxy, so the
parser repairs the common latin1->utf8 representation before json decoding.
"""
from __future__ import annotations

import json
from typing import Any

import requests

BASE_URL = "https://www.time.ir/event-year"
HOME_URL = "https://www.time.ir/"
SERVER_ACTION = "7f1826b2a370a6dcddacdb9aa92bc13ba09419e2ee"
ROUTER_STATE = '%5B%22%22%2C%7B%22children%22%3A%5B%5B%22locale%22%2C%22fa%22%2C%22d%22%2Cnull%5D%2C%7B%22children%22%3A%5B%22event-year%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull%2C4096%5D%7D%2Cnull%2Cnull%2C4096%5D%7D%2Cnull%2Cnull%2C4112%5D%7D%2Cnull%2Cnull%2C4112%5D'
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _repair_text(raw: bytes) -> str:
    """Decode UTF-8 normally; repair the latin1/UTF-8 mojibake seen in captures."""
    text = raw.decode("utf-8", errors="replace")
    if "�" in text:
        return text
    # time.ir's RSC response itself is UTF-8. This second step is only needed
    # when the bytes were first decoded as latin1 by an intermediary.
    if "Ø" in text or "Û" in text or "â" in text:
        try:
            return text.encode("latin1").decode("utf-8")
        except UnicodeError:
            pass
    return text


def _extract_action_json(text: str) -> dict[str, Any]:
    """Extract the structured JSON object from the RSC ``1:`` chunk."""
    marker = text.find("1:")
    if marker < 0:
        raise RuntimeError("time.ir response did not contain the expected RSC JSON chunk (1:).")
    payload = text[marker + 2:]
    try:
        data, _ = json.JSONDecoder().raw_decode(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not decode time.ir RSC JSON chunk: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise RuntimeError("time.ir returned an unexpected calendar JSON structure.")
    return data


def parse_holidays_response(raw: bytes, year: int) -> list[dict[str, Any]]:
    data = _extract_action_json(_repair_text(raw))
    records: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()

    for month in data["data"]:
        for event in month.get("event_list") or []:
            if event.get("base") != 0 or event.get("is_holiday") is not True:
                continue
            if int(event.get("jalali_year") or 0) != year:
                continue
            jm = int(event.get("jalali_month") or 0)
            jd = int(event.get("jalali_day") or 0)
            title = str(event.get("title") or "").strip()
            if not (1 <= jm <= 12 and 1 <= jd <= 31 and title):
                continue
            key = (jm, jd, title)
            if key in seen:
                continue
            seen.add(key)
            records.append({
                "date": f"{year:04d}/{jm:02d}/{jd:02d}",
                "year": year,
                "month": jm,
                "day": jd,
                "title": title,
                "kind": "official",
                "source": BASE_URL,
            })

    records.sort(key=lambda row: (row["month"], row["day"], row["title"]))
    if not records:
        raise RuntimeError(f"No official holiday rows were detected for {year}; sync was aborted.")
    return records


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
        "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Referer": HOME_URL,
    }


def crawl_year(session: requests.Session, year: int) -> list[dict[str, Any]]:
    headers = _headers()
    # Establish the same normal site cookies a browser has before invoking the action.
    home = session.get(HOME_URL, headers=headers, timeout=(10, 30))
    home.raise_for_status()

    post_headers = {
        **headers,
        "Accept": "text/x-component",
        "Content-Type": "text/plain;charset=UTF-8",
        "Next-Action": SERVER_ACTION,
        "Next-Router-State-Tree": ROUTER_STATE,
        "Next-Url": "/event-year",
        "Origin": "https://www.time.ir",
        "Referer": BASE_URL,
    }
    response = session.post(
        BASE_URL,
        data=f"[{year}]",
        headers=post_headers,
        timeout=(10, 45),
    )
    if response.status_code == 403:
        raise RuntimeError(
            "time.ir درخواست Server Action را با 403 رد کرد. "
            "احتمالاً محدودیت ضدربات/دسترسی از IP سرور فعال شده است؛ "
            "درخواست باید از همان سروری اجرا شود که دسترسی به time.ir دارد."
        )
    response.raise_for_status()
    return parse_holidays_response(response.content, year)


def crawl_years(years: list[int]) -> list[dict[str, Any]]:
    session = requests.Session()
    rows: list[dict[str, Any]] = []
    for year in years:
        rows.extend(crawl_year(session, year))
    return rows
