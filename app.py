import streamlit as st
import json
import uuid
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from supabase import create_client

logger = logging.getLogger(__name__)

st.set_page_config(page_title="فراتر از شناخت", page_icon="🧠", layout="wide")

# ---------- Configuration ----------
@st.cache_resource
def get_database():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def db_call(fn, user_message="عملیات پایگاه داده ناموفق بود."):
    try:
        return fn()
    except Exception:
        # Keep database details in server logs, not in the public interface.
        logger.exception("Database operation failed")
        st.error(user_message)
        return None

def valid_source_url(value):
    if not value.strip():
        return True
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)

def rows(table, order="created_at", desc=True):
    result = db.table(table).select("*").order(order, desc=desc).execute()
    return result.data or []

def insert(table, payload):
    return db.table(table).insert(payload).execute()

def update(table, payload, row_id):
    return db.table(table).update(payload).eq("id", row_id).execute()

try:
    db = get_database()
except Exception:
    logger.exception("Database connection failed")
    st.error("اتصال به حافظه دائمی برقرار نشد. تنظیمات اتصال را در بخش Secrets بررسی کن.")
    st.stop()

st.title("🧠 فراتر از شناخت")
st.caption("Beyond Cognition | محیط عملیاتی مغز پژوهشی")
st.caption("اصل سامانه: هیچ مدل واحدی نباید سقف توان کل سامانه باشد.")

# ---------- Load data ----------
try:
    sessions = rows("research_sessions")
    legacy_records = rows("research_records")
except Exception:
    logger.exception("Initial data load failed")
    st.error("خواندن داده‌ها با خطا روبه‌رو شد. لطفاً کمی بعد دوباره تلاش کن.")
    st.stop()

# ---------- Overview ----------
metric_cols = st.columns(4)
metric_cols[0].metric("جلسات پژوهش", len(sessions))
metric_cols[1].metric("یادداشت‌های قدیمی", len(legacy_records))
metric_cols[2].metric("جلسات فعال", sum(s.get("status") == "active" for s in sessions))
metric_cols[3].metric("جلسات تکمیل‌شده", sum(s.get("status") == "completed" for s in sessions))

tab_home, tab_new, tab_work, tab_archive, tab_export = st.tabs(
    ["نمای کلی", "پژوهش جدید", "میز کار پژوهش", "حافظه قبلی", "پشتیبان‌گیری"]
)

with tab_home:
    st.subheader("نمای کلی پژوهش‌ها")
    if not sessions:
        st.info("هنوز جلسه پژوهشی ایجاد نشده است. از بخش «پژوهش جدید» شروع کن.")
    else:
        for s in sessions[:20]:
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown("**" + s["title"] + "**")
                c1.write(s["central_question"])
                c2.caption("وضعیت: " + s["status"])
                c2.caption(str(s["created_at"])[:10])
    st.markdown("### قواعد ثبت شناختی")
    st.markdown("- **مستند:** دارای منبع قابل بررسی\n- **استنباط منطقی:** نتیجه‌گیری از مقدمات مشخص\n- **فرضیه آزمون‌پذیر:** دارای راهی برای تأیید یا رد\n- **گمانه فلسفی:** ایده‌ای برای کاوش، نه واقعیت اثبات‌شده\n- **نامعلوم:** داده کافی در دست نیست")

with tab_new:
    st.subheader("ایجاد جلسه پژوهشی")
    with st.form("new_session"):
        title = st.text_input("عنوان پژوهش", placeholder="مثلاً: آیا می‌توان همکاری چندمدلی را ارزیابی‌پذیر کرد؟")
        question = st.text_area("پرسش مرکزی", height=130)
        submitted = st.form_submit_button("ایجاد جلسه", type="primary", use_container_width=True)
    if submitted:
        if not title.strip() or not question.strip():
            st.warning("عنوان و پرسش مرکزی الزامی است.")
        else:
            result = db_call(lambda: insert("research_sessions", {
                "id": str(uuid.uuid4()), "title": title.strip(),
                "central_question": question.strip(), "status": "active"
            }))
            if result is not None:
                st.success("جلسه پژوهشی ایجاد شد.")
                st.rerun()

