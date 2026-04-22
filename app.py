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

HEADERS = {"User-Agent": "Mozilla/5.0"}

# =========================
# 共通
# =========================
def normalize_name(name):
    return name.replace("　", "").replace(" ", "")

def format_name(name):
    return "#" + normalize_name(name)

# =========================
# 前日判定（完全修正版）
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

            # 開催セル
            if "bk_kaisai" in td.get("class", []):
                a = td.find("a")
                if a:
                    href = a.get("href")

                    if href and "encp=" in href:
                        encp = re.search(r"encp=([^&]+)", href).group(1)

                        start_day = day_cursor

                        # ★ 前日判定
                        if start_day - 1 == today:
                            st.write(f"DEBUG: 開催開始日={start_day}")
                            st.write(f"DEBUG: 前日一致 encp={encp}")
                            return encp

            day_cursor += colspan

    return None

# =========================
# 前日処理
# =========================
def run_prev_mode(session, encp):

    # 遷移再現
    session.get("https://keirin.jp/pc/top", headers=HEADERS)
    session.get("https://keirin.jp/pc/raceschedule", headers=HEADERS)

    url = f"https://keirin.jp/pc/racelist?encp={encp}"
    res = session.get(url, headers=HEADERS)

    html = res.text

    st.write(f"DEBUG: URL={url}")
    st.write(f"DEBUG: status={res.status_code}")
    st.write(f"DEBUG: HTML長さ={len(html)}")

    # JSON抽出
    match = re.search(r"jsonData\['PJ0302'\]\s*=\s*(\{[\s\S]*?\})\s*;", html)

    if not match:
        st.write("DEBUG: PJ0302取れない")
        st.code(html[:500])
        return "データ取得失敗"

    st.write("DEBUG: PJ0302取得OK")

    data = json.loads(match.group(1))

    outputs = []

    for gaitei in data["J0302data"]["J0302gaitei"]:
        for p in gaitei["J0302sensyu"]:
            if "岡　山" in p["hukenName"]:
                name = p["playerNm"]
                text = f"""{TARGET_PLACE}競輪
地元選手より、意気込みをいただきました！
{name}選手 「」
{HASHTAGS}
"""
                outputs.append(text)

    return "\n\n----------------------\n\n".join(outputs) if outputs else "岡山選手なし"

# =========================
# メイン
# =========================
def main():
    session = requests.Session()

    prev_encp = get_prev_encp(session)

    if prev_encp:
        st.info("🟡 前日（開催前日）")
        return run_prev_mode(session, prev_encp)
    else:
        st.info("⚪ 非開催日")
        return "開催なし"

st.code(main(), language="text")
