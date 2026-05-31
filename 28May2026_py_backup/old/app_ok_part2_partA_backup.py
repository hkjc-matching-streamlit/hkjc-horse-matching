import os
import re
from datetime import datetime
from urllib.parse import urlencode

import pandas as pd
import requests
import streamlit as st
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

    active_df["是否命中HKJC"] = active_df["標準化馬名"].isin(hkjc_set)

    matched = active_df[active_df["是否命中HKJC"]].copy()
    unmatched = active_df[~active_df["是否命中HKJC"]].copy()

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
    add_btn = st.button("確定新增", use_container_width=True, type="primary")

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
        use_container_width=True,
        hide_index=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("💾 更新並儲存", use_container_width=True):
            edited_df = normalize_df(edited_df)
            edited_df["最後更新日期"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_data(edited_df)
            st.success("☁️ 本地 Excel / CSV 已成功更新及儲存。")
            st.rerun()

    with c2:
        if st.button("🔄 重新載入資料", use_container_width=True):
            load_data.clear()
            st.rerun()

    with c3:
        st.metric("已勾選馬匹", int(edited_df["狀態"].apply(to_bool).sum()))
else:
    st.info("目前名單是空的，請先在上方新增第一匹馬。")

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
            c.metric("成功命中", len(matched_df))

            st.markdown("### ✅ 命中馬匹")
            if not matched_df.empty:
                st.dataframe(
                    matched_df[["馬匹名字", "電郵地址", "建立日期", "最後更新日期"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("今次未有命中馬匹。")

            st.markdown("### ❌ 未命中馬匹")
            if not unmatched_df.empty:
                st.dataframe(
                    unmatched_df[["馬匹名字", "電郵地址"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.success("所有已勾選馬匹都已在 HKJC 報名表中找到。")

            with st.expander("查看 HKJC 抓到的全部馬匹名字"):
                st.write(result["horses"])

        except Exception as e:
            st.error(f"抓取或比對失敗：{e}")

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
3. 將命中結果寫回本地 Excel
4. 再加入 email 通知
    """)