import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# =========================
# 設定
# =========================
st_autorefresh(interval=180000, key="refresh")
st.title("競輪結果（玉野）Cookie検証")

# ターゲット（変更なし）
TARGET_PRE_PLACE = "玉野"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

# 画像から取得したCookie（一時的にハードコードして検証）
# ※有効期限が切れると使えなくなりますが、まずはこれで「-1」が消えるか見ます
DEBUG_COOKIE = {
    "analysis-cookie": "AeXiHhIE5K9UopwtXGagIr5MoXJFVMmCzwHqSi90FYY7SaWkKliEIKUrnIkNuVzX3"
}

def get_prev_target_encp():
    # 2026/04/22 のスケジュールから玉野の encp を引く（検証用）
    url = "https://keirin.jp/pc/raceschedule?scyy=2026&scym=04"
    res = requests.get(url, headers=HEADERS).text
    soup = BeautifulSoup(res, "html.parser")
    for row in soup.find_all("tr"):
        if TARGET_PRE_PLACE in row.text:
            a = row.find("a", {"data-pprm-encp": True})
            if a: return a.get("data-pprm-encp")
    return None

def verify_jsj_with_cookie():
    encp = get_prev_target_encp()
    if not encp: return "encp取得失敗"
    
    # セッションを作成してCookieとRefererをセット
    session = requests.Session()
    session.cookies.update(DEBUG_COOKIE)
    
    referer = f"https://keirin.jp/pc/participationlist?encp={encp}"
    url = f"https://keirin.jp/pc/json?encp={encp}&type=JSJ008&kanyusyaflg=1&kaisaikbikbn=1"
    
    st.write(f"DEBUG: 実行URL: {url}")
    
    res = session.get(url, headers={**HEADERS, "Referer": referer})
    data = res.json()
    
    st.write(f"DEBUG: resultCd: {data.get('resultCd')}")
    if data.get("resultCd") == 0:
        st.success("Cookieによる認証突破に成功しました！")
        st.write(f"DEBUG: 取得キー: {list(data.keys())}")
        # 岡山選手がいるかチラ見
        members = data.get("MemberSelectionList", {}).get("MemberSelection", [])
        st.write(f"DEBUG: 選手数: {len(members)}")
    else:
        st.error(f"認証失敗: {data.get('message')}")
    
    return "検証終了"

# 実行
st.code(verify_jsj_with_cookie())
