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
# 前日ロジック（修正版）
# =========================
def get_html(session, year, month):
    url = f"https://keirin.jp/pc/raceschedule?scyy={year}&scym={str(month).zfill(2)}"
    return session.get(url, headers=HEADERS).text

def get_target_row(html):
    soup = BeautifulSoup(html, "html.parser")
    for row in soup.find_all("tr"):
        if TARGET_PLACE in row.text:
            return row
    return None

def get_start_info(row):
    tds = row.find_all("td", class_="td_day")
    day = 1
    result = []
    for td in tds:
        classes = td.get("class", [])
        colspan = int(td.get("colspan", 1))
        if "bk_kaisai" in classes:
            a = td.find("a")
            if a:
                encp = a.get("data-pprm-encp")
                result.append({"start": day, "prev": day - 1, "encp": encp})
        day += colspan
    return result

def get_prev_encp(session):
    now = datetime.now(timezone(timedelta(hours=9)))
    today, month, year = now.day, now.month, now.year

    html = get_html(session, year, month)
    row = get_target_row(html)
    if not row:
        return None

    infos = get_start_info(row)
    for r in infos:
        if r["prev"] == today:
            return r["encp"]

    return None

# ★★★★★ ここが完全修正ポイント ★★★★★
def run_prev_mode(session, encp):

    # 事前遷移（重要）
    session.get("https://keirin.jp/pc/top", headers=HEADERS)
    session.get("https://keirin.jp/pc/raceschedule", headers=HEADERS)

    # POSTでracelist取得（PJ0302）
    url = "https://keirin.jp/pc/racelist"
    payload = {
        "encp": encp,
        "disp": "PJ0302"
    }

    res = session.post(url, data=payload, headers=HEADERS)
    html = res.text

    # PJ0302抽出
    match = re.search(r"jsonData\['PJ0302'\]\s*=\s*(\{[\s\S]*?\})\s*;", html)

    if not match:
        return "PJ0302取得失敗"

    data = json.loads(match.group(1))

    # タイトル取得
    title = ""
    try:
        title = data["J0302data"]["J0302gaitei"][0]["bangumiName"]
    except:
        title = ""

    outputs = []
    seen = set()

    for g in data["J0302data"]["J0302gaitei"]:
        for p in g["J0302sensyu"]:
            if "岡　山" in p["hukenName"]:

                name = p["playerNm"]
                key = normalize_name(name)

                if key in seen:
                    continue
                seen.add(key)

                text = f"""{TARGET_PLACE}競輪
「{title}」
地元選手より、意気込みをいただきました！
{name}選手 「」
{HASHTAGS}
"""
                outputs.append(text)

    return "\n\n----------------------\n\n".join(outputs) if outputs else "岡山選手なし"

# =========================
# 開催中ロジック（そのまま）
# =========================
def get_top_json(session):
    html = session.get("https://keirin.jp/pc/top", headers=HEADERS).text
    match = re.search(r"var pc0101_json = (\{.*?\});", html, re.DOTALL)
    if not match:
        return None
    return json.loads(match.group(1))

def get_live_encp(session):
    top = get_top_json(session)
    if not top:
        return None

    for r in top["RaceList"]:
        if r["keirinjoName"] == TARGET_PLACE:
            return r["touhyouLivePara"]

    return None

def run_live_mode(session, temp_enc):

    jsj001 = session.get(
        f"https://keirin.jp/pc/json?encp={temp_enc}&type=JSJ001",
        headers=HEADERS
    ).json()

    if "C0201data" not in jsj001:
        return "開催情報取得失敗"

    data = jsj001["C0201data"]

    enc = data["encSelParaR"]
    enc_map = {f"{i+1}R": r["encParaR"] for i, r in enumerate(data["C0201race"])}

    title = data["raceName"]
    grade = convert_grade(data["imgGradeAlt"])
    day_type = convert_day_type_from_icon(data["imgFuka1Alt"])
    day_label = get_day_label(data["C0201kaisai"])
    place_name = build_place_name(TARGET_PLACE)

    result_json = session.get(
        f"https://keirin.jp/pc/json?encp={enc}&disp=PJ0306&type=JSJ018",
        headers=HEADERS
    ).json()

    if "resultList" not in result_json:
        return "結果取得失敗"

    outputs = []

    for race in result_json["resultList"]:

        if not race["tyakui1List"]:
            continue

        race_no = race["rclblRaceNo"]
        race_name = race["rclblSyumokuName"]

        if "初日" in day_label:
            pass
        elif "2日目" in day_label:
            if not is_day2_target(race_name):
                continue
        elif "3日目" in day_label:
            if not is_day3_target(race_name):
                continue
        elif "最終日" in day_label:
            if not is_day4_target(race_name):
                continue

        result_raw = []
        for block, pos in [
            ("tyakui1List", 1),
            ("tyakui2List", 2),
            ("tyakui3List", 3)
        ]:
            for p in race.get(block, []):
                result_raw.append((pos, p["rclblSensyuName"]))

        enc_r = enc_map.get(race_no)

        player_json = session.get(
            f"https://keirin.jp/pc/json?encp={enc_r}&type=JSJ006",
            headers=HEADERS
        ).json()

        player_dict = {}
        for p in player_json.get("sensyuTypeInfo", []):
            key = normalize_name(p["sensyuName"])
            player_dict[key] = {
                "pref": p["huKen"].replace("　", ""),
                "term": p["sotugyouki"]
            }

        lines = []
        for pos, raw_name in result_raw:
            key = normalize_name(raw_name)
            info = player_dict.get(key, {"pref": "不明", "term": "不明"})
            lines.append(
                f"{pos}着　{format_name(raw_name)} （{info['pref']}）{info['term']}期"
            )

        winner = format_name(result_raw[0][1])

        text = f"""{place_name}
「{title}」({grade}{day_type})
{day_label}　第{race_no}

{chr(10).join(lines)}

{winner} おめでとうございます！
{HASHTAGS}
"""
        outputs.append(text)

    return "\n\n----------------------\n\n".join(outputs)

# =========================
# メイン
# =========================
def main():
    try:
        session = requests.Session()

        # 開催中優先
        live_encp = get_live_encp(session)
        if live_encp:
            return run_live_mode(session, live_encp)

        # 前日
        prev_encp = get_prev_encp(session)
        if prev_encp:
            return run_prev_mode(session, prev_encp)

        return "開催なし"

    except Exception as e:
        return f"エラー: {e}"

# =========================
# 表示
# =========================
st.code(main(), language="text")
