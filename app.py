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

def get_day_label(kaisai_list):
    for k in kaisai_list:
        if k["flgSelect"]:
            return k["txtDaily"].replace("(", "").replace(")", "")
    return ""

def is_day2_target(name):
    return ("準決" in name) or ("二予" in name) or ("ガ予２" in name)

def is_day3_target(name):
    return ("準決" in name) or ("決勝" in name)

def is_day4_target(name):
    return "決勝" in name

# =========================
# 前日判定
# =========================
def get_prev_encp(session):
    now = datetime.now(timezone(timedelta(hours=9)))
    today, month, year = now.day, now.month, now.year

    url = f"https://keirin.jp/pc/raceschedule?scyy={year}&scym={str(month).zfill(2)}"
    html = session.get(url, headers=HEADERS).text
    soup = BeautifulSoup(html, "html.parser")

    for row in soup.find_all("tr"):
        if TARGET_PLACE in row.text:
            tds = row.find_all("td", class_="td_day")
            day = 1
            for td in tds:
                colspan = int(td.get("colspan", 1))
                if "bk_kaisai" in td.get("class", []):
                    a = td.find("a")
                    if a:
                        encp = a.get("data-pprm-encp")
                        if day - 1 == today:
                            return encp
                day += colspan
    return None

# =========================
# 開催中判定
# =========================
def get_live_info(session):
    html = session.get("https://keirin.jp/pc/top", headers=HEADERS).text
    match = re.search(r"var pc0101_json = (\{.*?\});", html, re.DOTALL)
    if not match:
        return None, None

    top = json.loads(match.group(1))

    for r in top["RaceList"]:
        if r["keirinjoName"] == TARGET_PLACE:
            encp = r["touhyouLivePara"]

            jsj001 = session.get(
                f"https://keirin.jp/pc/json?encp={encp}&type=JSJ001",
                headers=HEADERS
            ).json()

            if "C0201data" not in jsj001:
                return encp, None

            day_label = get_day_label(jsj001["C0201data"]["C0201kaisai"])
            return encp, day_label

    return None, None

# =========================
# 前日処理（修正版）
# =========================
def run_prev_mode(session, encp):

    url = f"https://keirin.jp/pc/racelist?encp={encp}"
    html = session.get(url, headers=HEADERS).text

    # ★ 修正済み（確実に拾う）
    match = re.search(r"jsonData\['PJ0302'\]\s*=\s*(\{.*?\})\s*;", html, re.DOTALL)

    if not match:
        return "データ取得失敗"

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
# 開催中処理
# =========================
def run_live_mode(session, encp, day_label):

    jsj001 = session.get(
        f"https://keirin.jp/pc/json?encp={encp}&type=JSJ001",
        headers=HEADERS
    ).json()["C0201data"]

    enc = jsj001["encSelParaR"]
    title = jsj001["raceName"]

    result_json = session.get(
        f"https://keirin.jp/pc/json?encp={enc}&disp=PJ0306&type=JSJ018",
        headers=HEADERS
    ).json()

    outputs = []

    for race in result_json.get("resultList", []):
        if not race["tyakui1List"]:
            continue

        race_no = race["rclblRaceNo"]
        race_name = race["rclblSyumokuName"]

        if "2日目" in day_label and not is_day2_target(race_name):
            continue
        if "3日目" in day_label and not is_day3_target(race_name):
            continue
        if "最終日" in day_label and not is_day4_target(race_name):
            continue

        winner = format_name(race["tyakui1List"][0]["rclblSensyuName"])

        text = f"""{TARGET_PLACE}競輪
「{title}」
{day_label}　第{race_no}

{winner} おめでとうございます！
{HASHTAGS}
"""
        outputs.append(text)

    return "\n\n----------------------\n\n".join(outputs) if outputs else "対象レースなし"

# =========================
# メイン
# =========================
def main():
    session = requests.Session()

    live_encp, day_label = get_live_info(session)
    prev_encp = get_prev_encp(session)

    if live_encp:
        st.info(f"🟢 開催中：{day_label}")
        return run_live_mode(session, live_encp, day_label)

    elif prev_encp:
        st.info("🟡 前日（開催前日）")
        return run_prev_mode(session, prev_encp)

    else:
        st.info("⚪ 非開催日")
        return "開催なし"

st.code(main(), language="text")
