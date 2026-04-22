import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import re
import json
from datetime import datetime, timedelta, timezone

st_autorefresh(interval=180000, key="refresh")

st.title("玉野競輪 投稿生成アプリ")

now = datetime.now(timezone(timedelta(hours=9)))
st.write(f"📅 今日: {now.strftime('%Y-%m-%d %H:%M:%S')}")

TARGET_PLACE = "玉野"
HASHTAGS = "#玉野けいりん #チャリロトバンク玉野 #競輪"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# 前日判定（TOPベース）
# =========================
def get_tomorrow_tamano_encp(session):

    html = session.get("https://keirin.jp/pc/top", headers=HEADERS).text

    match = re.search(r"var pc0101_json = (\{.*?\});", html, re.DOTALL)
    if not match:
        return None

    data = json.loads(match.group(1))

    tomorrow = (datetime.now(timezone(timedelta(hours=9))) + timedelta(days=1)).strftime("%Y%m%d")

    for r in data["RaceList"]:
        if r["keirinjoName"] == TARGET_PLACE and r["kaisaiDate"] == tomorrow:
            return r["touhyouLivePara"]

    return None

# =========================
# 本体（racelistからPJ0302抜く）
# =========================
def run_prev_mode(session, encp):

    # ★重要：まずJSJ001で正規encpに変換
    jsj = session.get(
        f"https://keirin.jp/pc/json?encp={encp}&type=JSJ001",
        headers=HEADERS
    ).json()

    if "C0201data" not in jsj:
        return "データ取得失敗(JSJ001)"

    real_encp = jsj["C0201data"]["encSelParaK"]

    # ★ここで初めてracelistが通る
    url = f"https://keirin.jp/pc/racelist?encp={real_encp}&dkbn=2"
    res = session.get(url, headers=HEADERS)
    html = res.text

    st.write(f"DEBUG: status={res.status_code}")

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

    encp = get_tomorrow_tamano_encp(session)

    if encp:
        st.info("🟡 前日（開催前日）")
        return run_prev_mode(session, encp)
    else:
        st.info("⚪ 非開催日")
        return "開催なし"

st.code(main(), language="text")
