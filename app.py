import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

st_autorefresh(interval=180000, key="refresh")

st.title("玉野競輪 投稿生成アプリ")

now = datetime.now(timezone(timedelta(hours=9)))
today = now.day
st.write(f"📅 今日: {now.strftime('%Y-%m-%d %H:%M:%S')}")

TARGET_PLACE = "玉野"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# =========================
# 前日encp取得（schedule）
# =========================
def get_prev_encp(session):

    now = datetime.now(timezone(timedelta(hours=9)))
    today = now.day
    year = now.year
    month = now.month

    url = f"https://keirin.jp/pc/raceschedule?scyy={year}&scym={str(month).zfill(2)}"
    html = session.get(url, headers=HEADERS).text

    soup = BeautifulSoup(html, "html.parser")

    for row in soup.find_all("tr"):
        if TARGET_PLACE not in row.text:
            continue

        tds = row.find_all("td", class_="td_day")
        day_cursor = 1

        for td in tds:
            colspan = int(td.get("colspan", 1))

            if "bk_kaisai" in td.get("class", []):
                a = td.find("a")
                if a:
                    encp = a.get("data-pprm-encp")

                    # ★ 前日判定
                    if day_cursor == today + 1:
                        return encp

            day_cursor += colspan

    return None

# =========================
# 本体
# =========================
def run_prev_mode(session, encp):

    # ★ encp変換（これが最重要）
    js = session.get(
        f"https://keirin.jp/pc/json?encp={encp}&type=PC0201",
        headers=HEADERS
    ).json()

    if "C0201data" not in js:
        return "PC0201取得失敗"

    real_encp = js["C0201data"]["encSelParaK"]

    # ★ 正しいページ
    url = f"https://keirin.jp/pc/racelist?encp={real_encp}&dkbn=2"
    html = session.get(url, headers=HEADERS).text

    match = re.search(r"jsonData\['PJ0302'\]\s*=\s*(\{[\s\S]*?\})\s*;", html)

    if not match:
        return "PJ0302取得失敗"

    data = json.loads(match.group(1))

    outputs = []

    for g in data["J0302data"]["J0302gaitei"]:
        for p in g["J0302sensyu"]:
            if "岡　山" in p["hukenName"]:
                outputs.append(p["playerNm"])

    return "\n".join(outputs) if outputs else "岡山選手なし"

# =========================
# メイン
# =========================
def main():
    session = requests.Session()

    encp = get_prev_encp(session)

    if encp:
        st.info("🟡 前日（開催前日）")
        return run_prev_mode(session, encp)
    else:
        st.info("⚪ 非開催日")
        return "開催なし"

st.code(main(), language="text")
