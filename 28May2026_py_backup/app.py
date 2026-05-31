import streamlit as st
import os
import re
from datetime import datetime
from urllib.parse import urlencode

import pandas as pd
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="馬匹出賽通知提示系統", page_icon="🏇", layout="wide")

DATA_XLSX = "horses.xlsx"
DATA_CSV = "horses.csv"
COLUMNS = ["狀態", "馬匹名字", "電郵地址", "建立日期", "最後更新日期"]
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"


def ensure_storage():
    if os.path.exists(DATA_XLSX):
        try:
            df = pd.read_excel(DATA_XLSX)
            df = normalize_df(df)
            save_data(df)
            return
        except Exception:
            pass

    if os.path.exists(DATA_CSV):
        try:
            df = pd.read_csv(DATA_CSV)
            df = normalize_df(df)
            save_data(df)
            return
        except Exception:
            pass

    df = pd.DataFrame(columns=COLUMNS)
    save_data(df)


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUMNS)

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = True if col == "狀態" else ""

    df = df[COLUMNS].copy()
    df["狀態"] = df["狀態"].apply(to_bool)

    for col in ["馬匹名字", "電郵地址", "建立日期", "最後更新日期"]:
        df[col] = df[col].astype(str).replace("nan", "").str.strip()

    return df


def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ["true", "1", "yes", "y", "checked", "是"]


@st.cache_data(ttl=2)
def load_data():
    ensure_storage()
    try:
        df = pd.read_excel(DATA_XLSX)
    except Exception:
        df = pd.read_csv(DATA_CSV)
    return normalize_df(df)


def save_data(df: pd.DataFrame):
    clean = normalize_df(df)
    clean.to_excel(DATA_XLSX, index=False)
    clean.to_csv(DATA_CSV, index=False, encoding="utf-8-sig")
    load_data.clear()


