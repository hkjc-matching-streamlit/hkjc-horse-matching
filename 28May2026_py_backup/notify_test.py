import smtplib
import ssl
from email.message import EmailMessage

# 🏭 這裡就是從「倉庫」拿原料
from race_data import check_date, running_list, standby_list, not_arranged_list

SENDER_EMAIL = "vgfrankie@gmail.com"
APP_PASSWORD = "nlbwcjbszmedvfbb"  # 你的 16 位金鑰密碼已經正確在陣
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

# --- 下面是判斷觸發與寄信邏輯 ---
running_count = len(running_list)
standby_count = len(standby_list)

if running_count > 0 or standby_count > 0:
    selected_count = running_count + standby_count + len(not_arranged_list)
    subject = f"HKJC Alert - {check_date} - {running_count}正選 / {standby_count}後備"
    
    # 呼叫上面的加工機器生成內文
    email_body = build_hkjc_email_body(check_date, selected_count, running_list, standby_list, not_arranged_list)
    
    # 📦 封裝電子郵件物件
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.set_content(email_body)
    
    # 🔒 建立安全 SSL 連線環境
    context = ssl.create_default_context()
    
    # 🚀【就是這段！實質發送的點火引擎】
    try:
        print("📡 偵測到有出賽馬匹，正在建立安全連線...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            print("🔐 Gmail 驗證成功，正在發送密碼學信件...")
            smtp.send_message(msg)
        print("🎉 [Success] 電郵已順利跨海送達您的 msn.com 信箱！")
    except Exception as e:
        print(f"❌ [Error] 郵件發送失敗，原因: {e}")

else:
    print(f"😎 智慧過濾：今日（{check_date}）無任何追蹤馬匹出賽，未觸發寄信。")