with tab_work:
    st.subheader("میز کار پژوهش")
    if not sessions:
        st.info("ابتدا یک جلسه پژوهشی بساز.")
    else:
        options = {f'{s["title"]} · {s["id"][:8]}': s for s in sessions}
        selected_label = st.selectbox("انتخاب جلسه", list(options.keys()))
        selected = options[selected_label]
        sid = selected["id"]
        st.markdown("### " + selected["title"])
        st.write(selected["central_question"])
        status_options = ["active", "paused", "completed"]
        new_status = st.selectbox("وضعیت جلسه", status_options,
                                  index=status_options.index(selected["status"]) if selected["status"] in status_options else 0)
        if st.button("به‌روزرسانی وضعیت"):
            result = db_call(lambda: update("research_sessions", {
                "status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()
            }, sid))
            if result is not None:
                st.success("وضعیت به‌روزرسانی شد.")
                st.rerun()

        step_rows = db_call(lambda: db.table("research_steps").select("*").eq("session_id", sid).order("sequence_no").execute())
        steps = step_rows.data if step_rows and step_rows.data else []
        st.metric("تعداد مراحل ثبت‌شده", len(steps))
        if steps:
            for step in steps:
                with st.expander(f'{step["sequence_no"]}. {step["role"]} · {step["epistemic_status"]}'):
                    if step.get("input_text"):
                        st.markdown("**ورودی / دستور کار**")
                        st.write(step["input_text"])
                    st.markdown("**خروجی ثبت‌شده**")
                    st.write(step["output_text"])
                    ev = db_call(lambda step_id=step["id"]: db.table("research_evidence").select("*").eq("step_id", step_id).order("created_at").execute())
                    evidence = ev.data if ev and ev.data else []
                    if evidence:
                        st.markdown("**شواهد پیوست‌شده**")
                        for item in evidence:
                            st.write(f'- {item["evidence_type"]}: {item["claim"]}')
                            if item.get("source_url"):
                                st.markdown(f'  منبع: {item["source_url"]}')

        st.markdown("### ثبت مرحله شناختی")
        roles = ["صورت‌بندی مسئله", "تحلیل‌گر", "فرضیه‌ساز", "منتقد", "ارزیاب شواهد", "ترکیب‌کننده", "یادداشت پژوهشگر"]
        epistemic = ["نامعلوم / بررسی‌نشده", "مستند", "استنباط منطقی", "فرضیه آزمون‌پذیر", "گمانه فلسفی", "ردشده"]
        with st.form("new_step"):
            role = st.selectbox("نقش مرحله", roles)
            step_input = st.text_area("ورودی یا دستور کار", height=90)
            output = st.text_area("خروجی / تحلیل", height=180)
            epistemic_status = st.selectbox("وضعیت معرفتی", epistemic)
            save_step = st.form_submit_button("ثبت مرحله", type="primary", use_container_width=True)
        if save_step:
            if not output.strip():
                st.warning("خروجی مرحله را وارد کن.")
            else:
                result = db_call(lambda: insert("research_steps", {
                    "id": str(uuid.uuid4()), "session_id": sid,
                    "sequence_no": max((int(item.get("sequence_no", 0)) for item in steps), default=0) + 1, "role": role,
                    "input_text": step_input.strip(), "output_text": output.strip(),
                    "epistemic_status": epistemic_status
                }))
                if result is not None:
                    st.success("مرحله ثبت شد.")
                    st.rerun()

        st.markdown("### افزودن شاهد به مرحله موردنظر")
        if not steps:
            st.caption("برای ثبت شاهد، ابتدا حداقل یک مرحله ایجاد کن.")
        else:
            step_options = {
                f'{item["sequence_no"]}. {item["role"]} · {item["id"][:8]}': item
                for item in steps
            }
            target_step_label = st.selectbox("مرحله مقصد شاهد", list(step_options.keys()))
            target_step = step_options[target_step_label]
            with st.form("new_evidence"):
                evidence_type = st.selectbox("نوع شاهد", ["منبع علمی", "سند رسمی", "داده تجربی", "مشاهده", "استدلال مخالف", "سایر"])
                claim = st.text_area("ادعا یا نکته‌ای که شاهد پشتیبانی می‌کند", height=90)
                source_title = st.text_input("عنوان منبع")
                source_url = st.text_input("نشانی منبع (در صورت وجود)")
                reliability = st.selectbox("ارزیابی اولیه اعتبار", ["ارزیابی‌نشده", "بالا", "متوسط", "پایین", "متعارض"])
                notes = st.text_area("یادداشت")
                save_evidence = st.form_submit_button("ثبت شاهد")
            if save_evidence:
                if not claim.strip():
                    st.warning("متن شاهد الزامی است.")
                elif not valid_source_url(source_url):
                    st.warning("نشانی منبع باید با http:// یا https:// شروع شود.")
                else:
                    result = db_call(lambda: insert("research_evidence", {
                        "id": str(uuid.uuid4()), "step_id": target_step["id"],
                        "evidence_type": evidence_type, "claim": claim.strip(),
                        "source_title": source_title.strip(), "source_url": source_url.strip(),
                        "reliability": reliability, "notes": notes.strip()
                    }))
                    if result is not None:
                        st.success("شاهد ثبت شد.")
                        st.rerun()

        st.markdown("### ثبت اجرای مدل یا عامل بیرونی")
        st.caption("این بخش فعلاً گزارش اجرای واقعی مدل را ثبت می‌کند؛ هنوز هیچ API مدل خارجی به سامانه متصل نشده است.")
        with st.form("model_run"):
            provider = st.text_input("ارائه‌دهنده", placeholder="مثلاً OpenAI / Anthropic / مدل محلی")
            model_name = st.text_input("نام دقیق مدل")
            task_role = st.selectbox("نقش اجرا", roles)
            prompt = st.text_area("پرامپت ارسال‌شده")
            response_text = st.text_area("پاسخ دریافت‌شده")
            run_status = st.selectbox("وضعیت اجرا", ["completed", "failed", "manual_record"])
            save_run = st.form_submit_button("ثبت گزارش اجرا")
        if save_run:
            if not provider.strip() or not model_name.strip():
                st.warning("ارائه‌دهنده و نام مدل الزامی است.")
            else:
                result = db_call(lambda: insert("model_runs", {
                    "id": str(uuid.uuid4()), "session_id": sid,
                    "provider": provider.strip(), "model_name": model_name.strip(),
                    "task_role": task_role, "prompt": prompt.strip(),
                    "response": response_text.strip(), "status": run_status
                }))
                if result is not None:
                    st.success("گزارش اجرا ثبت شد.")
                    st.rerun()

        st.markdown("### سابقه اجراهای ثبت‌شده")
        run_result = db_call(
            lambda: db.table("model_runs").select("*").eq("session_id", sid)
            .order("created_at", desc=True).limit(30).execute()
        )
        saved_runs = run_result.data if run_result and run_result.data else []
        if not saved_runs:
            st.caption("برای این جلسه هنوز گزارشی از اجرای مدل ثبت نشده است.")
        for run in saved_runs:
            with st.expander(f'{run["provider"]} / {run["model_name"]} · {run["status"]}'):
                st.caption(f'نقش: {run["task_role"]} | زمان: {str(run["created_at"])[:19]}')
                if run.get("prompt"):
                    st.markdown("**پرامپت**")
                    st.text(run["prompt"])
                if run.get("response"):
                    st.markdown("**پاسخ**")
                    st.write(run["response"])

