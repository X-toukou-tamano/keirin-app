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

    st.write(f"DEBUG: schedule長さ={len(html)}")

    soup = BeautifulSoup(html, "html.parser")

    for row in soup.find_all("tr"):
        if TARGET_PLACE not in row.text:
            continue

        st.write("DEBUG: 玉野行検出")

        tds = row.find_all("td", class_="td_day")
        day_cursor = 1

        for td in tds:
            colspan = int(td.get("colspan", 1))

            if "bk_kaisai" in td.get("class", []):
                a = td.find("a")

                if a:
                    encp = a.get("data-pprm-encp")
                    st.write(f"DEBUG: encp候補={encp} / day={day_cursor}")

                    if day_cursor == today + 1:
                        st.write("DEBUG: ★前日確定")
                        return encp

            day_cursor += colspan

    st.write("DEBUG: 前日見つからず")
    return None


# =========================
# racelist取得（ここが本体）
# =========================
def fetch_racelist(session, encp):

    st.write("====== racelist取得開始 ======")

    # ★ JSJ001を先に叩く
    url_jsj = f"https://keirin.jp/pc/json?encp={encp}&type=JSJ001"
    res_jsj = session.get(url_jsj, headers=HEADERS)

    st.write(f"DEBUG: JSJ001 status={res_jsj.status_code}")
    st.write(f"DEBUG: JSJ001 length={len(res_jsj.text)}")

    # racelist
    url = f"https://keirin.jp/pc/racelist?encp={encp}&dkbn=2"
    res = session.get(url, headers=HEADERS)

    st.write(f"DEBUG: racelist status={res.status_code}")
    st.write(f"DEBUG: racelist URL={url}")
    st.write(f"DEBUG: racelist length={len(res.text)}")

    # 先頭確認
    st.write("DEBUG: HTML先頭👇")
    st.code(res.text[:400])

    return res.text


# =========================
# PJ0302抽出
# =========================
def parse_players(html):

    st.write("====== PJ0302抽出 ======")

    match = re.search(r"jsonData\['PJ0302'\]\s*=\s*(\{[\s\S]*?\})\s*;", html)

    if not match:
        st.write("DEBUG: PJ0302見つからない")
        return None

    st.write("DEBUG: PJ0302発見")

    data = json.loads(match.group(1))

    outputs = []

    for g in data["J0302data"]["J0302gaitei"]:
        for p in g["J0302sensyu"]:
            st.write(f"DEBUG: {p['playerNm']} / {p['hukenName']}")

            if "岡　山" in p["hukenName"]:
                outputs.append(p["playerNm"])

    return outputs


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

    html = fetch_racelist(session, encp)

    players = parse_players(html)

    if not players:
        return "岡山選手なし or 抽出失敗"

    return "\n".join(players)


st.code(main(), language="text")
