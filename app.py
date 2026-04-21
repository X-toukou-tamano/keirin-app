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
st.title("競輪結果（玉野）デバッグ版")

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
# 取得・判定ロジック
# =========================
def get_html(url):
    return requests.get(url, headers=HEADERS, timeout=10).text

def get_start_info(row):
    tds = row.find_all("td", class_="td_day")
    day, result = 1, []
    st.write(f"DEBUG: スケジュール表から {len(tds)} セルをスキャン")
    for td in tds:
        if "bk_kaisai" in td.get("class", []):
            a = td.find("a")
            if a:
                encp = a.get("data-pprm-encp")
                st.write(f"DEBUG: {day}日目に開催検知")
                result.append({"start": day, "prev": day - 1, "encp": encp})
        day += int(td.get("colspan", 1))
    return result

def get_prev_target_encp(year, month, today):
    url = f"https://keirin.jp/pc/raceschedule?scyy={year}&scym={str(month).zfill(2)}"
    soup = BeautifulSoup(get_html(url), "html.parser")
    target_row = None
    for row in soup.find_all("tr"):
        if TARGET_PRE_PLACE in row.text:
            target_row = row
            break
    if not target_row: return None
    infos = get_start_info(target_row)
    for r in infos:
        if r["prev"] == today: return r["encp"]
    return None

# =========================
# 岡山選手抽出（強化ログ版）
# =========================
def extract_okayama_players(html):
    soup = BeautifulSoup(html, "html.parser")
    players = []
    
    # 【詳細ログ】HTML構造の解剖
    st.write(f"DEBUG: HTML文字数: {len(html)}")
    all_tables = soup.find_all("table")
    st.write(f"DEBUG: 検出テーブル数: {len(all_tables)}")
    
    all_rows = soup.find_all("tr")
    st.write(f"DEBUG: 全行数(tr): {len(all_rows)}")

    # 最初の30行分、何が書いてあるか全列出力（ズレ確認）
    st.write("--- 行データの中身（最初の20行のみ） ---")
    for i, row in enumerate(all_rows[:20]):
        tds = row.find_all(["td", "th"])
        col_texts = [t.get_text(strip=True) for t in tds]
        st.write(f"Row[{i}]: {' | '.join(col_texts)}")
        
        # 岡山という文字がこの行のどこかにあるか？
        if "岡山" in "".join(col_texts):
            st.write(f"DEBUG: ★'岡山'をRow[{i}]で発見！")
            # 通常、選手名は3列目（Index 2）
            if len(tds) >= 3:
                name = tds[2].get_text(strip=True)
                players.append(name)
                st.write(f"DEBUG: => 選手名として取得: {name}")

    # もし岡山選手が見つからなかった場合、HTML全体に"岡山"があるか最終チェック
    if not players and "岡山" in html:
        st.warning("警告：HTML全体には'岡山'が存在しますが、表(tr/td)としての抽出に失敗しています。構造が特殊な可能性があります。")
    elif not players:
        st.error("警告：HTML全体に'岡山'という文字が1つも含まれていません。JSJ(JSON)通信が必要です。")

    return list(set(players))

# =========================
# メイン処理
# =========================
def get_data():
    try:
        now = datetime.now(timezone(timedelta(hours=9)))
        today, month, year = now.day, now.month, now.year
        st.write(f"DEBUG: 判定時刻: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        # 1. TOP開催判定
        top_html = get_html("https://keirin.jp/pc/top")
        match = re.search(r"var pc0101_json = (\{.*?\});", top_html, re.DOTALL)
        if match:
            top = json.loads(match.group(1))
            for r in top.get("RaceList", []):
                if r.get("keirinjoName") == TARGET_PLACE:
                    return f"{TARGET_PLACE}競輪 開催中"

        # 2. 前日判定
        encp = get_prev_target_encp(year, month, today)
        if not encp: return "開催なし / 前日でもない"

        # 3. 出走表取得
        url = f"https://keirin.jp/pc/racelist?encp={encp}&dkbn=1"
        st.write(f"DEBUG: 出走表URL: {url}")
        
        headers_ref = HEADERS.copy()
        headers_ref["Referer"] = "https://keirin.jp/pc/raceschedule"
        html = requests.get(url, headers=headers_ref, timeout=10).text

        # 選手抽出
        players = extract_okayama_players(html)
        if not players: return "岡山選手なし"

        # 4. コメント構築
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("div", class_="raceTitle")
        title = title_tag.get_text(strip=True) if title_tag else "無題"
        grade_img = soup.find("img", class_="gradeIconSize")
        grade = grade_img.get("alt", "") if grade_img else ""
        
        place_name = build_place_name(title, TARGET_PRE_PLACE)
        res = [f"{place_name}\n「{title}」({grade})\n地元選手より、意気込みをいただきました！\n{p}選手 「」\n{HASHTAGS}" for p in players]
        return "\n\n----------------------\n\n".join(res)

    except Exception as e:
        return f"システムエラー: {e}"

# 出力
st.code(get_data(), language="text")
