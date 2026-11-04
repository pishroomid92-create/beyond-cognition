import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import streamlit as st
from supabase import create_client
from workflow import summarize_workflow
from model_registry import PROVIDERS, configured_providers
from provider_adapters import ModelProviderError, generate_model_response
from workflow_agents import AGENT_SEQUENCE, build_agent_messages

logger = logging.getLogger("beyond_cognition")
st.set_page_config(page_title="فراتر از شناخت", page_icon="🧠", layout="wide")

def require_app_password():
    configured_password = str(st.secrets.get("APP_PASSWORD", "")).strip()
    if not configured_password:
        st.error("قفل ورود فعال نشده است. مدیر برنامه باید APP_PASSWORD را در Streamlit Secrets تنظیم کند.")
        st.stop()

    if st.session_state.get("authenticated", False):
        if st.sidebar.button("خروج از حساب"):
            st.session_state["authenticated"] = False
            st.rerun()
        return

    st.title("🔐 ورود به فراتر از شناخت")
    with st.form("app_password_form"):
        entered_password = st.text_input("رمز ورود", type="password")
        submitted = st.form_submit_button("ورود", type="primary", use_container_width=True)

    if submitted:
        if hmac.compare_digest(entered_password, configured_password):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("رمز ورود صحیح نیست.")
    st.stop()


require_app_password()

APP_VERSION = "0.6.0"
PAGE_SIZE = 500
TABLES = ("research_sessions", "research_steps", "research_evidence", "model_runs", "research_records")
ROLES = ["صورت‌بندی مسئله", "تحلیل‌گر", "فرضیه‌ساز", "منتقد", "ارزیاب شواهد", "ترکیب‌کننده", "یادداشت پژوهشگر"]
EPISTEMIC = ["نامعلوم / بررسی‌نشده", "مستند", "استنباط منطقی", "فرضیه آزمون‌پذیر", "گمانه فلسفی", "ردشده"]
SESSION_STATUSES = ["active", "paused", "completed"]

@st.cache_resource
def get_database():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def db_call(fn, message="عملیات پایگاه داده ناموفق بود."):
    try:
        return fn()
    except Exception:
        logger.exception("Database operation failed")
        st.error(message)
        return None

def fetch_rows(table, order="created_at", desc=True, limit=None):
    """Read every row in bounded pages; one API response may be capped."""
    rows = []
    offset = 0
    while True:
        page_size = PAGE_SIZE if limit is None else min(PAGE_SIZE, limit - offset)
        if page_size <= 0:
            break
        result = (
            db.table(table).select("*").order(order, desc=desc).order("id")
            .range(offset, offset + page_size - 1).execute()
        )
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += len(batch)
    return rows

def insert_row(table, payload):
    return db.table(table).insert(payload).execute()

def update_row(table, payload, row_id):
    return db.table(table).update(payload).eq("id", row_id).execute()

