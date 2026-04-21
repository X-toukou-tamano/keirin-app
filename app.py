import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import calendar

# =========================
# 設定
# =========================
st_autorefresh(interval=180000, key="refresh")
st.title("競輪結果（玉野）最終検証")

TARGET_PLACE = "玉野"
TARGET_PRE_PLACE = "玉野"
HASHTAGS = "#玉野けいりん #チャリロトバンク玉野 #競輪"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_prev_target_encp(year, month, today):
    url = f"https://keirin.jp/pc/raceschedule?scyy={year}&scym={str(month).zfill(2)}"
    res = requests.get(url, headers=HEADERS).text
    soup = BeautifulSoup(res, "html.parser")
    for row in soup.find_all("tr"):
        if TARGET_PRE_PLACE in row.text:
            tds = row.find_all("td", class_="td_day")
            day = 1
            for td in tds:
                if "bk_kaisai" in td.get("class", []):
                    a = td.find("a")
                    if a and (day - 1) == today:
                        return a.get("data-pprm-encp")
                day += int(td.get("colspan", 1))
    return None

def get_data():
    try:
        now = datetime.now(timezone(timedelta(hours=9)))
        today, month, year = now.day, now.month, now.year
        encp = get_prev_target_encp(year, month, today)
        if not encp: return "開催なし / 前日でもない"

        # --- 【超本命】JSJ008 を正しいRefererで叩く ---
        test_headers = HEADERS.copy()
        # 紹介状を「出場予定選手一覧ページ」に設定
        test_headers["Referer"] = f"https://keirin.jp/pc/participationlist?encp={encp}"
        
        # パラメータもブラウザと完全一致させる
        final_url = f"https://keirin.jp/pc/json?encp={encp}&type=JSJ008&kanyusyaflg=1&kaisaikbikbn=1"
        st.write(f"DEBUG: 最終検証URL: {final_url}")
        
        res = requests.get(final_url, headers=test_headers)
        jsj = res.json()

        st.write(f"DEBUG: resultCd: {jsj.get('resultCd')}")
        st.write(f"DEBUG: 第1階層キー: {list(jsj.keys())}")

        # JSJ008であれば MemberSelectionList があるはず
        m_list_obj = jsj.get("MemberSelectionList", {})
        members = m_list_obj.get("MemberSelection", [])
        
        if not members:
            # キーが違う可能性を考慮してJSONを少しダンプ
            st.write("DEBUG: 選手リストが見つかりません。JSONの中身を一部確認:")
            st.write(str(jsj)[:300])
            return "データ構造不一致"

        st.write(f"DEBUG: 選手数: {len(members)}")
        
        players = []
        for m in members:
            name = m.get("kanyusyaName", "")
            pref = m.get("prefName", "")
            if "岡山" in pref:
                players.append(name)
                st.write(f"DEBUG: ★岡山選手ヒット: {name}")

        if not players: return "岡山選手なし"

        # 表示構築
        title = jsj.get("raceName", "無題")
        grade = jsj.get("imgGradeAlt", "")
        outputs = [f"地元選手より意気込みを！\n{p}選手 「」\n{HASHTAGS}" for p in players]
        return "\n\n---\n\n".join(outputs)

    except Exception as e:
        return f"エラー: {e}"

st.code(get_data(), language="text")
