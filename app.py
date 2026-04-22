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
# 前日判定 + JSON取得
# =========================
def get_prev_data(session):

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
                # ★ 前日判定
                if day_cursor == today + 1:
                    
                    # ★ このページのHTMLから直接PJ0302を抜く
                    match = re.search(r"jsonData\['PJ0302'\]\s*=\s*(\{[\s\S]*?\})\s*;", html)

                    if not match:
                        return None

                    data = json.loads(match.group(1))
                    return data

            day_cursor += colspan

    return None

# =========================
# 表示処理
# =========================
def run_prev_mode(data):

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

    data = get_prev_data(session)

    if data:
        st.info("🟡 前日（開催前日）")
        return run_prev_mode(data)
    else:
        st.info("⚪ 非開催日")
        return "開催なし"

st.code(main(), language="text")
