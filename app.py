import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# =========================
# 自動更新（3分）
# =========================
st_autorefresh(interval=180000, key="refresh")

st.title("玉野競輪 投稿生成アプリ")

# 今日の日付表示
now = datetime.now(timezone(timedelta(hours=9)))
st.write(f"📅 今日: {now.strftime('%Y-%m-%d %H:%M:%S')}")

TARGET_PLACE = "玉野"
HASHTAGS = "#玉野けいりん #チャリロトバンク玉野 #競輪"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest"
}

# =========================
# 共通
# =========================
def normalize_name(name):
    return name.replace("　", "").replace(" ", "")

def format_name(name):
    return "#" + normalize_name(name)

def convert_day_type_from_icon(val):
    return {"01": "D", "02": "N", "03": "MID"}.get(val, "")

def convert_grade(grade):
    return grade.replace("1","Ⅰ").replace("2","Ⅱ").replace("3","Ⅲ").replace("4","Ⅳ")

def build_place_name(place):
    return f"{place}市営{place}競輪"

def get_day_label(kaisai_list):
    for k in kaisai_list:
        if k["flgSelect"]:
            return k["txtDaily"].replace("(", "").replace(")", "")
    return ""

# ===== 日別フィルタ =====
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
# 開催中判定（＋日付取得）
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
# 前日処理
# =========================
def run_prev_mode(session, encp):
    url = f"https://keirin.jp/pc/racelist?encp={encp}&dkbn=1"
    html = session.get(url, headers=HEADERS).text

    soup = BeautifulSoup(html, "html.parser")

    title = soup.find("div", class_="raceTitle").get_text(strip=True)

    outputs = []
    for row in soup.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) < 3:
            continue
        if "岡山" in tds[2].get_text():
            name = tds[2].get_text(strip=True)
            text = f"""{TARGET_PLACE}競輪
「{title}」
地元選手より、意気込みをいただきました！
{name}選手 「」
{HASHTAGS}
"""
            outputs.append(text)

    return "\n\n----------------------\n\n".join(outputs) if outputs else "岡山選手なし"

# =========================
# 開催中処理（フィルタ込み）
# =========================
def run_live_mode(session, encp, day_label):

    jsj001 = session.get(
        f"https://keirin.jp/pc/json?encp={encp}&type=JSJ001",
        headers=HEADERS
    ).json()["C0201data"]

    enc = jsj001["encSelParaR"]
    enc_map = {f"{i+1}R": r["encParaR"] for i, r in enumerate(jsj001["C0201race"])}

    title = jsj001["raceName"]
    grade = convert_grade(jsj001["imgGradeAlt"])
    day_type = convert_day_type_from_icon(jsj001["imgFuka1Alt"])
    place_name = build_place_name(TARGET_PLACE)

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

        # 日別フィルタ
        if "2日目" in day_label and not is_day2_target(race_name):
            continue
        if "3日目" in day_label and not is_day3_target(race_name):
            continue
        if "最終日" in day_label and not is_day4_target(race_name):
            continue

        result_raw = []
        for block, pos in [("tyakui1List",1),("tyakui2List",2),("tyakui3List",3)]:
            for p in race.get(block, []):
                result_raw.append((pos, p["rclblSensyuName"]))

        lines = [f"{pos}着　{format_name(name)}" for pos, name in result_raw]

        winner = format_name(result_raw[0][1])

        text = f"""{place_name}
「{title}」({grade}{day_type})
{day_label}　第{race_no}

{chr(10).join(lines)}

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

    # 状態判定
    live_encp, day_label = get_live_info(session)
    prev_encp = get_prev_encp(session)

    # ===== 状態表示 =====
    if live_encp:
        st.info(f"🟢 開催中：{day_label}")
        return run_live_mode(session, live_encp, day_label)

    elif prev_encp:
        st.info("🟡 前日（開催前日）")
        return run_prev_mode(session, prev_encp)

    else:
        st.info("⚪ 非開催日")
        return "開催なし"

# =========================
# 表示
# =========================
st.code(main(), language="text")
