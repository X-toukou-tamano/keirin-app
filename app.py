import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime
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

    print(f"\n--- [LOG] get_start_info 開始 (場所: {TARGET_PRE_PLACE}) ---")
    for td in tds:
        classes = td.get("class", [])
        colspan = int(td.get("colspan", 1))
        inner_text = td.text.strip()
        
        # ログ: プログラム上のカウントと実際のセルの情報を出力
        print(f"DEBUG: counter={day}日目 | class={classes} | colspan={colspan} | text='{inner_text}'")

        if "bk_kaisai" in classes:
            a = td.find("a")
            if a:
                encp = a.get("data-pprm-encp")
                print(f"  => 開催開始を検知! 開始日判定: {day}")
                result.append({
                    "start": day,
                    "prev": day - 1,
                    "encp": encp
                })

        day += colspan
    print("--- [LOG] get_start_info 終了 ---\n")

    return result

def get_prev_target_encp(year, month, today):
    print(f"--- [LOG] get_prev_target_encp (本日: {today}日) ---")
    html = get_html(year, month)
    row = get_target_row(html, TARGET_PRE_PLACE)

    if row is None:
        print(f"ERROR: {TARGET_PRE_PLACE} の行が見つかりませんでした。")
        return None

    infos = get_start_info(row)

    # 当月
    for r in infos:
        print(f"判定チェック: 開催前日={r['prev']} vs 本日={today}")
        if r["prev"] == today:
            print("  => 一致! 前日処理を実行します。")
            return r["encp"]

    # 月跨ぎ
    print("当月内に該当なし。月跨ぎを確認します。")
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
                print("  => 月跨ぎでの前日一致を検知!")
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
        now = datetime.now()
        today = now.day
        month = now.month
        year = now.year
        
        print(f"\n[SYSTEM LOG] 実行時刻: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[SYSTEM LOG] 判定用日付: {year}年{month}月{today}日")

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
            print("LOG: 開催中データを検知しました。")
            jsj001 = requests.get(
                f"https://keirin.jp/pc/json?encp={temp_enc}&type=JSJ001",
                headers=HEADERS,
                timeout=10
            ).json()

            data = jsj001.get("C0201data")
            if not data:
                return "JSJ001取得失敗"

            title = data.get("raceName", "")
            place_name = build_place_name(title, TARGET_PLACE)

            return f"{place_name}\n開催中"

        # =========================
        # ★ 前日処理
        # =========================
        print("LOG: 開催中ではないため、前日判定へ移行します。")
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
