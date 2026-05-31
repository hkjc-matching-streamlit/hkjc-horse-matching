import streamlit as st
import smtplib
import ssl
from email.message import EmailMessage

# 🏭 這裡就是從「倉庫」拿原料
from race_data import check_date, running_list, standby_list, not_arranged_list

sender_email = st.secrets["GMAIL_SENDER"]
app_password = st.secrets["GMAIL_APP_PASSWORD"]
receiver_email = st.secrets["RECEIVER_EMAIL"]


def build_hkjc_email_body(
    check_date,
    selected_count,
    running_list,
    standby_list,
    not_arranged_list,
    local_url="http://127.0.0.1:8501",
):
    running_count = len(running_list)
    standby_count = len(standby_list)
    not_arranged_count = len(not_arranged_list)

    running_text = (
        "\n".join([f"- {horse_name} — 第 {race_no} 場" for horse_name, race_no in running_list])
        if running_list
        else "- 無"
    )
    standby_text = (
        "\n".join([f"- {horse_name} — 第 {race_no} 場（後備）" for horse_name, race_no in standby_list])
        if standby_list
        else "- 無"
    )
    not_arranged_text = (
        "\n".join([f"- {horse_name}" for horse_name in not_arranged_list])
        if not_arranged_list
        else "- 無"
    )

    body = f"""HKJC 馬匹出賽提醒

日期：{check_date}
已勾選馬匹：{selected_count} 匹

正選出賽：{running_count} 匹
後備：請參看備註
未安排出賽：{not_arranged_count} 匹

正選名單：
{running_text}

後備名單：請參看備註

未安排名單：
{not_arranged_text}

快速連結：
HKJC 官方頁面：
https://racing.hkjc.com/

Local view：
{local_url}

備註：你所追蹤的馬匹有機會列為後備，因此未必會在本電郵顯示；最終是否列為正選，請於賽馬日自行查核作實。
"""
    return body


# --- 下面是判斷觸發與寄信邏輯 ---
running_count = len(running_list)
standby_count = len(standby_list)

if running_count > 0 or standby_count > 0:
    selected_count = running_count + standby_count + len(not_arranged_list)
    subject = f"HKJC Alert - {check_date} - {running_count}正選 / {standby_count}後備"

    email_body = build_hkjc_email_body(
        check_date,
        selected_count,
        running_list,
        standby_list,
        not_arranged_list,
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg.set_content(email_body)

    context = ssl.create_default_context()

    try:
        st.write("DEBUG: notify_test 進入寄信流程")
        st.write("DEBUG subject:", subject)
        st.write("DEBUG to:", receiver_email)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
            smtp.login(sender_email, app_password)
            st.write("DEBUG: Gmail login 成功")
            smtp.send_message(msg)

        st.success("🎉 notify_test：正式通知郵件已送出")
    except Exception as e:
        st.error(f"❌ notify_test：發信錯誤: {e}")

else:
    st.info(f"😎 智慧過濾：今日（{check_date}）無任何追蹤馬匹出賽，未觸發寄信。")