def add_horse(df: pd.DataFrame, horse_name: str, email_addr: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    horse_name = horse_name.strip()
    email_addr = email_addr.strip()

    mask = (
        df["馬匹名字"].astype(str).str.casefold() == horse_name.casefold()
    ) & (
        df["電郵地址"].astype(str).str.casefold() == email_addr.casefold()
    )

    if mask.any():
        idx = df[mask].index[0]
        df.loc[idx, "狀態"] = True
        if not str(df.loc[idx, "建立日期"]).strip():
            df.loc[idx, "建立日期"] = now
        df.loc[idx, "最後更新日期"] = now
        return df, "updated"

    new_row = pd.DataFrame([{
        "狀態": True,
        "馬匹名字": horse_name,
        "電郵地址": email_addr,
        "建立日期": now,
        "最後更新日期": now,
    }])

    return pd.concat([df, new_row], ignore_index=True), "added"


def normalize_horse_name(name: str) -> str:
    text = str(name).strip()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[+＊*]", "", text)
    text = re.sub(r"R\d+$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\d+$", "", text)
    text = text.replace("（退出）", "").replace("(退出)", "")
    return text.strip()


def fetch_hkjc_racecard_chinese(race_date: str, racecourse: str, race_no: str):
    params = urlencode({
        "racedate": race_date,
        "Racecourse": racecourse,
        "RaceNo": race_no
    })
    url = f"https://racing.hkjc.com/zh-hk/local/information/racecard?{params}"
    headers = {"User-Agent": USER_AGENT}

    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")

    horses = []
    reserve_horses = []
    seen_main = set()
    seen_reserve = set()

    all_horse_links = soup.find_all("a", href=re.compile(r"horseid=", re.IGNORECASE))

    in_reserve = False

    for a in all_horse_links:
        name = normalize_horse_name(a.get_text(strip=True))
        if not name or len(name) < 2:
            continue

        parent_text = ""
        for parent in a.parents:
            parent_text = parent.get_text()
            if "後備馬匹" in parent_text or "後 備 馬 批" in parent_text:
                in_reserve = True
                break
            if "我的排位表" in parent_text or "我 的 排 位 表" in parent_text:
                in_reserve = False
                break

        if in_reserve:
            if name not in seen_reserve:
                seen_reserve.add(name)
                reserve_horses.append(name)
        else:
            if name not in seen_main:
                seen_main.add(name)
                horses.append(name)

    page_title = soup.title.get_text(strip=True) if soup.title else "HKJC 中文排位表"

    return {
        "url": url,
        "title": page_title,
        "horses": horses,
        "reserve_horses": reserve_horses,
        "count": len(horses),
        "reserve_count": len(reserve_horses),
    }


def compare_local_with_racecard(local_df: pd.DataFrame, main_horses: list[str], reserve_horses: list[str]):
    active_df = local_df[local_df["狀態"].apply(to_bool)].copy()
    active_df["標準化馬名"] = active_df["馬匹名字"].apply(normalize_horse_name)

    main_set = {normalize_horse_name(x) for x in main_horses}
    reserve_set = {normalize_horse_name(x) for x in reserve_horses}

    active_df["列為正選"] = active_df["標準化馬名"].isin(main_set)
    active_df["列為後備"] = active_df["標準化馬名"].isin(reserve_set)

    matched_main = active_df[active_df["列為正選"]].copy()
    matched_reserve = active_df[active_df["列為後備"]].copy()
    unmatched = active_df[~active_df["列為正選"] & ~active_df["列為後備"]].copy()

    return matched_main, matched_reserve, unmatched, active_df


def fetch_hkjc_racecard_day_chinese(race_date: str, racecourse: str, max_races: int = 11):
    all_main = []
    all_reserve = []
    race_details = []

    for race_no in range(1, max_races + 1):
        try:
            result = fetch_hkjc_racecard_chinese(race_date, racecourse, str(race_no))

            if result["count"] == 0 and result["reserve_count"] == 0:
                continue

            race_details.append({
                "race_no": race_no,
                "main_horses": result["horses"],
                "reserve_horses": result["reserve_horses"],
                "url": result["url"],
                "title": result["title"],
            })

            for h in result["horses"]:
                all_main.append((race_no, h))

            for h in result["reserve_horses"]:
                all_reserve.append((race_no, h))

        except Exception:
            continue

    return {
        "race_details": race_details,
        "all_main": all_main,
        "all_reserve": all_reserve,
        "race_count": len(race_details),
    }


def compare_local_with_racecard_day(local_df: pd.DataFrame, all_main: list[tuple], all_reserve: list[tuple]):
    active_df = local_df[local_df["狀態"].apply(to_bool)].copy()
    active_df["標準化馬名"] = active_df["馬匹名字"].apply(normalize_horse_name)

    main_map = {}
    reserve_map = {}

    for race_no, horse_name in all_main:
        key = normalize_horse_name(horse_name)
        main_map.setdefault(key, []).append(race_no)

    for race_no, horse_name in all_reserve:
        key = normalize_horse_name(horse_name)
        reserve_map.setdefault(key, []).append(race_no)

    active_df["馬匹正選場次"] = active_df["標準化馬名"].apply(
        lambda x: ", ".join(str(n) for n in main_map.get(x, []))
    )
    active_df["列為後備場次"] = active_df["標準化馬名"].apply(
        lambda x: ", ".join(str(n) for n in reserve_map.get(x, []))
    )

    active_df["馬匹正選"] = active_df["馬匹正選場次"] != ""
    active_df["列為後備"] = active_df["列為後備場次"] != ""

    matched_main = active_df[active_df["馬匹正選"]].copy()
    matched_reserve = active_df[~active_df["馬匹正選"] & active_df["列為後備"]].copy()
    unmatched = active_df[~active_df["馬匹正選"] & ~active_df["列為後備"]].copy()

    return matched_main, matched_reserve, unmatched, active_df


def fetch_hkjc_entries_chinese(race_date: str):
    params = urlencode({"racedate": race_date})
    url = f"https://racing.hkjc.com/racing/information/Chinese/Racing/Entries.aspx?{params}"
    headers = {"User-Agent": USER_AGENT}

    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    horses = []
    seen = set()

    text_nodes = soup.find_all(string=True)

    for raw in text_nodes:
        raw = str(raw).strip()
        if not raw:
            continue

        cleaned = normalize_horse_name(raw)

        if 1 < len(cleaned) <= 12 and re.search(r"[\u4e00-\u9fff]", cleaned):
            if cleaned not in ["馬名", "後備馬匹", "退出", "後備", "報名表", "賽事資料", "賽馬資訊"]:
                if cleaned not in seen:
                    seen.add(cleaned)
                    horses.append(cleaned)

    page_title = soup.title.get_text(strip=True) if soup.title else "HKJC 中文報名表"

    return {
        "url": url,
        "title": page_title,
        "horses": horses,
        "count": len(horses),
    }


def compare_local_with_hkjc(local_df: pd.DataFrame, hkjc_horses: list[str]):
    active_df = local_df[local_df["狀態"].apply(to_bool)].copy()
    active_df["標準化馬名"] = active_df["馬匹名字"].apply(normalize_horse_name)

    hkjc_set = {normalize_horse_name(x) for x in hkjc_horses}

    active_df["是否出賽HKJC"] = active_df["標準化馬名"].isin(hkjc_set)

    matched = active_df[active_df["是否出賽HKJC"]].copy()
    unmatched = active_df[~active_df["是否出賽HKJC"]].copy()

    return matched, unmatched, active_df


st.title("🏇 馬匹出賽通知提示系統（Local + HKJC 配對版）")
st.caption("本地 localhost：horses.xlsx / horses.csv 儲存 + 香港賽馬會中文報名表名字配對")

st.info("此版本先使用 HKJC 中文報名表做配對，不需要 Google Cloud。")

with st.sidebar:
    st.markdown("## 📁 本地儲存")
    st.code(f"Excel: {os.path.abspath(DATA_XLSX)}\nCSV:   {os.path.abspath(DATA_CSV)}")
    st.markdown("## 🔎 配對說明")
    st.write("目前先用 HKJC 中文報名表做測試比對，之後可再升級排位表、正選/後備、email 通知。")

try:
    df_current = load_data()
except Exception as e:
    st.error(f"讀取本地資料失敗：{e}")
    st.stop()

st.subheader("新增追蹤馬匹")
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    horse_name = st.text_input("馬匹名字（建議輸入繁體中文）", placeholder="例如：勇敢孖寶")
with col2:
    email_addr = st.text_input("電郵地址", placeholder="例如：you@example.com")
with col3:
    st.write("")
    st.write("")
    add_btn = st.button("確定新增", width="stretch", type="primary")

if add_btn:
    if horse_name and email_addr:
        df_updated, action = add_horse(df_current.copy(), horse_name, email_addr)
        save_data(df_updated)
        if action == "added":
            st.success(f"🎉 已新增：{horse_name} → {email_addr}")
        else:
            st.success(f"♻️ 已更新並重新啟用：{horse_name} → {email_addr}")
        st.rerun()
    else:
        st.error("請同時輸入馬匹名字和電郵地址。")

st.markdown("---")
st.subheader("現時追蹤名單")
st.write("預設全部為已勾選；若你不想某匹馬列入下一次通知，可取消勾選『狀態』，再按儲存。")

if not df_current.empty:
    edited_df = st.data_editor(
        df_current,
        column_config={
            "狀態": st.column_config.CheckboxColumn("通知狀態", default=True),
            "馬匹名字": st.column_config.TextColumn("馬匹名字"),
            "電郵地址": st.column_config.TextColumn("電郵地址"),
            "建立日期": st.column_config.TextColumn("建立日期"),
            "最後更新日期": st.column_config.TextColumn("最後更新日期"),
        },
        disabled=["建立日期"],
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
    )

    c1, c2, c3 = st.columns(3)

    for_saving_df = edited_df.copy() if edited_df is not None else df_current.copy()

    with c1:
        if st.button("💾 更新並儲存", width="stretch"):
            for_saving_df = normalize_df(for_saving_df)
            for_saving_df["最後更新日期"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_data(for_saving_df)
            st.success("☁️ 本地 Excel / CSV 已成功更新及儲存。")
            st.rerun()

    with c2:
        if st.button("🔄 重新載入資料", width="stretch"):
            load_data.clear()
            st.rerun()

    with c3:
        st.metric("已勾選馬匹", int(for_saving_df["狀態"].apply(to_bool).sum()))
else:
    st.info("目前名單是空的，請先在上方新增第一匹馬。")


SHOW_PART3 = False

# -------------------------
# Part 2
# -------------------------
st.markdown("---")
st.subheader("Part 2：與 HKJC 中文報名表配對")

with st.expander("Step 1：輸入賽事日期（格式 YYYY/MM/DD）", expanded=True):
    race_date = st.text_input("賽事日期", value=datetime.now().strftime("%Y/%m/%d"))
    match_btn = st.button("🔍 測試比對 HKJC 中文報名表", type="primary")

if match_btn:
    if df_current.empty:
        st.warning("請先新增至少一匹馬到本地名單。")
    else:
        try:
            result = fetch_hkjc_entries_chinese(race_date)
            matched_df, unmatched_df, active_df = compare_local_with_hkjc(df_current, result["horses"])

            st.success(f"已成功抓取 HKJC 中文報名表，共找到 {result['count']} 個馬名。")
            st.markdown(f"**資料來源：** [{result['title']}]({result['url']})")

            a, b, c = st.columns(3)
            a.metric("本地已勾選馬匹", len(active_df))
            b.metric("HKJC 報名表馬匹", result["count"])
            c.metric("成功列為報名", len(matched_df))

            st.markdown("### ✅ 報名馬匹")
            if not matched_df.empty:
                st.dataframe(
                    matched_df[["馬匹名字", "電郵地址", "建立日期", "最後更新日期"]],
                    width="stretch",
                    hide_index=True
                )
            else:
                st.info("今次未有列為報名馬匹。")

            st.markdown("### ❌ 未報名馬匹")
            if not unmatched_df.empty:
                st.dataframe(
                    unmatched_df[["馬匹名字", "電郵地址"]],
                    width="stretch",
                    hide_index=True
                )
            else:
                st.success("所有已勾選馬匹都已在 HKJC 報名表中找到。")

            with st.expander("查看 HKJC 抓到的全部馬匹名字"):
                st.write(result["horses"])

        except Exception as e:
            st.error(f"抓取或比對失敗：{e}")


# -------------------------
# Part 3
# -------------------------
if SHOW_PART3:
    st.markdown("---")
    st.subheader("Part 3：與 HKJC 中文排位表配對")

    with st.expander("Step 2：輸入排位表參數", expanded=True):
        rc_col1, rc_col2, rc_col3 = st.columns(3)

        with rc_col1:
            rc_date = st.text_input("賽事日期（排位表）", value=datetime.now().strftime("%Y/%m/%d"))
        with rc_col2:
            racecourse = st.selectbox("場地", ["HV", "ST"], index=0)
        with rc_col3:
            race_no = st.text_input("場次", value="1")

    racecard_btn = st.button("📋 測試比對 HKJC 中文排位表", type="primary")

    if racecard_btn:
        if df_current.empty:
            st.warning("請先新增至少一匹馬到本地名單。")
        else:
            try:
                rc_result = fetch_hkjc_racecard_chinese(rc_date, racecourse, race_no)
                matched_main, matched_reserve, unmatched_rc, active_df_rc = compare_local_with_racecard(
                    df_current,
                    rc_result["horses"],
                    rc_result["reserve_horses"]
                )

                st.success(
                    f"已成功抓取 HKJC 中文排位表：正選 {rc_result['count']} 匹，後備 {rc_result['reserve_count']} 匹。"
                )
                st.markdown(f"**資料來源：** [{rc_result['title']}]({rc_result['url']})")

                r1, r2, r3, r4 = st.columns(4)
                r1.metric("本地已勾選馬匹", len(active_df_rc))
                r2.metric("出賽正選", len(matched_main))
                r3.metric("列為後備", len(matched_reserve))
                r4.metric("未出賽", len(unmatched_rc))

                st.markdown("### ✅ 馬匹正選")
                if not matched_main.empty:
                    st.dataframe(
                        matched_main[["馬匹名字", "電郵地址", "建立日期", "最後更新日期"]],
                        width="stretch",
                        hide_index=True
                    )
                else:
                    st.info("今次沒有列為正選馬匹。")

                st.markdown("### 🟡 列為後備")
                if not matched_reserve.empty:
                    st.dataframe(
                        matched_reserve[["馬匹名字", "電郵地址", "建立日期", "最後更新日期"]],
                        width="stretch",
                        hide_index=True
                    )
                else:
                    st.info("今次沒有列為後備馬匹。")

                st.markdown("### ❌ 未出賽")
                if not unmatched_rc.empty:
                    st.dataframe(
                        unmatched_rc[["馬匹名字", "電郵地址"]],
                        width="stretch",
                        hide_index=True
                    )
                else:
                    st.success("所有已勾選馬匹都已在排位表中找到。")

                with st.expander("查看排位表抓到的正選馬匹"):
                    st.write(rc_result["horses"])

                with st.expander("查看排位表抓到的後備馬匹"):
                    st.write(rc_result["reserve_horses"])

            except Exception as e:
                st.error(f"排位表抓取或比對失敗：{e}")


# -------------------------
# Part 4：整個賽日自動掃描（1 至 11 場）+ 密碼學自動引爆發信
# -------------------------
st.markdown("---")
st.subheader("Part 4：整個賽日自動掃描排位表（1 至 11 場）")

with st.expander("Step 4：輸入整個賽日參數（不用輸入場次）", expanded=True):
    day_col1, day_col2, day_col3 = st.columns(3)

    with day_col1:
        day_date = st.text_input("賽事日期（整日掃描）", value=datetime.now().strftime("%Y/%m/%d"))
    with day_col2:
        day_racecourse = st.selectbox("場地（整日掃描）", ["HV", "ST"], index=0, key="day_racecourse")
    with day_col3:
        max_races = st.number_input("最多掃描場次", min_value=1, max_value=11, value=11, step=1)

    day_scan_btn = st.button("🧭 掃描整個賽日排位表", type="primary")

if day_scan_btn:
    if df_current.empty:
        st.warning("請先新增至少一匹馬到本地名單。")
    else:
        try:
            day_result = fetch_hkjc_racecard_day_chinese(day_date, day_racecourse, max_races=int(max_races))

            matched_main_day, matched_reserve_day, unmatched_day, active_df_day = compare_local_with_racecard_day(
                df_current,
                day_result["all_main"],
                day_result["all_reserve"]
            )

            st.success(f"已成功掃描整個賽日，共找到 {day_result['race_count']} 場有資料的排位表。")

            d1, d2, d3, d4 = st.columns(4)
            d1.metric("本地已勾選馬匹", len(active_df_day))
            d2.metric("出賽正選", len(matched_main_day))
            d3.metric("列為後備", len(matched_reserve_day))
            d4.metric("未出賽", len(unmatched_day))

            st.markdown("### ✅ 出賽正選（顯示出賽場次）")
            if not matched_main_day.empty:
                st.dataframe(
                    matched_main_day[["馬匹名字", "電郵地址", "馬匹正選場次", "列為後備場次", "建立日期", "最後更新日期"]],
                    width="stretch",
                    hide_index=True
                )
            else:
                st.info("整個賽日沒有列為正選馬匹。")

            st.markdown("### 🟡 列為後備（顯示後備場次）")
            if not matched_reserve_day.empty:
                st.dataframe(
                    matched_reserve_day[["馬匹名字", "電郵地址", "馬匹正選場次", "列為後備場次", "建立日期", "最後更新日期"]],
                    width="stretch",
                    hide_index=True
                )
            else:
                st.info("整個賽日沒有列為後備馬匹。")

            st.markdown("### ❌ 未出賽")
            if not unmatched_day.empty:
                st.dataframe(
                    unmatched_day[["馬匹名字", "電郵地址"]],
                    width="stretch",
                    hide_index=True
                )
            else:
                st.success("所有已勾選馬匹都已在整個賽日排位表中找到。")

            with st.expander("查看每一場抓到的資料"):
                for item in day_result["race_details"]:
                    st.markdown(f"**第 {item['race_no']} 場** |  [{item['title']}]({item['url']})")
                    st.write("正選：", item["main_horses"])
                    st.write("後備：", item["reserve_horses"])
                    st.markdown("---")

            # 🎯 垂直對齊條件：12 個空格，與 with st.expander 完美同級
            # ────────────────────────────────────────────────────────
            st.markdown("---")
            st.subheader("📬 智能電郵通知系統")
            
            final_running = []
            for _, row in matched_main_day.iterrows():
                final_running.append((row["馬匹名字"], row["馬匹正選場次"]))
                
            final_standby = []
            for _, row in matched_reserve_day.iterrows():
                final_standby.append((row["馬匹名字"], row["列為後備場次"]))
                
            final_not_arranged = unmatched_day["馬匹名字"].tolist()
            
            # 智能自動覆寫中轉站
            with open("race_data.py", "w", encoding="utf-8") as f:
                f.write("# 由 app.py 自動生成的即時賽馬數據中轉站\n")
                f.write(f'check_date = "{day_date}"\n\n')
                f.write(f"running_list = {final_running}\n\n")
                f.write(f"standby_list = {final_standby}\n\n")
                f.write(f"not_arranged_list = {final_not_arranged}\n")
                
            st.caption("📝 今日掃描大數據已成功自動覆寫至 `race_data.py`。")
            
            with st.spinner("📧 正在同步喚醒 notify_test.py 進行安全發信..."):
                try:
                    import notify_test
                    import importlib
                    importlib.reload(notify_test)
                    
                    if len(final_running) > 0 or len(final_standby) > 0:
                        st.success("🎉 自動化任務完美閉環！出賽通知電郵已成功觸發寄出！")
                        st.balloons()
                    else:
                        st.info("😎 智慧過濾：今日無任何追蹤馬匹正選或後備出賽，電郵未觸發，保持信箱清爽。")
                        
                except Exception as mail_err:
                    st.error(f"❌ 調用發信程式失敗：{mail_err}")
            # ────────────────────────────────────────────────────────

        except Exception as e:
            st.error(f"整個賽日掃描失敗：{e}")


st.markdown("---")

with st.expander("目前資料欄位說明"):
    st.markdown("""
- **狀態**：是否列入下一次通知配對
- **馬匹名字**：建議用繁體中文輸入
- **電郵地址**：日後發送通知用
- **建立日期**：首次加入時間
- **最後更新日期**：最近一次修改時間
    """)

with st.expander("下一步可做什麼"):
    st.markdown("""
1. 改抓 HKJC 中文排位表
2. 區分正選 / 後備
3. 將出賽結果寫回本地 Excel
4. 再加入 email通知
    """)