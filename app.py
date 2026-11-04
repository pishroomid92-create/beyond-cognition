import streamlit as st
import json
import uuid
from supabase import create_client

st.set_page_config(
    page_title="فراتر از شناخت",
    page_icon="🧠",
    layout="wide"
)


# اتصال به پایگاه داده
@st.cache_resource
def get_database():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


try:
    db = get_database()
    st.success("اتصال به حافظه دائمی برقرار است.")
except Exception as e:
    st.error("خطا در اتصال به پایگاه داده:")
    st.code(str(e))
    st.stop()


# دریافت اطلاعات
def load_records():
    result = (
        db.table("research_records")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


# ذخیره اطلاعات
def save_record(record):
    db.table("research_records").insert(record).execute()


# عنوان سامانه
st.title("🧠 فراتر از شناخت")
st.caption(
    "Beyond Cognition | Human–AI Research System"
)

st.divider()


# خواندن حافظه
try:
    records = load_records()
except Exception as e:
    st.error("خطا در خواندن حافظه پژوهشی:")
    st.code(str(e))
    st.stop()


# آمار سامانه
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("تعداد پژوهش‌ها", len(records))

with col2:
    st.metric(
        "فرضیه‌ها",
        sum(r["kind"] == "فرضیه" for r in records)
    )

with col3:
    st.metric(
        "نتایج",
        sum(r["kind"] == "نتیجه" for r in records)
    )


st.divider()


# ثبت پژوهش
st.subheader("ثبت پژوهش جدید")

with st.form("research_form"):

    title = st.text_input("عنوان پژوهش")

    question = st.text_area(
        "پرسش یا محتوای پژوهش",
        height=130
    )

    kind = st.selectbox(
        "نوع ثبت",
        ["پرسش", "فرضیه", "تحلیل", "نتیجه", "نقد", "مشاهده"]
    )

    status = st.selectbox(
        "وضعیت اعتبار",
        [
            "بررسی‌نشده",
            "مستند",
            "استنباط منطقی",
            "فرضیه آزمون‌پذیر",
            "گمانه فلسفی",
            "ردشده"
        ]
    )

    sources = st.text_area("منابع و شواهد")

    submitted = st.form_submit_button(
        "ذخیره در حافظه دائمی",
        use_container_width=True
    )

    if submitted:

        if not title.strip() or not question.strip():
            st.warning("عنوان و محتوا الزامی است.")

        else:
            record = {
                "id": str(uuid.uuid4()),
                "title": title.strip(),
                "question": question.strip(),
                "kind": kind,
                "status": status,
                "sources": sources.strip()
            }

            try:
                save_record(record)
                st.success("پژوهش ذخیره شد.")
                st.rerun()

            except Exception as e:
                st.error("خطا در ذخیره پژوهش:")
                st.code(str(e))


st.divider()


# نمایش حافظه پژوهشی
st.subheader("📚 حافظه پژوهشی")

if not records:
    st.info("هنوز پژوهشی ثبت نشده است.")

for record in records:

    with st.expander(
        str(record["kind"]) + " | " + str(record["title"])
    ):

        st.write("**محتوا:**")
        st.write(record["question"])

        st.write("**وضعیت:**", record["status"])

        if record.get("sources"):
            st.write("**منابع:**")
            st.write(record["sources"])

        st.caption("شناسه: " + str(record["id"]))


st.divider()


# پشتیبان‌گیری
st.subheader("مدیریت حافظه")

backup = json.dumps(
    records,
    ensure_ascii=False,
    indent=2
)

st.download_button(
    "دریافت نسخه پشتیبان JSON",
    data=backup.encode("utf-8"),
    file_name="beyond_cognition_backup.json",
    mime="application/json",
    use_container_width=True
)


st.divider()

st.caption(
    "Beyond Cognition | Persistent Research Core | Version 0.2.1"
)
