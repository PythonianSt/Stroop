import streamlit as st
import pandas as pd
import random
import time
import base64
from io import BytesIO, StringIO
from datetime import datetime
import pytz
import qrcode
from github import Github, GithubException

st.set_page_config(page_title="Incongruent Stroop Test", page_icon="🧠", layout="centered")

BKK = pytz.timezone("Asia/Bangkok")

WORDS = {
    "แดง": "#E53935",
    "น้ำเงิน": "#1E88E5",
    "เขียว": "#43A047",
    "เหลือง": "#FDD835",
    "ม่วง": "#8E24AA",
    "ส้ม": "#FB8C00",
}

COLOR_NAMES = list(WORDS.keys())


def now_bkk():
    return datetime.now(BKK).strftime("%Y-%m-%d %H:%M:%S")


def get_secret(name, default=None):
    try:
        return st.secrets[name]
    except Exception:
        return default


GITHUB_TOKEN = get_secret("GITHUB_TOKEN")
GITHUB_REPO = get_secret("GITHUB_REPO")
GITHUB_BRANCH = get_secret("GITHUB_BRANCH", "main")
CSV_PATH = get_secret("CSV_PATH", "stroop_results.csv")
ADMIN_CODE = get_secret("ADMIN_CODE", "Admin26")


def github_repo():
    if not GITHUB_TOKEN or not GITHUB_REPO:
        raise RuntimeError("Missing GitHub secrets.")
    gh = Github(GITHUB_TOKEN)
    return gh.get_repo(GITHUB_REPO)


def load_csv_from_github():
    repo = github_repo()
    try:
        file = repo.get_contents(CSV_PATH, ref=GITHUB_BRANCH)
        content = base64.b64decode(file.content).decode("utf-8")
        if content.strip() == "":
            return pd.DataFrame(), file
        return pd.read_csv(StringIO(content)), file
    except GithubException as e:
        if e.status == 404:
            return pd.DataFrame(), None
        raise e


def save_row_to_github(row):
    repo = github_repo()
    df_old, file = load_csv_from_github()
    df_new = pd.concat([df_old, pd.DataFrame([row])], ignore_index=True)

    csv_buffer = StringIO()
    df_new.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    new_content = csv_buffer.getvalue()

    commit_msg = f"Add Stroop result {row.get('student_id', '')} {row.get('timestamp_bkk', '')}"

    if file is None:
        repo.create_file(
            path=CSV_PATH,
            message=commit_msg,
            content=new_content,
            branch=GITHUB_BRANCH,
        )
    else:
        repo.update_file(
            path=CSV_PATH,
            message=commit_msg,
            content=new_content,
            sha=file.sha,
            branch=GITHUB_BRANCH,
        )


def make_incongruent_items(n_items=20):
    items = []
    for i in range(n_items):
        word = random.choice(COLOR_NAMES)
        ink = random.choice([c for c in COLOR_NAMES if c != word])
        items.append({
            "no": i + 1,
            "word": word,
            "ink": ink,
            "hex": WORDS[ink],
        })
    return items


def make_qr_png(data):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def reset_test():
    st.session_state.items = make_incongruent_items(st.session_state.n_items)
    st.session_state.answers = {}
    st.session_state.start_time = time.time()
    st.session_state.finished = False


st.title("🧠 Incongruent Stroop Test")
st.caption("ให้อ่าน “สีของตัวอักษร” ไม่ใช่อ่านคำ")

tab_test, tab_qr, tab_admin = st.tabs(["ทดสอบ", "สร้าง QR", "Admin"])