def touch_session(session_id):
    return db.table("research_sessions").update({
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", session_id).execute()

def valid_source_url(value):
    value = (value or "").strip()
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)

def safe_date(value):
    return str(value or "")[:19].replace("T", " ")

def show_error_context():
    st.caption("جزئیات فنی خطا در گزارش سمت سرور ثبت شده است؛ اطلاعات محرمانه اتصال نمایش داده نمی‌شود.")

try:
    db = get_database()
except Exception:
    logger.exception("Database connection failed")
    st.error("اتصال به حافظه دائمی برقرار نشد. تنظیمات اتصال برنامه را بررسی کن.")
    st.stop()

st.title("🧠 فراتر از شناخت")
st.caption("Beyond Cognition | مغز پژوهشی")
st.caption("اصل سامانه: هیچ مدل واحدی نباید سقف توان کل سامانه باشد.")
st.caption(f"نسخه {APP_VERSION}")

# Load primary data. Legacy records are read-only and are never migrated or deleted here.
sessions_result = db_call(lambda: fetch_rows("research_sessions", "updated_at", True),
                          "خواندن جلسات پژوهشی ناموفق بود.")
legacy_result = db_call(lambda: fetch_rows("research_records", "created_at", True),
                        "خواندن حافظه قبلی ناموفق بود.")
if sessions_result is None or legacy_result is None:
    show_error_context()
    st.stop()
sessions = sessions_result
legacy_records = legacy_result

active_count = sum(s.get("status") == "active" for s in sessions)
paused_count = sum(s.get("status") == "paused" for s in sessions)
completed_count = sum(s.get("status") == "completed" for s in sessions)

m = st.columns(4)
m[0].metric("کل جلسات", len(sessions))
m[1].metric("فعال", active_count)
m[2].metric("متوقف", paused_count)
m[3].metric("تکمیل‌شده", completed_count)

tab_home, tab_new, tab_work, tab_archive, tab_backup = st.tabs(
    ["نمای کلی", "پژوهش جدید", "میز کار پژوهش", "حافظه قبلی", "پشتیبان‌گیری"]
)

with tab_home:
    st.subheader("نمای کلی پژوهش‌ها")
    if not sessions:
        st.info("هنوز جلسه‌ای ایجاد نشده است. از بخش «پژوهش جدید» شروع کن.")
    else:
        search_home = st.text_input("جست‌وجو در عنوان و پرسش پژوهش", key="home_search")
        filtered_home = [
            s for s in sessions
            if search_home.strip().casefold() in
            (str(s.get("title", "")) + " " + str(s.get("central_question", ""))).casefold()
        ]
        if not filtered_home:
            st.info("موردی با این عبارت پیدا نشد.")
        for s in filtered_home[:30]:
            with st.container(border=True):
                left, right = st.columns([5, 1])
                left.markdown("**" + str(s.get("title") or "بدون عنوان") + "**")
                left.write(s.get("central_question") or "")
                right.caption("وضعیت: " + str(s.get("status") or "نامشخص"))
                right.caption(safe_date(s.get("updated_at") or s.get("created_at"))[:10])
        if len(filtered_home) > 30:
            st.caption("برای خلوت ماندن صفحه، فقط ۳۰ نتیجه نخست نمایش داده شده است.")
    st.markdown("### معیارهای وضعیت معرفتی")
    st.markdown(
        "- **مستند:** دارای منبع قابل بررسی\n"
        "- **استنباط منطقی:** نتیجه‌گیری از مقدمات روشن\n"
        "- **فرضیه آزمون‌پذیر:** دارای روش بالقوه تأیید یا رد\n"
        "- **گمانه فلسفی:** ایده‌ای برای کاوش، نه واقعیت اثبات‌شده\n"
        "- **نامعلوم / بررسی‌نشده:** داده کافی در دست نیست\n"
        "- **ردشده:** با شواهد یا آزمون معتبر ناسازگار تشخیص داده شده است"
    )

with tab_new:
    st.subheader("ایجاد جلسه پژوهشی")
    with st.form("create_session_form", clear_on_submit=True):
        title = st.text_input("عنوان پژوهش", placeholder="عنوان کوتاه و مشخص")
        question = st.text_area("پرسش مرکزی", height=130,
                                placeholder="دقیقاً چه چیزی را می‌خواهیم بررسی کنیم؟")
        create = st.form_submit_button("ایجاد جلسه", type="primary", use_container_width=True)
    if create:
        if not title.strip() or not question.strip():
            st.warning("عنوان و پرسش مرکزی هر دو الزامی‌اند.")
        else:
            result = db_call(lambda: insert_row("research_sessions", {
                "id": str(uuid.uuid4()), "title": title.strip(),
                "central_question": question.strip(), "status": "active"
            }), "ایجاد جلسه انجام نشد.")
            if result is not None:
                st.success("جلسه پژوهشی ایجاد شد.")
                st.rerun()

with tab_work:
    st.subheader("میز کار پژوهش")
    with st.expander("الگوی پیشنهادی گردش‌کار پژوهش", expanded=False):
        st.markdown(
            "۱. **صورت‌بندی مسئله:** تعریف دقیق پرسش، دامنه و معیار پاسخ\n"
            "۲. **تحلیل‌گر:** تفکیک دانسته‌ها، مجهولات و پیش‌فرض‌ها\n"
            "۳. **فرضیه‌ساز:** ارائه چند توضیح یا پاسخ رقیب\n"
            "۴. **منتقد:** جست‌وجوی ایرادها، شواهد مخالف و مثال نقض\n"
            "۵. **ارزیاب شواهد:** سنجش کیفیت، استقلال و اعتبار منابع\n"
            "۶. **ترکیب‌کننده:** جمع‌بندی همراه با درجه اطمینان و پرسش‌های باز"
        )
        st.caption("این الگو راهنمای ثبت کار است؛ هنوز اجرای خودکار چندمدلی در سامانه فعال نیست.")
    if not sessions:
        st.info("ابتدا یک جلسه پژوهشی ایجاد کن.")
    else:
        selector_col, filter_col = st.columns([3, 2])
        session_filter = filter_col.selectbox("فیلتر وضعیت", ["همه", "active", "paused", "completed"])
        candidates = sessions if session_filter == "همه" else [s for s in sessions if s.get("status") == session_filter]
        if not candidates:
            st.info("در این وضعیت جلسه‌ای وجود ندارد.")
        else:
            options = {
                f'{s.get("title", "بدون عنوان")} · {str(s.get("id", ""))[:8]}': s
                for s in candidates
            }
            selected_label = selector_col.selectbox("انتخاب جلسه", list(options.keys()))
            selected = options[selected_label]
            sid = selected["id"]

            st.markdown("### " + str(selected.get("title") or "بدون عنوان"))
            st.write(selected.get("central_question") or "")

            with st.expander("ویرایش عنوان، پرسش و وضعیت جلسه"):
                with st.form("edit_session_form"):
                    edited_title = st.text_input("عنوان", value=selected.get("title") or "")
                    edited_question = st.text_area("پرسش مرکزی", value=selected.get("central_question") or "", height=110)
                    current_status = selected.get("status") if selected.get("status") in SESSION_STATUSES else "active"
                    edited_status = st.selectbox("وضعیت", SESSION_STATUSES,
                                                 index=SESSION_STATUSES.index(current_status))
                    save_session = st.form_submit_button("ذخیره تغییرات")
                if save_session:
                    if not edited_title.strip() or not edited_question.strip():
                        st.warning("عنوان و پرسش مرکزی نمی‌توانند خالی باشند.")
                    else:
                        result = db_call(lambda: update_row("research_sessions", {
                            "title": edited_title.strip(),
                            "central_question": edited_question.strip(),
                            "status": edited_status,
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }, sid), "ویرایش جلسه انجام نشد.")
                        if result is not None:
                            st.success("تغییرات جلسه ذخیره شد.")
                            st.rerun()

            step_result = db_call(
                lambda: db.table("research_steps").select("*").eq("session_id", sid)
                .order("sequence_no").execute(),
                "خواندن مراحل این جلسه ناموفق بود."
            )
            if step_result is None:
                show_error_context()
                steps = []
            else:
                steps = step_result.data or []

            evidence_by_step = {step["id"]: [] for step in steps}
            if steps:
                step_ids = [step["id"] for step in steps]
                ev_result = db_call(
                    lambda: db.table("research_evidence").select("*")
                    .in_("step_id", step_ids).order("created_at").execute(),
                    "خواندن شواهد این جلسه ناموفق بود."
                )
                if ev_result is not None:
                    for evidence in (ev_result.data or []):
                        evidence_by_step.setdefault(evidence["step_id"], []).append(evidence)

            total_evidence = sum(len(v) for v in evidence_by_step.values())
            required_roles = ROLES[:6]
            workflow_state = summarize_workflow(steps, required_roles)
            completed_count = workflow_state["completed_count"]
            missing_roles = workflow_state["missing_roles"]
            st.markdown("### پیشرفت گردش‌کار")
            st.progress(completed_count / len(required_roles))
            st.caption(f'پیشرفت نقش‌های اصلی: {completed_count} از {len(required_roles)}')
            if workflow_state["next_role"]:
                st.info("گام پیشنهادی بعدی: " + workflow_state["next_role"])
            if missing_roles:
                st.caption("نقش‌های ثبت‌نشده: " + "، ".join(missing_roles))
            else:
                st.success("هر شش نقش اصلی ثبت شده‌اند؛ کیفیت شواهد و استدلال‌ها همچنان باید ارزیابی شود.")
            if workflow_state["duplicate_roles"]:
                st.warning("نقش‌های تکراری ثبت شده‌اند: " + "، ".join(workflow_state["duplicate_roles"]))
            if workflow_state["out_of_order"]:
                st.warning("ترتیب برخی مراحل با الگوی پژوهش هم‌خوان نیست: " + "، ".join(workflow_state["out_of_order"]))
            k = st.columns(3)
            k[0].metric("مراحل ثبت‌شده", len(steps))
            k[1].metric("شواهد پیوست‌شده", total_evidence)
            k[2].metric("آخرین به‌روزرسانی", safe_date(selected.get("updated_at"))[:10] or "—")

            st.markdown("### مراحل و شواهد")
            if not steps:
                st.info("برای این جلسه هنوز مرحله‌ای ثبت نشده است.")
            for step in steps:
                label = f'{step.get("sequence_no", "?")}. {step.get("role", "بدون نقش")} · {step.get("epistemic_status", "نامشخص")}'
                with st.expander(label):
                    if step.get("input_text"):
                        st.markdown("**ورودی / دستور کار**")
                        st.write(step["input_text"])
                    st.markdown("**خروجی ثبت‌شده**")
                    st.write(step.get("output_text") or "")
                    st.caption("زمان ثبت: " + safe_date(step.get("created_at")))
                    for ev in evidence_by_step.get(step["id"], []):
                        st.markdown("---")
                        st.markdown("**شاهد: " + str(ev.get("evidence_type") or "بدون نوع") + "**")
                        st.write(ev.get("claim") or "")
                        if ev.get("source_title"):
                            st.caption("منبع: " + ev["source_title"])
                        if ev.get("source_url"):
                            st.write("نشانی منبع:", ev["source_url"])
                        st.caption("اعتبار اولیه: " + str(ev.get("reliability") or "ارزیابی‌نشده"))
                        if ev.get("notes"):
                            st.write(ev["notes"])
                        with st.form("edit_evidence_" + str(ev["id"])):
                            edited_type = st.selectbox(
                                "نوع شاهد",
                                ["منبع علمی", "سند رسمی", "داده تجربی", "مشاهده", "استدلال مخالف", "سایر"],
                                index=["منبع علمی", "سند رسمی", "داده تجربی", "مشاهده", "استدلال مخالف", "سایر"].index(ev["evidence_type"])
                                if ev.get("evidence_type") in ["منبع علمی", "سند رسمی", "داده تجربی", "مشاهده", "استدلال مخالف", "سایر"] else 0
                            )
                            edited_claim = st.text_area("متن شاهد", value=ev.get("claim") or "", height=70)
                            edited_source_title = st.text_input("عنوان منبع", value=ev.get("source_title") or "")
                            edited_source_url = st.text_input("نشانی منبع", value=ev.get("source_url") or "")
                            reliability_options = ["ارزیابی‌نشده", "بالا", "متوسط", "پایین", "متعارض"]
                            old_reliability = ev.get("reliability")
                            edited_reliability = st.selectbox(
                                "اعتبار اولیه", reliability_options,
                                index=reliability_options.index(old_reliability) if old_reliability in reliability_options else 0
                            )
                            edited_notes = st.text_area("یادداشت", value=ev.get("notes") or "", height=60)
                            save_evidence_edit = st.form_submit_button("ذخیره ویرایش شاهد")
                        if save_evidence_edit:
                            if not edited_claim.strip():
                                st.warning("متن شاهد نمی‌تواند خالی باشد.")
                            elif not valid_source_url(edited_source_url):
                                st.warning("نشانی منبع باید با http یا https شروع شود.")
                            else:
                                result = db_call(lambda: update_row("research_evidence", {
                                    "evidence_type": edited_type,
                                    "claim": edited_claim.strip(),
                                    "source_title": edited_source_title.strip(),
                                    "source_url": edited_source_url.strip(),
                                    "reliability": edited_reliability,
                                    "notes": edited_notes.strip()
                                }, ev["id"]), "ویرایش شاهد ناموفق بود.")
                                if result is not None:
                                    db_call(lambda: touch_session(sid), "زمان آخرین فعالیت جلسه به‌روزرسانی نشد.")
                                    st.success("شاهد ویرایش شد.")
                                    st.rerun()
                    with st.form("edit_step_" + str(step["id"])):
                        edit_role = st.selectbox("نقش", ROLES,
                            index=ROLES.index(step["role"]) if step.get("role") in ROLES else 0)
                        edit_input = st.text_area("ورودی", value=step.get("input_text") or "", height=80)
                        edit_output = st.text_area("خروجی", value=step.get("output_text") or "", height=150)
                        old_epistemic = step.get("epistemic_status")
                        edit_epistemic = st.selectbox("وضعیت معرفتی", EPISTEMIC,
                            index=EPISTEMIC.index(old_epistemic) if old_epistemic in EPISTEMIC else 0)
                        save_step_edit = st.form_submit_button("ذخیره ویرایش مرحله")
                    if save_step_edit:
                        if not edit_output.strip():
                            st.warning("خروجی مرحله نمی‌تواند خالی باشد.")
                        else:
                            result = db_call(lambda: update_row("research_steps", {
                                "role": edit_role, "input_text": edit_input.strip(),
                                "output_text": edit_output.strip(),                                "epistemic_status": edit_epistemic
                            }, step["id"]), "ویرایش مرحله انجام نشد.")
                            if result is not None:
                                db_call(lambda: touch_session(sid), "زمان آخرین فعالیت جلسه به‌روزرسانی نشد.")
                                st.success("مرحله ویرایش شد.")
                                st.rerun()

            st.markdown("### ثبت مرحله شناختی")
            with st.form("new_step_form", clear_on_submit=True):
                role = st.selectbox("نقش مرحله", ROLES, index=ROLES.index(workflow_state["next_role"]) if workflow_state["next_role"] in ROLES else 0)
                step_input = st.text_area("ورودی یا دستور کار", height=80)
                output = st.text_area("خروجی / تحلیل", height=160)
                epistemic_status = st.selectbox("وضعیت معرفتی", EPISTEMIC)
                save_step = st.form_submit_button("ثبت مرحله", type="primary", use_container_width=True)
            if save_step:
                if not output.strip():
                    st.warning("خروجی مرحله را وارد کن.")
                else:
                    next_sequence = max((int(x.get("sequence_no", 0)) for x in steps), default=0) + 1
                    result = db_call(lambda: insert_row("research_steps", {
                        "id": str(uuid.uuid4()), "session_id": sid, "sequence_no": next_sequence,
                        "role": role, "input_text": step_input.strip(),
                        "output_text": output.strip(), "epistemic_status": epistemic_status
                    }), "ثبت مرحله ناموفق بود.")
                    if result is not None:
                        db_call(lambda: touch_session(sid), "زمان آخرین فعالیت جلسه به‌روزرسانی نشد.")
                        st.success("مرحله ثبت شد.")
                        st.rerun()

            st.markdown("### افزودن شاهد")
            if steps:
                step_options = {
                    f'{x.get("sequence_no")}. {x.get("role")} · {str(x.get("id"))[:8]}': x
                    for x in steps
                }
                target_label = st.selectbox("مرحله مقصد", list(step_options.keys()))
                target_step = step_options[target_label]
                with st.form("new_evidence_form", clear_on_submit=True):
                    evidence_type = st.selectbox("نوع شاهد", ["منبع علمی", "سند رسمی", "داده تجربی", "مشاهده", "استدلال مخالف", "سایر"])
                    claim = st.text_area("ادعا یا نکته‌ای که شاهد پشتیبانی می‌کند", height=80)
                    source_title = st.text_input("عنوان منبع")
                    source_url = st.text_input("نشانی منبع")
                    reliability = st.selectbox("اعتبار اولیه", ["ارزیابی‌نشده", "بالا", "متوسط", "پایین", "متعارض"])
                    notes = st.text_area("یادداشت", height=70)
                    save_evidence = st.form_submit_button("ثبت شاهد")
                if save_evidence:
                    if not claim.strip():
                        st.warning("متن شاهد الزامی است.")
                    elif not valid_source_url(source_url):
                        st.warning("نشانی منبع باید یک نشانی معتبر با http یا https باشد.")
                    else:
                        result = db_call(lambda: insert_row("research_evidence", {
                            "id": str(uuid.uuid4()), "step_id": target_step["id"],
                            "evidence_type": evidence_type, "claim": claim.strip(),
                            "source_title": source_title.strip(), "source_url": source_url.strip(),
                            "reliability": reliability, "notes": notes.strip()
                        }), "ثبت شاهد ناموفق بود.")
                        if result is not None:
                            db_call(lambda: touch_session(sid), "زمان آخرین فعالیت جلسه به‌روزرسانی نشد.")
                            st.success("شاهد ثبت شد.")
                            st.rerun()
            else:
                st.caption("ابتدا یک مرحله ثبت کن تا بتوانی شاهدی به آن پیوست کنی.")

            st.markdown("### اتصال و آزمایش ارائه‌دهنده مدل")
            available_providers = configured_providers(st.secrets)
            if not available_providers:
                st.warning(
                    "هیچ کلید ارائه‌دهنده‌ای در زمان اجرای برنامه شناسایی نشد. "
                    "نام کلید را در Streamlit Secrets بررسی کن."
                )
            else:
                provider_labels = {
                    value: PROVIDERS[value]["label"] for value in available_providers
                }
                selected_provider = st.selectbox(
                    "ارائه‌دهنده",
                    available_providers,
                    format_func=lambda value: provider_labels[value],
                    key="active_model_provider",
                )
                st.success(
                    "کلید " + PROVIDERS[selected_provider]["secret_name"]
                    + " از Secrets شناسایی شد؛ مقدار کلید نمایش داده نمی‌شود."
                )
                model_id = st.text_input(
                    "شناسه مدل",
                    value="openrouter/free" if selected_provider == "openrouter" else "",
                    placeholder="شناسه دقیق مدل در کاتالوگ ارائه‌دهنده",
                    key="active_model_id",
                )
                api_key = str(
                    st.secrets.get(PROVIDERS[selected_provider]["secret_name"], "")
                ).strip()

                if st.button("آزمایش واقعی اتصال", key="test_model_connection"):
                    if not model_id.strip():
                        st.warning("شناسه مدل را وارد کن.")
                    else:
                        with st.spinner("در حال ارسال درخواست آزمایشی..."):
                            try:
                                connection_test = generate_model_response(
                                    provider=selected_provider,
                                    model=model_id.strip(),
                                    messages=[
                                        {
                                            "role": "system",
                                            "content": "Reply with exactly CONNECTION_OK and nothing else.",
                                        },
                                        {
                                            "role": "user",
                                            "content": "Connection test. Reply exactly CONNECTION_OK.",
                                        },
                                    ],
                                    api_key=api_key,
                                    temperature=0,
                                    max_output_tokens=64,
                                    timeout_seconds=45,
                                )
                            except ModelProviderError as exc:
                                st.error("آزمایش اتصال ناموفق بود: " + str(exc))
                            else:
                                st.success(
                                    "اتصال واقعی موفق است. مدل پاسخ داد: "
                                    + connection_test.text[:200]
                                )
                                st.caption(
                                    f"مدل پاسخ‌دهنده: {connection_test.model} "
                                    f"| زمان پاسخ: {connection_test.latency_ms} ms"
                                )

                st.divider()
                st.markdown("### اجرای گردش‌کار شش‌مرحله‌ای پژوهش")
                st.caption(
                    "در این نسخه شش نقش به‌ترتیب با همین مدل اجرا می‌شوند؛ "
                    "این گردش‌کار چندمرحله‌ای است، نه شش مدل مستقل. "
                    "هر مرحله پس از دریافت پاسخ ذخیره می‌شود. در صورت خطا، "
                    "مراحل موفق قبلی باقی می‌مانند و اجرا متوقف می‌شود."
                )
                with st.form("agent_pipeline_form"):
                    pipeline_question = st.text_area(
                        "پرسش مرکزی برای گردش‌کار",
                        value=selected.get("central_question") or "",
                        height=120,
                        key="pipeline_central_question",
                    )
                    pipeline_temperature = st.slider(
                        "تنوع پاسخ مراحل", 0.0, 1.0, 0.2, 0.1,
                        key="pipeline_temperature",
                    )
                    pipeline_tokens = st.slider(
                        "حداکثر توکن خروجی هر مرحله", 256, 4096, 1800, 256,
                        key="pipeline_tokens",
                    )
                    run_pipeline = st.form_submit_button(
                        "اجرای شش مرحله و ذخیره نتایج",
                        type="primary",
                        use_container_width=True,
                    )

                if run_pipeline:
                    if not pipeline_question.strip():
                        st.warning("پرسش مرکزی پژوهش خالی است.")
                    elif not model_id.strip():
                        st.warning("شناسه مدل را وارد کن.")
                    else:
                        previous_outputs = []
                        next_sequence = max(
                            (int(item.get("sequence_no", 0)) for item in steps),
                            default=0,
                        ) + 1
                        completed_roles = []
                        pipeline_failed = False
                        for role in AGENT_SEQUENCE:
                            stage_messages = build_agent_messages(
                                role, pipeline_question, previous_outputs
                            )
                            stage_prompt = stage_messages[0]["content"] + (
                                "\\n\\n" + stage_messages[1]["content"]
                            )
                            with st.spinner("در حال اجرای مرحله: " + role):
                                try:
                                    stage_result = generate_model_response(
                                        provider=selected_provider,
                                        model=model_id.strip(),
                                        messages=stage_messages,
                                        api_key=api_key,
                                        temperature=pipeline_temperature,
                                        max_output_tokens=pipeline_tokens,
                                        timeout_seconds=90,
                                    )
                                except ModelProviderError as exc:
                                    db_call(
                                        lambda: insert_row("model_runs", {
                                            "id": str(uuid.uuid4()),
                                            "session_id": sid,
                                            "provider": selected_provider,
                                            "model_name": model_id.strip(),
                                            "task_role": role,
                                            "prompt": stage_prompt,
                                            "response": str(exc),
                                            "status": "failed",
                                        }),
                                        "ثبت گزارش خطای مرحله ناموفق بود.",
                                    )
                                    st.error("گردش‌کار در مرحله «" + role + "» متوقف شد: " + str(exc))
                                    pipeline_failed = True
                                    break

                            saved_run = db_call(
                                lambda: insert_row("model_runs", {
                                    "id": str(uuid.uuid4()),
                                    "session_id": sid,
                                    "provider": selected_provider,
                                    "model_name": stage_result.model,
                                    "task_role": role,
                                    "prompt": stage_prompt,
                                    "response": stage_result.text,
                                    "status": "completed",
                                }),
                                "ذخیره اجرای مدل ناموفق بود؛ گردش‌کار متوقف شد.",
                            )
                            if saved_run is None:
                                pipeline_failed = True
                                break

                            saved_step = db_call(
                                lambda: insert_row("research_steps", {
                                    "id": str(uuid.uuid4()),
                                    "session_id": sid,
                                    "sequence_no": next_sequence,
                                    "role": role,
                                    "input_text": stage_prompt,
                                    "output_text": stage_result.text,
                                    "epistemic_status": "نامعلوم / بررسی‌نشده",
                                }),
                                "ذخیره مرحله پژوهش ناموفق بود؛ گردش‌کار متوقف شد.",
                            )
                            if saved_step is None:
                                pipeline_failed = True
                                break

                            previous_outputs.append({
                                "role": role,
                                "output": stage_result.text,
                            })
                            completed_roles.append(role)
                            next_sequence += 1
                            st.success(
                                f"مرحله {len(completed_roles)}/6 تکمیل شد: {role} "
                                f"({stage_result.latency_ms} ms)"
                            )

                        db_call(lambda: touch_session(sid))
                        if pipeline_failed:
                            st.warning(
                                "گردش‌کار به‌صورت ایمن متوقف شد. "
                                f"{len(completed_roles)} مرحله موفق در حافظه ثبت شده است."
                            )
                        else:
                            st.success(
                                "هر شش مرحله اجرا و در حافظه پژوهش ثبت شدند. "
                                "برچسب معرفتی خروجی‌ها عمداً «بررسی‌نشده» باقی مانده است."
                            )
                            st.rerun()

            st.markdown("### ثبت گزارش اجرای مدل یا عامل")
            st.caption("این فرم برای ثبت دستی اجراهایی است که بیرون از سامانه انجام شده‌اند.")
            with st.form("model_run_form", clear_on_submit=True):
                provider = st.text_input("ارائه‌دهنده", placeholder="نام سرویس یا ارائه‌دهنده")
                model_name = st.text_input("نام دقیق مدل")
                task_role = st.selectbox("نقش اجرا", ROLES)
                prompt = st.text_area("پرامپت ارسال‌شده", height=100)
                response_text = st.text_area("پاسخ دریافت‌شده", height=120)
                run_status = st.selectbox("وضعیت", ["completed", "failed", "manual_record"])
                save_run = st.form_submit_button("ثبت گزارش اجرا")
            if save_run:
                if not provider.strip() or not model_name.strip():
                    st.warning("ارائه‌دهنده و نام مدل الزامی است.")
                else:
                    result = db_call(lambda: insert_row("model_runs", {
                        "id": str(uuid.uuid4()), "session_id": sid,
                        "provider": provider.strip(), "model_name": model_name.strip(),
                        "task_role": task_role, "prompt": prompt.strip(),
                        "response": response_text.strip(), "status": run_status
                    }), "ثبت گزارش اجرا ناموفق بود.")
                    if result is not None:
                        db_call(lambda: touch_session(sid), "زمان آخرین فعالیت جلسه به‌روزرسانی نشد.")
                        st.success("گزارش اجرا ثبت شد.")
                        st.rerun()

            run_result = db_call(
                lambda: db.table("model_runs").select("*").eq("session_id", sid)
                .order("created_at", desc=True).limit(50).execute(),
                "خواندن سوابق اجرای مدل ناموفق بود."
            )
            st.markdown("### سابقه اجراهای ثبت‌شده")
            saved_runs = run_result.data if run_result else []
            if not saved_runs:
                st.caption("برای این جلسه گزارشی از اجرای مدل ثبت نشده است.")
            for run in saved_runs:
                with st.expander(f'{run.get("provider")} / {run.get("model_name")} · {run.get("status")}'):
                    st.caption(f'نقش: {run.get("task_role")} | زمان: {safe_date(run.get("created_at"))}')
                    if run.get("prompt"):
                        st.markdown("**پرامپت**")
                        st.text(run["prompt"])
                    if run.get("response"):
                        st.markdown("**پاسخ**")
                        st.write(run["response"])

with tab_archive:
    st.subheader("حافظه پژوهشی نسخه قبلی")
    st.caption("این سوابق فقط خواندنی هستند؛ در این نسخه حذف یا تبدیل اجباری نمی‌شوند.")
    if not legacy_records:
        st.info("رکورد قدیمی‌ای وجود ندارد.")
    else:
        legacy_search = st.text_input("جست‌وجو در حافظه قبلی", key="legacy_search")
        filtered_legacy = [
            r for r in legacy_records
            if legacy_search.strip().casefold() in
            (str(r.get("title", "")) + " " + str(r.get("question", "")) + " " + str(r.get("sources", ""))).casefold()
        ]
        st.caption(f"{len(filtered_legacy)} رکورد از {len(legacy_records)} رکورد")
        for record in filtered_legacy:
            with st.expander(f'{record.get("kind", "ثبت")} | {record.get("title", "بدون عنوان")}'):
                st.write(record.get("question") or "")
                st.caption("وضعیت: " + str(record.get("status") or ""))
                if record.get("sources"):
                    st.write("منابع: " + str(record["sources"]))
                st.caption("زمان ثبت: " + safe_date(record.get("created_at")))

with tab_backup:
    st.subheader("پشتیبان‌گیری از حافظه پژوهشی")
    st.write("نسخه پشتیبان شامل تمام صفحات جلسات، مراحل، شواهد، گزارش اجراهای مدل و رکوردهای قدیمی است.")
    st.caption("دریافت به‌صورت صفحه‌بندی‌شده انجام می‌شود تا محدودیت تعداد رکورد در یک پاسخ باعث ناقص‌شدن خروجی نشود.")
    if st.button("آماده‌سازی نسخه پشتیبان", type="primary"):
        try:
            export_data = {
                "schema_version": APP_VERSION,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "sessions": fetch_rows("research_sessions"),
                "steps": fetch_rows("research_steps"),
                "evidence": fetch_rows("research_evidence"),
                "model_runs": fetch_rows("model_runs"),
                "legacy_records": fetch_rows("research_records")
            }
            payload = json.dumps(export_data, ensure_ascii=False, indent=2, default=str).encode("utf-8")
            st.download_button(
                "دریافت فایل پشتیبان JSON",
                data=payload,
                file_name="beyond_cognition_backup_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + ".json",
                mime="application/json",
                use_container_width=True
            )
            st.success("فایل پشتیبان آماده دریافت است.")
        except Exception:
            logger.exception("Backup export failed")
            st.error("ساخت نسخه پشتیبان ناموفق بود.")

st.divider()
st.caption("Beyond Cognition · Research Core · " + APP_VERSION)