import streamlit as st
from streamlit_autorefresh import st_autorefresh
import requests
import re
import json

# =========================
# 自動更新（3分）
# =========================
st_autorefresh(interval=180000, key="refresh")

st.title("競輪結果（玉野）")

TARGET_PLACE = "武雄"
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

def build_place_name(place):
    return f"{place}市営{place}競輪"

# ★ここ修正（flgSelect使わない）
def get_day_label(kaisai_list):
    days = []
    for k in kaisai_list:
        txt = k.get("txtDaily", "")
        if txt:
            days.append(txt.replace("(", "").replace(")", ""))

    if not days:
        return ""

    return days[-1]  # ←最後＝最新日

# ===== 日別条件 =====
def is_day2_target(name):
    return ("準決" in name) or ("二予" in name) or ("ガ予２" in name)

def is_day3_target(name):
    return ("準決" in name) or ("決勝" in name)

def is_day4_target(name):
    return "決勝" in name

# =========================
# データ取得
# =========================
def get_data():
    try:
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

        if not temp_enc:
            return f"{TARGET_PLACE}開催なし"

        jsj001 = requests.get(
            f"https://keirin.jp/pc/json?encp={temp_enc}&type=JSJ001",
            headers=HEADERS,
            timeout=10
        ).json()

        data = jsj001.get("C0201data")
        if not data:
            return "JSJ001取得失敗"

        enc = data.get("encSelParaR")

        enc_map = {
            f"{i+1}R": r.get("encParaR")
            for i, r in enumerate(data.get("C0201race", []))
        }

        title = data.get("raceName", "")
        grade = convert_grade(data.get("imgGradeAlt", ""))
        day_type = convert_day_type_from_icon(data.get("imgFuka1Alt", ""))
        day_label = get_day_label(data.get("C0201kaisai", []))
        place_name = build_place_name(TARGET_PLACE)

        result_json = requests.get(
            f"https://keirin.jp/pc/json?encp={enc}&disp=PJ0306&type=JSJ018",
            headers=HEADERS,
            timeout=10
        ).json()

        result_list = result_json.get("resultList")
        if not result_list:
            return "結果取得失敗"

        outputs = []

        for race in result_list:

            if not race.get("tyakui1List"):
                continue

            race_no = race.get("rclblRaceNo")
            race_name = race.get("rclblSyumokuName", "")

            result_raw = []
            for block, pos in [
                ("tyakui1List", 1),
                ("tyakui2List", 2),
                ("tyakui3List", 3)
            ]:
                for p in race.get(block, []):
                    result_raw.append((pos, p.get("rclblSensyuName", "")))

            enc_r = enc_map.get(race_no)
            if not enc_r:
                continue

            player_json = requests.get(
                f"https://keirin.jp/pc/json?encp={enc_r}&type=JSJ006",
                headers=HEADERS,
                timeout=10
            ).json()

            player_dict = {}
            for p in player_json.get("sensyuTypeInfo", []):
                key = normalize_name(p.get("sensyuName", ""))
                player_dict[key] = {
                    "pref": p.get("huKen", "").replace("　", ""),
                    "term": p.get("sotugyouki", "")
                }

            lines = []
            for pos, raw_name in result_raw:
                key = normalize_name(raw_name)
                info = player_dict.get(key, {"pref": "不明", "term": "不明"})
                lines.append(
                    f"{pos}着　{format_name(raw_name)}（{info['pref']}）{info['term']}期"
                )

            winner = format_name(result_raw[0][1])

            # ===== 結果 =====
            text_result = f"""{place_name}
「{title}」({grade}{day_type})
{day_label}　第{race_no}

{chr(10).join(lines)}

{winner} おめでとうございます！
{HASHTAGS}
"""
            outputs.append(text_result)

            # ===== コメント条件 =====
            comment_flag = False

            if "初日" in day_label:
                comment_flag = True
            elif "2日目" in day_label and is_day2_target(race_name):
                comment_flag = True
            elif "3日目" in day_label and is_day3_target(race_name):
                comment_flag = True
            elif ("最終日" in day_label or "4日目" in day_label) and is_day4_target(race_name):
                comment_flag = True

            if comment_flag:
                winner_name = result_raw[0][1]
                key = normalize_name(winner_name)
                info = player_dict.get(key, {"pref": "不明", "term": "不明"})

                text_intro = f"""{place_name}
「{title}」({grade}{day_type})

勝利選手の写真とレース後のコメントです！

{day_label}　第{race_no}
{winner_name}（{info['pref']}）{info['term']}期
「」

{HASHTAGS}
"""
                outputs.append(text_intro)

        if not outputs:
            return "結果待ち"

        return "\n\n----------------------\n\n".join(outputs)

    except Exception as e:
        return f"エラー: {e}"

# =========================
# 表示
# =========================
st.code(get_data(), language="text")