with tab_test:
    st.subheader("ข้อมูลผู้ทำแบบทดสอบ")

    student_id = st.text_input(
        "Student ID / รหัสนักศึกษา",
        placeholder="เช่น 6612345678",
    )

    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("อายุ", min_value=10, max_value=100, value=19)
    with col2:
        gender = st.selectbox("เพศ", ["", "ชาย", "หญิง", "อื่น ๆ / ไม่ระบุ"])

    st.session_state.n_items = st.selectbox("จำนวนข้อ", [10, 20, 30, 40], index=1)

    if "items" not in st.session_state:
        st.session_state.items = make_incongruent_items(st.session_state.n_items)
        st.session_state.answers = {}
        st.session_state.start_time = None
        st.session_state.finished = False

    col_start, col_reset = st.columns(2)

    with col_start:
        if st.button("เริ่ม / สุ่มชุดใหม่", type="primary"):
            if not student_id.strip():
                st.warning("กรุณาใส่ Student ID ก่อนเริ่ม")
            else:
                reset_test()
                st.rerun()

    with col_reset:
        if st.button("ล้างคำตอบ"):
            st.session_state.answers = {}
            st.session_state.start_time = time.time()
            st.session_state.finished = False
            st.rerun()

    if st.session_state.start_time is None:
        st.info("กด “เริ่ม / สุ่มชุดใหม่” ก่อนทำแบบทดสอบ")
    else:
        st.divider()
        st.subheader("คำสั่ง")
        st.write("ดูคำที่ปรากฏ แล้วเลือก **สีของตัวอักษร** ให้ถูกต้อง")

        for item in st.session_state.items:
            st.markdown(
                f"""
                <div style="font-size:42px; font-weight:700; color:{item['hex']};
                            text-align:center; padding:8px;">
                    {item['word']}
                </div>
                """,
                unsafe_allow_html=True,
            )

            ans = st.radio(
                f"ข้อ {item['no']}: ตัวอักษรนี้เป็นสีอะไร?",
                COLOR_NAMES,
                key=f"ans_{item['no']}",
                horizontal=True,
                index=None,
            )
            st.session_state.answers[item["no"]] = ans

        answered = sum(1 for v in st.session_state.answers.values() if v is not None)

        st.write(f"ตอบแล้ว {answered}/{len(st.session_state.items)} ข้อ")

        if st.button("ส่งคำตอบ", type="primary"):
            if answered < len(st.session_state.items):
                st.warning("กรุณาตอบให้ครบทุกข้อ")
            else:
                end_time = time.time()
                duration_sec = round(end_time - st.session_state.start_time, 2)

                correct = 0
                wrong_items = []

                for item in st.session_state.items:
                    ans = st.session_state.answers.get(item["no"])
                    is_correct = ans == item["ink"]
                    correct += int(is_correct)
                    if not is_correct:
                        wrong_items.append(
                            f"{item['no']}:{item['word']}/{item['ink']}/ตอบ{ans}"
                        )

                total = len(st.session_state.items)
                errors = total - correct
                accuracy = round(correct / total * 100, 2)
                correct_per_min = round(correct / duration_sec * 60, 2) if duration_sec > 0 else None

                row = {
                    "timestamp_bkk": now_bkk(),
                    "student_id": student_id.strip(),
                    "age": age,
                    "gender": gender,
                    "test_type": "incongruent_stroop",
                    "n_items": total,
                    "correct": correct,
                    "errors": errors,
                    "accuracy_percent": accuracy,
                    "duration_sec": duration_sec,
                    "correct_per_min": correct_per_min,
                    "wrong_items": "; ".join(wrong_items),
                }

                try:
                    save_row_to_github(row)
                    st.success("บันทึกผลลง GitHub CSV สำเร็จ")
                except Exception as e:
                    st.error(f"บันทึก GitHub ไม่สำเร็จ: {e}")

                st.metric("ถูก", f"{correct}/{total}")
                st.metric("Accuracy", f"{accuracy}%")
                st.metric("เวลา", f"{duration_sec} วินาที")
                st.metric("Correct/min", correct_per_min)

                if errors > 0:
                    st.caption("รายการที่ตอบผิด")
                    st.write(wrong_items)

with tab_qr:
    st.subheader("สร้าง QR สำหรับนักศึกษา")

    base_url = st.text_input(
        "URL ของ Streamlit app",
        placeholder="https://your-app.streamlit.app",
    )
    qr_student_id = st.text_input("Student ID สำหรับ QR", key="qr_student_id")

    if base_url and qr_student_id:
        qr_url = f"{base_url}?student_id={qr_student_id}"
        img_bytes = make_qr_png(qr_url)
        st.image(img_bytes, caption=qr_url, width=220)
        st.download_button(
            "ดาวน์โหลด QR PNG",
            img_bytes,
            file_name=f"stroop_qr_{qr_student_id}.png",
            mime="image/png",
        )

with tab_admin:
    st.subheader("Admin")

    code = st.text_input("Admin code", type="password")

    if code == ADMIN_CODE:
        try:
            df, _ = load_csv_from_github()
            st.success(f"โหลดข้อมูลสำเร็จ: {len(df)} rows")

            if not df.empty:
                st.dataframe(df, use_container_width=True)
                st.download_button(
                    "ดาวน์โหลด CSV",
                    df.to_csv(index=False, encoding="utf-8-sig"),
                    file_name="stroop_results.csv",
                    mime="text/csv",
                )
            else:
                st.info("ยังไม่มีข้อมูล")
        except Exception as e:
            st.error(f"โหลดข้อมูลไม่สำเร็จ: {e}")
    elif code:
        st.error("รหัสไม่ถูกต้อง")
