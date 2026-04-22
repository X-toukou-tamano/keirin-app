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
# 前日encp取得
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
# 本体（API直取り）
# =========================
def fetch_players(session, encp):

    st.write("DEBUG: PC0201取得開始")

    # ★これが本命API
    res = session.get(
        f"https://keirin.jp/pc/json?encp={encp}&type=PC0201",
        headers=HEADERS
    )

    st.write(f"DEBUG: status={res.status_code}")
    st.write(f"DEBUG: length={len(res.text)}")
    st.code(res.text[:300])

    try:
        data = res.json()
    except:
        return "JSON取得失敗"

    if "C0201data" not in data:
        return "PC0201構造エラー"

    players = []

    # ★選手一覧
    for p in data["C0201data"].get("C0201sensyu", []):
        st.write(f"DEBUG: {p['namePlayerSei']}")

        # ※ここは県情報が無いので名前だけ
        players.append(p["namePlayerSei"])

    return "\n".join(players) if players else "選手取得失敗"


# =========================
# メイン
# =========================
def main():

    session = requests.Session()

    encp = get_prev_encp(session)

    if not encp:
        st.info("⚪ 非開催日")
        return "開催なし"

    st.info("🟡 前日（開催前日）")

    return fetch_players(session, encp)


st.code(main(), language="text")
