
import streamlit as st
import json
from datetime import datetime
from uuid import uuid4

st.set_page_config(
    page_title="فراتر از شناخت",
    page_icon="🧠",
    layout="wide"
)

if "records" not in st.session_state:
    st.session_state.records = []

st.title("🧠 فراتر از شناخت")
st.caption("Beyond Cognition | Human–AI Research System")
st.divider()

st.subheader("هسته پژوهشی نسخه ۰.۱")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("تعداد پژوهش‌ها", len(st.session_state.records))

with col2:
    st.metric(
        "فرضیه‌ها",
        sum(r["kind"] == "فرضیه" for r in st.session_state.records)
    )

with col3:
    st.metric(
        "نتایج ثبت‌شده",
        sum(r["kind"] == "نتیجه" for r in st.session_state.records)
    )

st.divider()

st.subheader("ثبت پژوهش جدید")

with st.form("research_form"):
    title = st.text_input("عنوان پژوهش")

    question = st.text_area(
        "پرسش یا محتوای پژوهش",
        height=120
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

    sources = st.text_area(
        "منابع و شواهد",
        height=80
    )

    submitted = st.form_submit_button(
        "ثبت در حافظه پژوهشی",
        use_container_width=True
    )

    if submitted:
        if title.strip() and question.strip():
            record = {
                "id": str(uuid4()),
                "title": title.strip(),
                "question": question.strip(),
                "kind": kind,
                "status": status,
                "sources": sources.strip(),
                "created_at": datetime.now().isoformat()
            }

            st.session_state.records.append(record)
            st.success("پژوهش ثبت شد.")
        else:
            st.warning("عنوان و محتوای پژوهش الزامی است.")

st.divider()

st.subheader("📚 حافظه پژوهشی")

if not st.session_state.records:
    st.info("هنوز پژوهشی ثبت نشده است.")
else:
    for record in reversed(st.session_state.records):
        with st.expander(
            f'{record["kind"]} | {record["title"]}'
        ):
            st.write("**محتوا:**")
            st.write(record["question"])

            st.write("**وضعیت:**", record["status"])

            if record["sources"]:
                st.write("**منابع:**")
                st.write(record["sources"])

            st.caption(
                "شناسه: " + record["id"]
            )

st.divider()

st.subheader("مدیریت داده‌های پژوهشی")

data = json.dumps(
    st.session_state.records,
    ensure_ascii=False,
    indent=2
)

st.download_button(
    "⬇️ خروجی گرفتن از حافظه پژوهشی",
    data=data.encode("utf-8"),
    file_name="beyond_cognition_memory.json",
    mime="application/json",
    use_container_width=True
)

uploaded_file = st.file_uploader(
    "بازیابی حافظه از فایل JSON",
    type=["json"]
)

if uploaded_file is not None:
    if st.button("بازیابی اطلاعات"):
        try:
            imported = json.loads(
                uploaded_file.getvalue().decode("utf-8")
            )

            if not isinstance(imported, list):
                raise ValueError("ساختار فایل معتبر نیست.")

            if not all(
                isinstance(item, dict)
                and all(
                    key in item
                    for key in [
                        "id", "title", "question",
                        "kind", "status", "sources",
                        "created_at"
                    ]
                )
                for item in imported
            ):
                raise ValueError("ساختار اطلاعات ناقص است.")

            existing_ids = {
                r["id"] for r in st.session_state.records
            }

            new_records = [
                r for r in imported
                if r["id"] not in existing_ids
            ]

            st.session_state.records.extend(new_records)
            st.success(
                f"{len(new_records)} رکورد بازیابی شد."
            )
            st.rerun()

        except Exception as error:
            st.error(f"خطا در بازیابی: {error}")

st.caption(
    "Beyond Cognition | Initial Research Core | Version 0.1"
)
