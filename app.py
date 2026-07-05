"""
app.py
------
تطبيق Streamlit لسحب بيانات المنتجات من متاجر Shopify و YouCan
وتصديرها كملف Excel / CSV منظم.

نظام الحماية:
- الأكواد المقبولة (VALID_KEYS) كتقرا من st.secrets، ماشي مكتوبة فالكود.
- خاصك تزيدها فـ Streamlit Cloud > Settings > Secrets (شوف .streamlit/secrets.toml.example)
- عدد الاستعمالات ديال الأكواد التجريبية (max_uses) كيتراقب عبر usage_tracker.py
"""

from __future__ import annotations

import time
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

from scraper import ScrapeError, scrape_store
from usage_tracker import has_remaining_uses, record_use, remaining_uses

# ---------------------------------------------------------------------------
# إعدادات الصفحة
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="أداة سحب بيانات المنافسين | COD Morocco",
    page_icon="📦",
    layout="centered",
)

MAX_PRODUCTS_DEFAULT = 60
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_SECONDS = 60


# ---------------------------------------------------------------------------
# تصميم عام (CSS)
# ---------------------------------------------------------------------------
def inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap');

        html, body, [class*="css"] {
            font-family: 'Tajawal', sans-serif;
        }

        .block-container {
            padding-top: 2rem;
            max-width: 780px;
        }

        .app-header {
            text-align: center;
            padding: 1.2rem 1rem 0.4rem 1rem;
        }
        .app-header h1 {
            font-weight: 900;
            font-size: 1.7rem;
            margin-bottom: 0.15rem;
            color: #1f2937;
        }
        .app-header p {
            color: #6b7280;
            font-size: 0.95rem;
            margin-top: 0;
        }

        div.stButton > button, div.stDownloadButton > button {
            border-radius: 10px;
            font-weight: 700;
            padding: 0.6rem 1rem;
        }

        .metric-card {
            background: #f8fafc;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 0.9rem 0.6rem;
            text-align: center;
        }
        .metric-card .value {
            font-size: 1.4rem;
            font-weight: 900;
            color: #111827;
        }
        .metric-card .label {
            font-size: 0.8rem;
            color: #6b7280;
            margin-top: 0.15rem;
        }

        .badge {
            display: inline-block;
            padding: 0.15rem 0.65rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
        }
        .badge-paid { background: #dcfce7; color: #166534; }
        .badge-trial { background: #fef9c3; color: #854d0e; }

        [data-testid="stTextInput"] input,
        [data-testid="stDataFrame"] {
            direction: rtl;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def app_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="app-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# نظام الحماية (Gatekeeper)
# ---------------------------------------------------------------------------
def load_valid_keys() -> dict:
    """
    كنقراو الأكواد الصالحة من secrets.
    الشكل المتوقع فـ secrets.toml:

    [keys]
    "TEST-FREE-00" = { type = "trial", expires = "2026-12-31", max_uses = 20 }
    "CLIENT-AHMED-01" = { type = "paid", expires = "" , max_uses = 0 }

    - type: "trial" ولا "paid"
    - expires: تاريخ الانتهاء "YYYY-MM-DD"، ولا "" إلا كان بلا تاريخ نهاية
    - max_uses: عدد مرات السحب المسموحة للكود التجريبي (0 = بلا حدود)
    """
    if "keys" in st.secrets:
        return dict(st.secrets["keys"])
    return {}


def is_key_valid(key: str, keys_db: dict) -> tuple[bool, str]:
    if not key:
        return False, "دخل الكود ديالك من فضلك."

    if key not in keys_db:
        return False, "الكود غير صحيح. تأكد من كتابته بشكل صحيح أو تواصل معنا."

    info = keys_db[key]
    expires = info.get("expires", "")
    if expires:
        try:
            expiry_date = datetime.strptime(expires, "%Y-%m-%d")
            if datetime.now() > expiry_date:
                return False, "هذا الكود انتهت صلاحيته. تواصل معنا لتجديده."
        except ValueError:
            pass

    max_uses = int(info.get("max_uses", 0) or 0)
    if info.get("type", "trial") == "trial" and not has_remaining_uses(key, max_uses):
        return False, "استهلكتي عدد المحاولات المسموح بيه فهاد الكود التجريبي. تواصل معنا للترقية لكود مدفوع."

    return True, ""


def _login_locked() -> int:
    """كترجع عدد الثواني الباقية للفتح مرة أخرى، أو 0 إلا ماكانش قفل."""
    locked_until = st.session_state.get("login_locked_until", 0)
    remaining = int(locked_until - time.time())
    return max(remaining, 0)


def gatekeeper() -> None:
    """شاشة الدخول: كتطلب كود التفعيل قبل عرض الأداة."""
    inject_custom_css()
    app_header("🔒 أداة سحب بيانات المنتجات", "أدخل كود التفعيل ديالك للمتابعة")

    lock_remaining = _login_locked()
    if lock_remaining > 0:
        st.error(
            f"⛔ تسجلات بزاف محاولات فاشلة. صبر {lock_remaining} ثانية وعاود جرب."
        )
        st.stop()

    key_input = st.text_input("كود التفعيل (Access Key)", type="password")
    submit = st.button("دخول ✅", use_container_width=True)

    if submit:
        keys_db = load_valid_keys()
        clean_key = key_input.strip()
        valid, message = is_key_valid(clean_key, keys_db)
        if valid:
            st.session_state["authenticated"] = True
            st.session_state["active_key"] = clean_key
            st.session_state["key_type"] = keys_db[clean_key].get("type", "trial")
            st.session_state["key_max_uses"] = int(keys_db[clean_key].get("max_uses", 0) or 0)
            st.session_state["key_expires"] = keys_db[clean_key].get("expires", "")
            st.session_state["login_attempts"] = 0
            st.rerun()
        else:
            attempts = st.session_state.get("login_attempts", 0) + 1
            st.session_state["login_attempts"] = attempts
            if attempts >= MAX_LOGIN_ATTEMPTS:
                st.session_state["login_locked_until"] = time.time() + LOGIN_LOCK_SECONDS
                st.session_state["login_attempts"] = 0
            st.error(message)

    st.markdown("---")
    st.caption(
        "ماعندكش كود؟ تواصل معنا فـ صفحة الفيسبوك أو الواتساب باش تجرب الأداة مجانا."
    )


# ---------------------------------------------------------------------------
# تصدير Excel / CSV
# ---------------------------------------------------------------------------
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """كنحولو DataFrame لملف Excel (bytes) بترميز متوافق مع العربية."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Products")
        worksheet = writer.sheets["Products"]
        worksheet.freeze_panes = "A2"
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 4
            worksheet.column_dimensions[chr(65 + i)].width = min(max_len, 60)
    return buffer.getvalue()


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """تصدير CSV بترميز utf-8-sig باش يتفتح مزيان فـ Excel مع الحروف العربية."""
    return df.to_csv(index=False).encode("utf-8-sig")


def numeric_price_series(df: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(df["الثمن"], errors="coerce")


# ---------------------------------------------------------------------------
# لوحة الإحصائيات
# ---------------------------------------------------------------------------
def show_stats(df: pd.DataFrame) -> None:
    prices = numeric_price_series(df)
    valid_prices = prices.dropna()

    col1, col2, col3, col4 = st.columns(4)
    stats = [
        (col1, str(len(df)), "عدد المنتجات"),
        (col2, f"{valid_prices.mean():.0f}" if not valid_prices.empty else "—", "متوسط الثمن"),
        (col3, f"{valid_prices.min():.0f}" if not valid_prices.empty else "—", "أرخص ثمن"),
        (col4, f"{valid_prices.max():.0f}" if not valid_prices.empty else "—", "أغلى ثمن"),
    ]
    for col, value, label in stats:
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="value">{value}</div>
                    <div class="label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if not valid_prices.empty and len(valid_prices) > 1:
        st.markdown("#### 📊 توزيع الأثمنة")
        st.bar_chart(valid_prices.reset_index(drop=True))


# ---------------------------------------------------------------------------
# الواجهة الرئيسية (بعد الدخول)
# ---------------------------------------------------------------------------
def sidebar_panel() -> None:
    with st.sidebar:
        st.success("✅ تم الدخول بنجاح")
        key_type = st.session_state.get("key_type", "trial")
        badge_class = "badge-paid" if key_type == "paid" else "badge-trial"
        badge_label = "مدفوع" if key_type == "paid" else "تجريبي"
        st.markdown(
            f'<span class="badge {badge_class}">{badge_label}</span>',
            unsafe_allow_html=True,
        )

        expires = st.session_state.get("key_expires", "")
        if expires:
            try:
                days_left = (datetime.strptime(expires, "%Y-%m-%d") - datetime.now()).days
                st.caption(f"⏳ باقي {max(days_left, 0)} يوم على انتهاء الكود")
            except ValueError:
                pass

        max_uses = st.session_state.get("key_max_uses", 0)
        if key_type == "trial" and max_uses:
            left = remaining_uses(st.session_state["active_key"], max_uses)
            st.caption(f"🔁 باقي لك {left} / {max_uses} محاولة سحب")

        st.markdown("---")
        if st.button("تسجيل الخروج 🚪", use_container_width=True):
            st.session_state.clear()
            st.rerun()


def main_app() -> None:
    inject_custom_css()
    sidebar_panel()
    app_header(
        "📦 أداة سحب بيانات المنتجات",
        "دخل رابط منتج أو متجر (Shopify / YouCan) وسحب البيانات فـ ثواني",
    )

    key_type = st.session_state.get("key_type", "trial")
    max_uses = st.session_state.get("key_max_uses", 0)
    active_key = st.session_state.get("active_key", "")

    st.markdown("##### 1️⃣ أدخل الرابط")
    url = st.text_input(
        "رابط المنتج أو المتجر",
        placeholder="https://example-store.com/products/some-product",
        label_visibility="collapsed",
    )

    max_products = st.slider(
        "أقصى عدد من المنتجات (فـ حالة رابط متجر/كاتيغوري)",
        min_value=5,
        max_value=200,
        value=MAX_PRODUCTS_DEFAULT,
        step=5,
    )

    # إلا كان الكود تجريبي وعندو حد أقصى وخلاصو -> نمنعو السحب
    trial_exhausted = (
        key_type == "trial" and max_uses and not has_remaining_uses(active_key, max_uses)
    )
    if trial_exhausted:
        st.warning("⛔ استهلكتي كل محاولات السحب ديال هاد الكود التجريبي. تواصل معنا للترقية.")

    scrape_clicked = st.button(
        "🚀 سحب البيانات",
        type="primary",
        use_container_width=True,
        disabled=bool(trial_exhausted),
    )

    if scrape_clicked:
        if not url or not url.startswith("http"):
            st.error("خاصك تدخل رابط صحيح يبدأ بـ http:// أو https://")
            return

        progress_bar = st.progress(0, text="جاري السحب...")
        status_text = st.empty()
        start_time = time.time()

        def update_progress(current, total, message):
            pct = int((current / total) * 100) if total else 0
            elapsed = time.time() - start_time
            progress_bar.progress(
                min(pct, 100), text=f"تم سحب {current}/{total} منتج ({elapsed:.0f} ثانية)"
            )
            status_text.caption(message)

        try:
            with st.spinner("كنسحبو البيانات، صبر شوية..."):
                products = scrape_store(
                    url, max_products=max_products, progress_callback=update_progress
                )
        except ScrapeError as e:
            st.error(f"⚠️ وقع مشكل: {e}")
            return
        except Exception as e:
            st.error(f"⚠️ وقع مشكل غير متوقع: {e}")
            return
        finally:
            progress_bar.empty()
            status_text.empty()

        if not products:
            st.warning("ما لقيناش شي منتج فهاد الرابط. تأكد من الرابط وعاود جرب.")
            return

        # نسجلو الاستعمال (غير للأكواد التجريبية لي عندها حد أقصى)
        if key_type == "trial" and max_uses:
            record_use(active_key)

        df = pd.DataFrame(products)
        df = df.rename(
            columns={
                "title": "العنوان",
                "price": "الثمن",
                "currency": "العملة",
                "image": "رابط الصورة",
                "url": "رابط المنتج",
                "source": "المصدر",
            }
        )
        st.session_state["last_df"] = df

    df = st.session_state.get("last_df")
    if df is not None and not df.empty:
        st.success(f"✅ تم سحب {len(df)} منتج بنجاح!")
        show_stats(df)

        st.markdown("##### 2️⃣ تصفية وبحث")
        col_search, col_price = st.columns([2, 1])
        with col_search:
            search_term = st.text_input("🔍 بحث فـ العنوان", placeholder="مثلا: سماعات")
        with col_price:
            sort_choice = st.selectbox(
                "الترتيب", ["بدون ترتيب", "الثمن (تصاعدي)", "الثمن (تنازلي)"]
            )

        filtered_df = df.copy()
        if search_term:
            filtered_df = filtered_df[
                filtered_df["العنوان"].astype(str).str.contains(search_term, case=False, na=False)
            ]
        if sort_choice != "بدون ترتيب":
            temp_prices = pd.to_numeric(filtered_df["الثمن"], errors="coerce")
            filtered_df = filtered_df.assign(_p=temp_prices).sort_values(
                "_p", ascending=(sort_choice == "الثمن (تصاعدي)")
            ).drop(columns="_p")

        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

        st.markdown("##### 3️⃣ تحميل الملف")
        col_xlsx, col_csv = st.columns(2)
        with col_xlsx:
            st.download_button(
                label="⬇️ Excel (.xlsx)",
                data=to_excel_bytes(filtered_df),
                file_name=f"products_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col_csv:
            st.download_button(
                label="⬇️ CSV",
                data=to_csv_bytes(filtered_df),
                file_name=f"products_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
            )


# ---------------------------------------------------------------------------
# نقطة الدخول
# ---------------------------------------------------------------------------
def main() -> None:
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        gatekeeper()
    else:
        main_app()


if __name__ == "__main__":
    main()