with tab_archive:
    st.subheader("حافظه پژوهشی نسخه قبلی")
    st.caption("اطلاعات قبلی حفظ شده‌اند و در این نسخه حذف یا تبدیل اجباری نشده‌اند.")
    if not legacy_records:
        st.info("رکورد قدیمی‌ای وجود ندارد.")
    for record in legacy_records:
        with st.expander(f'{record.get("kind", "ثبت")} | {record.get("title", "بدون عنوان")}'):
            st.write(record.get("question", ""))
            st.caption("وضعیت: " + str(record.get("status", "")))
            if record.get("sources"):
                st.write("منابع: " + record["sources"])

with tab_export:
    st.subheader("پشتیبان‌گیری از حافظه پژوهشی")
    if st.button("ساخت فایل پشتیبان JSON", type="primary"):
        try:
            export_data = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "sessions": rows("research_sessions"),
                "steps": rows("research_steps"),
                "evidence": rows("research_evidence"),
                "model_runs": rows("model_runs"),
                "legacy_records": rows("research_records")
            }
            st.download_button("دریافت نسخه پشتیبان", json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8"),
                               file_name="beyond_cognition_backup.json", mime="application/json")
        except Exception as exc:
            st.exception(exc)

st.divider()
st.caption("Beyond Cognition · Research Core · Version 0.3.1")
