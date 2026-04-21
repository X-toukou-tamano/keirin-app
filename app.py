import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import calendar

# =========================
# 自動更新（3分）
# =========================
st_autorefresh(interval=180000, key="refresh")

st.title("競輪結果（玉野）")

TARGET_PLACE = "玉野"
TARGET_PRE_PLACE = "玉野"

HASHTAGS = "#玉野けいりん #チャリロトバンク玉野 #競輪"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# ヘルパー
# =========================
def normalize_name(name):
    return name.replace("　", "").replace(" ", "")

def format_name(name):
    return "#" + normalize_name(name)

def convert_day_type_from_icon(val):
    return {"01": "D", "02": "N", "03": "MID"}.get(val, "")

def convert_grade(grade):
    return grade.replace("1","Ⅰ").replace("2","Ⅱ").replace("3","Ⅲ").replace("4","Ⅳ")

def build_place_name(title, place):
    if f"in{place}" in title:
        base = title.split(f"in{place}")[0]
        return f"{base}市営{place}競輪"
    else:
        return f"{place}市営{place}競輪"

def get_day_label(kaisai_list):
    days = []
    for k in kaisai_list:
        txt = k.get("txtDaily", "")
        if txt:
            days.append(txt.replace("(", "").replace(")", ""))
    return days[-1] if days else ""

# =========================
# 前日ロジック
# =========================
def get_html(year, month):
    url = f"https://keirin.jp/pc/raceschedule?scyy={year}&scym={str(month).zfill(2)}"
    return requests.get(url, headers=HEADERS).text

def get_target_row(html, place):
    soup = BeautifulSoup(html, "html.parser")
    for row in soup.find_all("tr"):
        if place in row.text:
            return row
    return None

def get_start_info(row):
    tds = row.find_all("td", class_="td_day")

    day = 1
    result = []

    st.write(f"DEBUG: {TARGET_PRE_PLACE}の行から {len(tds)} 個のセルを読み込みました")

    for td in tds:
        classes = td.get("class", [])
        if "bk_kaisai" in classes:
            a = td.find("a")
            encp = a.get("data-pprm-encp") if a else None
            
            st.write(f"DEBUG: 開催セル検知! プログラム上の日付カウント: {day}日目 (クラス: {classes})")

            result.append({
                "start": day,
                "prev": day - 1,
                "encp": encp
            })

        day += int(td.get("colspan", 1))

    return result

def get_prev_target_encp(year, month, today):

    html = get_html(year, month)
    row = get_target_row(html, TARGET_PRE_PLACE)

    if row is None:
        st.write(f"DEBUG: {TARGET_PRE_PLACE} の行が見つかりません")
        return None

    infos = get_start_info(row)

    # 当月
    for r in infos:
        st.write(f"DEBUG: 比較中... 開催前日判定:{r['prev']} vs 今日の日付:{today}")
        if r["prev"] == today:
            st.write("DEBUG: 一致しました！")
            return r["encp"]

    # 月跨ぎ
    next_month = month + 1
    next_year = year

    if next_month == 13:
        next_month = 1
        next_year += 1

    html_next = get_html(next_year, next_month)
    row_next = get_target_row(html_next, TARGET_PRE_PLACE)
    
    if row_next:
        infos_next = get_start_info(row_next)
        last_day = calendar.monthrange(year, month)[1]

        for r in infos_next:
            if r["start"] == 1 and today == last_day:
                st.write("DEBUG: 月跨ぎで一致しました！")
                return r["encp"]

    return None

# =========================
# 岡山選手抽出
# =========================
def extract_okayama_players(html):
    soup = BeautifulSoup(html, "html.parser")

    players = []

    for row in soup.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) < 3:
            continue

        text = tds[2].get_text()

        if "岡山" in text:
            name = tds[2].get_text(strip=True)
            players.append(name)

    return players

def extract_event_info(html):
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    title_tag = soup.find("div", class_="raceTitle")
    if title_tag:
        title = title_tag.get_text(strip=True)

    grade = ""
    grade_img = soup.find("img", class_="gradeIconSize")
    if grade_img:
        grade = grade_img.get("alt", "")

    return title, grade

def build_pre_comment(players, html):

    title, grade = extract_event_info(html)
    place_name = build_place_name(title, TARGET_PRE_PLACE)

    outputs = []

    for p in players:
        text = f"""{place_name}
「{title}」({grade})
地元選手より、意気込みをいただきました！
{p}選手  「」
{HASHTAGS}
"""
        outputs.append(text)

    return outputs

# =========================
# メイン
# =========================
def get_data():
    try:
        # 【追加】日本時間(JST)を強制的に取得
        now = datetime.now(timezone(timedelta(hours=9)))
        today = now.day
        month = now.month
        year = now.year

        st.write(f"DEBUG: 判定に使用している今日の日付: {today}日")

        # ===== TOP =====
        html = requests.get(
            "https://keirin.jp/pc/top",
            headers=HEADERS,
            timeout=10
        ).text

        match = re.search(r"var pc0101_json = (\{.*?\});", html, re.DOTALL)
        if not match:
            return "TOP取得失敗"

        top = json.loads(match.group(1))

        temp_enc = None
        for r in top.get("RaceList", []):
            if r.get("keirinjoName") == TARGET_PLACE:
                temp_enc = r.get("touhyouLivePara")
                break

        # =========================
        # ★ 開催中
        # =========================
        if temp_enc:

            jsj001 = requests.get(
                f"https://keirin.jp/pc/json?encp={temp_enc}&type=JSJ001",
                headers=HEADERS,
                timeout=10
            ).json()

            data = jsj001.get("C0201data")
            if not data:
                return "JSJ001取得失敗"

            title = data.get("raceName", "")
            grade = convert_grade(data.get("imgGradeAlt", ""))
            day_type = convert_day_type_from_icon(data.get("imgFuka1Alt", ""))
            day_label = get_day_label(data.get("C0201kaisai", []))
            place_name = build_place_name(title, TARGET_PLACE)

            return f"{place_name}\n開催中"

        # =========================
        # ★ 前日処理
        # =========================
        encp = get_prev_target_encp(year, month, today)

        if not encp:
            return "開催なし / 前日でもない"

        url = f"https://keirin.jp/pc/racelist?encp={encp}&dkbn=1"
        html = requests.get(url, headers=HEADERS).text

        players = extract_okayama_players(html)

        if not players:
            return "岡山選手なし"

        outputs = build_pre_comment(players, html)

        return "\n\n----------------------\n\n".join(outputs)

    except Exception as e:
        return f"エラー: {e}"

# =========================
# 表示
# =========================
st.code(get_data(), language="text")
