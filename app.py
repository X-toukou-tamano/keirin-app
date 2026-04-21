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
st.title("競輪結果（玉野）検証版")

TARGET_PLACE = "玉野"
TARGET_PRE_PLACE = "玉野"
HASHTAGS = "#玉野けいりん #チャリロトバンク玉野 #競輪"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# =========================
# ヘルパー
# =========================
def normalize_name(name): return name.replace("　", "").replace(" ", "")
def convert_grade(grade): return grade.replace("1","Ⅰ").replace("2","Ⅱ").replace("3","Ⅲ").replace("4","Ⅳ")
def build_place_name(title, place):
    return f"{title.split(f'in{place}')[0]}市営{place}競輪" if f"in{place}" in title else f"{place}市営{place}競輪"

# =========================
# 前日判定（ここは変更なし）
# =========================
def get_prev_target_encp(year, month, today):
    url = f"https://keirin.jp/pc/raceschedule?scyy={year}&scym={str(month).zfill(2)}"
    res = requests.get(url, headers=HEADERS).text
    soup = BeautifulSoup(res, "html.parser")
    target_row = None
    for row in soup.find_all("tr"):
        if TARGET_PRE_PLACE in row.text:
            target_row = row
            break
    if not target_row: return None
    
    tds = target_row.find_all("td", class_="td_day")
    day = 1
    for td in tds:
        if "bk_kaisai" in td.get("class", []):
            a = td.find("a")
            if a:
                encp = a.get("data-pprm-encp")
                if (day - 1) == today: return encp
        day += int(td.get("colspan", 1))
    return None

# =========================
# 岡山選手抽出（JSJ048検証ログ）
# =========================
def extract_players_from_jsj(jsj_data):
    # どこにデータがあるか探すための全キー出力
    st.write(f"DEBUG: JSONの第1階層キー: {list(jsj_data.keys())}")
    
    # JSJ048 の場合、データは MemberSelectionList 等にある可能性が高い
    # ログとして中身を少しだけ出す
    st.write("--- 取得データの一部(Raw) ---")
    st.write(str(jsj_data)[:500] + "...")
    
    players = []
    # ヒットさせるための検索ロジック（仮に MemberSelectionList とする）
    members = jsj_data.get("MemberSelectionList", {}).get("MemberSelection", [])
    if not members:
        # 別の階層（kanyusyaListなど）を想定
        members = jsj_data.get("kanyusyaList", [])

    st.write(f"DEBUG: 解析対象の選手数: {len(members)}")

    for m in members:
        name = m.get("kanyusyaName") or m.get("playerName") or "不明"
        pref = m.get("prefName") or m.get("prefecture") or ""
        if "岡山" in pref:
            st.write(f"DEBUG: ★岡山選手検知: {name}")
            players.append(name)
            
    return list(set(players))

# =========================
# メイン
# =========================
def get_data():
    try:
        now = datetime.now(timezone(timedelta(hours=9)))
        today, month, year = now.day, now.month, now.year
        st.write(f"DEBUG: 判定日={today}日")

        encp = get_prev_target_encp(year, month, today)
        if not encp: return "開催なし / 前日でもない"

        # 【本命】出場予定選手一覧(participationlist)のJSJ048を叩く
        # Refererを participationlist に偽装
        test_headers = HEADERS.copy()
        test_headers["Referer"] = f"https://keirin.jp/pc/participationlist?encp={encp}"
        
        # ログにある JSJ048 を試行
        json_url = f"https://keirin.jp/pc/json?encp={encp}&type=JSJ048&kanyusyaflg=1&kaisaikbikbn=1"
        st.write(f"DEBUG: 本命URLアクセス: {json_url}")
        
        res = requests.get(json_url, headers=test_headers)
        jsj = res.json()

        st.write(f"DEBUG: サーバー応答(resultCd): {jsj.get('resultCd')}")
        
        players = extract_players_from_jsj(jsj)
        
        if not players: return "岡山選手なし"

        title = jsj.get("raceName", "無題")
        grade = jsj.get("imgGradeAlt", "")
        place_name = build_place_name(title, TARGET_PRE_PLACE)
        outputs = [f"{place_name}\n「{title}」({grade})\n地元選手より意気込みを！\n{p}選手 「」\n{HASHTAGS}" for p in players]
        return "\n\n----------------------\n\n".join(outputs)

    except Exception as e:
        return f"エラー: {e}"

st.code(get_data(), language="text")
