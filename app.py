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
HASHTAGS = "#玉野けいりん #チャリロトバンク玉野 #競輪"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# 前日判定
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

                    if day_cursor == today + 1:
                        return encp

            day_cursor += colspan

    return None

# =========================
# 前日処理（本体）
# =========================
def run_prev_mode(session, encp):

    # 遷移再現
    session.get("https://keirin.jp/pc/top", headers=HEADERS)
    session.get("https://keirin.jp/pc/raceschedule", headers=HEADERS)

    # ★これが唯一の正解URL
    url = f"https://keirin.jp/pc/racelist?encp={encp}&dkbn=2"

    res = session.get(url, headers=HEADERS)
    html = res.text

    st.write(f"DEBUG: status={res.status_code}")
    st.write(f"DEBUG: HTML長さ={len(html)}")

    # JSON抽出
    match = re.search(r"jsonData\['PJ0302'\]\s*=\s*(\{[\s\S]*?\})\s*;", html)

    if not match:
        st.write("DEBUG: PJ0302取得失敗")
        st.code(html[:500])
        return "データ取得失敗"

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
