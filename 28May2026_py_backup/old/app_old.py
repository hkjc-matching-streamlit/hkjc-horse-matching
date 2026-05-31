import streamlit as st
#from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.title("🏇 馬匹出賽通知提示系統 (雲端升級版)")
st.write("學習專案 - 雲端試算表實時同步")

# 📢 請在這裡貼上你 Google Drive 內那份綠色十字試算表的「完整網址」
# (記得把下面這行引號內的網址，換成你自己的網址！)
URL = "https://docs.google.com/spreadsheets/d/19Ne1YIGfLCUxbtiuBgLVso-TOYhXKoRd7N8D-FPtK84/edit?gid=2050700819#gid=2050700819"

# 建立 Google Sheets 雲端連線
#conn = st.connection("gsheets", type=GSheetsConnection)

# 讀取雲端最新資料
try:
    df_current = conn.read(spreadsheet=URL, ttl="0d") # ttl="0d" 代表每次都即時讀取，不留緩存
except Exception:
    # 如果雲端是完全空白的，建立預設欄位
    df_current = pd.DataFrame(columns=["狀態", "馬匹名字", "電郵地址"])

# --- 介面 1：輸入介面 ---
st.subheader("新增追蹤馬匹")
col1, col2 = st.columns(2)

with col1:
    horse_name = st.text_input("馬匹名字", placeholder="例如：你的心愛馬匹")
with col2:
    email_addr = st.text_input("電郵地址", placeholder="例如：ai@kissigndesign.com")

if st.button("確定新增"):
    if horse_name and email_addr:
        # 新增一行新資料
        new_data = pd.DataFrame([{"狀態": True, "馬匹名字": horse_name, "電郵地址": email_addr}])
        df_updated = pd.concat([df_current, new_data], ignore_index=True)
        
        # 實時寫入雲端 Google Sheets！
        conn.update(spreadsheet=URL, data=df_updated)
        st.success(f"🎉 成功同步到雲端：{horse_name} -> {email_addr}")
        st.rerun()
    else:
        st.error("請同時輸入馬匹名字和電郵地址！")

st.markdown("---")

# --- 介面 2：顯示與修改雲端清單 ---
st.subheader("現時雲端追蹤名單")
st.write("提示：勾選完畢或刪除整行後，請點擊下方按鈕同步回雲端。")

if not df_current.empty:
    # 神級資料編輯器
    edited_df = st.data_editor(
        df_current,
        column_config={
            "狀態": st.column_config.CheckboxColumn(
                "通知狀態",
                help="勾選代表下一次排位日會進行通知",
                default=True,
            )
        },
        disabled=["馬匹名字", "電郵地址"],
        num_rows="dynamic",
        use_container_width=True
    )

    # 按鈕：儲存修改回雲端
    if st.button("💾 更新並儲存到 Google Drive 雲端"):
        conn.update(spreadsheet=URL, data=edited_df)
        st.success("☁️ Google Drive 雲端試算表已成功 Update 及 Save！")
        st.rerun()
else:
    st.info("目前雲端名單空空如也，請在上方新增第一隻馬匹。")