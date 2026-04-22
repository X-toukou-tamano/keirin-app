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
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# =========================
# 前日判定
# =========================
def get_prev_encp(session):

    now = datetime.now(timezone(timedelta(hours=9)))
    today = now.day
    year = now.year
    month = now.month

    st.write(f"DEBUG: 今日={today}")

    url = f"https://keirin.jp/pc/raceschedule?scyy={year}&scym={str(month).zfill(2)}"
    html = session.get(url, headers=HEADERS).text

    soup = BeautifulSoup(html, "html.parser")

    for row in soup.find_all("tr"):
        if TARGET_PLACE not in row.text:
            continue

        st.write("DEBUG: 玉野の行検出")

        tds = row.find_all("td", class_="td_day")
        day_cursor = 1

        for td in tds:
            colspan = int(td.get("colspan", 1))

            if "bk_kaisai" in td.get("class", []):
                a = td.find("a")
                if a:
                    encp = a.get("data-pprm-encp")
                    st.write(f"DEBUG: encp候補={encp}")

                    if day_cursor == today + 1:
                        st.write(f"DEBUG: ★前日一致 encp={encp}")
                        return encp

            day_cursor += colspan

    return None

# =========================
# 前日処理（通信ログ版）
# =========================
def run_prev_mode(session, encp):

    # ブラウザ遷移再現
    session.get("https://keirin.jp/pc/top", headers=HEADERS)
    session.get("https://keirin.jp/pc/raceschedule", headers=HEADERS)

    # ★まずGETで確認
    url = f"https://keirin.jp/pc/participationlist?encp={encp}"
    res = session.get(url, headers=HEADERS)

    st.write("====== GET確認 ======")
    st.write("URL:", url)
    st.write("status:", res.status_code)
    st.write("headers:", dict(res.headers))
    st.write("最終URL:", res.url)
    st.write("HTML先頭:")
    st.code(res.text[:300])

    # ★POSTでも試す（これが本命）
    st.write("====== POST確認 ======")

    post_url = "https://keirin.jp/pc/participationlist"
    payload = {
        "encp": encp
    }

    res_post = session.post(post_url, data=payload, headers=HEADERS)

    st.write("POST status:", res_post.status_code)
    st.write("POST URL:", post_url)
    st.write("POST HTML先頭:")
    st.code(res_post.text[:300])

    # PJ0302抽出
    match = re.search(r"jsonData\['PJ0302'\]\s*=\s*(\{[\s\S]*?\})\s*;", res_post.text)

    if not match:
        st.write("DEBUG: PJ0302取れない")
        return "データ取得失敗"

    st.write("DEBUG: PJ0302取得成功")

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
