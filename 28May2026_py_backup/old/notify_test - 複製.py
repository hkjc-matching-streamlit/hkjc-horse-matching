import smtplib
import ssl
from email.message import EmailMessage

SENDER_EMAIL = "vgfrankie@gmail.com"
APP_PASSWORD = "XXXXXXXXXXXX"
RECEIVER_EMAIL = "vgfrankie@msn.com"


def build_hkjc_email_body(check_date, selected_count, running_list, standby_list, not_arranged_list, local_url="http://127.0.0.1:8501"):
    running_count = len(running_list)
    standby_count = len(standby_list)
    not_arranged_count = len(not_arranged_list)

    running_text = "\n".join([f"- {horse_name} — 第 {race_no} 場" for horse_name, race_no in running_list]) if running_list else "- 無"
    standby_text = "\n".join([f"- {horse_name} — 第 {race_no} 場（後備）" for horse_name, race_no in standby_list]) if standby_list else "- 無"
    not_arranged_text = "\n".join([f"- {horse_name}" for horse_name in not_arranged_list]) if not_arranged_list else "- 無"

    body = f"""HKJC 馬匹出賽提醒

日期：{check_date}
已勾選馬匹：{selected_count} 匹

正選出賽：{running_count} 匹
後備：{standby_count} 匹
未安排出賽：{not_arranged_count} 匹

正選名單：
{running_text}

後備名單：
{standby_text}

未安排名單：
{not_arranged_text}

快速連結：
HKJC 官方頁面：
https://racing.hkjc.com/

Local view：
{local_url}
"""
    return body


from race_data import check_date, running_list, standby_list, not_arranged_list





selected_count = len(running_list) + len(standby_list) + len(not_arranged_list)

subject = f"HKJC Alert - {check_date} - {len(running_list)}正選 / {len(standby_list)}後備 / {len(not_arranged_list)}未安排"

email_body = build_hkjc_email_body(
    check_date,
    selected_count,
    running_list,
    standby_list,
    not_arranged_list
)

msg = EmailMessage()
msg["Subject"] = subject
msg["From"] = SENDER_EMAIL
msg["To"] = RECEIVER_EMAIL
msg.set_content(email_body)

context = ssl.create_default_context()

with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
    smtp.login(SENDER_EMAIL, APP_PASSWORD)
    smtp.send_message(msg)

print("Test email sent successfully.")