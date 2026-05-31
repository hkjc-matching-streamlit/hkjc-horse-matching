import os
from datetime import datetime
import pandas as pd
import streamlit as st

st.set_page_config(page_title="馬匹出賽通知提示系統", page_icon="🏇", layout="wide")

DATA_XLSX = "horses.xlsx"
DATA_CSV = "horses.csv"
COLUMNS = ["狀態", "馬匹名字", "電郵地址", "建立日期", "最後更新日期"]


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
            if col == "狀態":
                df[col] = True
            else:
                df[col] = ""

    df = df[COLUMNS].copy()
    df["狀態"] = df["狀態"].apply(to_bool)
    df["馬匹名字"] = df["馬匹名字"].astype(str).str.strip()
    df["電郵地址"] = df["電郵地址"].astype(str).str.strip()
    df["建立日期"] = df["建立日期"].astype(str).replace("nan", "")
    df["最後更新日期"] = df["最後更新日期"].astype(str).replace("nan", "")
    return df


def to_bool(value):
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    return s in ["true", "1", "yes", "y", "checked", "是"]


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
        df["馬匹名字"].astype(str).str.strip().str.casefold() == horse_name.casefold()
    ) & (
        df["電郵地址"].astype(str).str.strip().str.casefold() == email_addr.casefold()
    )

    if mask.any():
        idx = df[mask].index[0]
        df.loc[idx, "狀態"] = True
        if not str(df.loc[idx, "建立日期"]).strip() or str(df.loc[idx, "建立日期"]).strip() == "nan":
            df.loc[idx, "建立日期"] = now
        df.loc[idx, "最後更新日期"] = now
        return df, "updated"

    new_row = pd.DataFrame([
        {
            "狀態": True,
            "馬匹名字": horse_name,
            "電郵地址": email_addr,
            "建立日期": now,
            "最後更新日期": now,
        }
    ])
    df = pd.concat([df, new_row], ignore_index=True)
    return df, "added"


st.title("🏇 馬匹出賽通知提示系統（Local Excel / CSV 版）")
st.caption("學習專案：本地 localhost 儲存，使用 horses.xlsx + horses.csv，同步更新")

st.info("目前版本不依賴 Google Cloud 或 JSON key。資料會儲存在專案資料夾內的 horses.xlsx 與 horses.csv。")

with st.sidebar:
    st.markdown("## 📁 儲存設定")
    st.code(f"Excel: {os.path.abspath(DATA_XLSX)}\nCSV:   {os.path.abspath(DATA_CSV)}")
    st.markdown("## 🧭 下一階段")
    st.write("完成本地版後，可再加入 HKJC / GraphQL 配對、email 提示、雲端部署。")

# 讀取目前資料
try:
    df_current = load_data()
except Exception as e:
    st.error(f"讀取本地資料失敗：{e}")
    st.stop()

# --- 介面 1：輸入區 ---
st.subheader("新增追蹤馬匹")
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    horse_name = st.text_input("馬匹名字", placeholder="例如：你的心愛馬匹")
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

# --- 介面 2：顯示與修改清單 ---
st.subheader("現時追蹤名單")
st.write("預設全部為已勾選；若你不想某匹馬列入下一次通知，可取消勾選「狀態」，再按儲存。")

if not df_current.empty:
    edited_df = st.data_editor(
        df_current,
        column_config={
            "狀態": st.column_config.CheckboxColumn(
                "通知狀態",
                help="勾選代表下一次排位日會進行通知",
                default=True,
            ),
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

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("💾 更新並儲存", use_container_width=True):
            edited_df = normalize_df(edited_df)
            edited_df["最後更新日期"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_data(edited_df)
            st.success("☁️ 本地 Excel / CSV 已成功更新及儲存。")
            st.rerun()

    with col_b:
        if st.button("🔄 重新載入資料", use_container_width=True):
            load_data.clear()
            st.rerun()

    with col_c:
        active_count = int(edited_df["狀態"].apply(to_bool).sum())
        st.metric("已勾選馬匹", active_count)

    st.markdown("### 匯出")
    excel_bytes = open(DATA_XLSX, "rb").read()
    csv_bytes = open(DATA_CSV, "rb").read()

    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "⬇️ 下載 Excel (.xlsx)",
            data=excel_bytes,
            file_name="horses.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            "⬇️ 下載 CSV",
            data=csv_bytes,
            file_name="horses.csv",
            mime="text/csv",
            use_container_width=True,
        )
else:
    st.info("目前名單是空的，請先在上方新增第一匹馬。")

st.markdown("---")

with st.expander("目前資料欄位說明"):
    st.markdown("""
- **狀態**：是否列入下一次通知配對
- **馬匹名字**：你的追蹤名單核心欄位
- **電郵地址**：日後發送通知用
- **建立日期**：首次加入時間
- **最後更新日期**：最近一次修改時間
    """)

with st.expander("下一步可做什麼"):
    st.markdown("""
1. 接入香港賽馬會資料 / GraphQL API
2. 將出賽名單與本地 horses.xlsx 做名字比對
3. 顯示「正選 / 後備 / 未匹配」結果
4. 日後再加入 email 提示與自動化排程
    """)