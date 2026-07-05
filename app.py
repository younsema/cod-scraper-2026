"""
app.py
------
تطبيق Streamlit لسحب بيانات المنتجات من متاجر Shopify و YouCan
وتصديرها كملف Excel منظم.

نظام الحماية:
- الأكواد المقبولة (VALID_KEYS) كتقرا من st.secrets، ماشي مكتوبة فالكود.
- خاصك تزيدها فـ Streamlit Cloud > Settings > Secrets (شوف .streamlit/secrets.toml.example)
"""

from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st

from scraper import ScrapeError, scrape_store

# ---------------------------------------------------------------------------
# إعدادات الصفحة
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="أداة سحب بيانات المنافسين | COD Morocco",
    page_icon="📦",
    layout="centered",
)

MAX_PRODUCTS_DEFAULT = 60


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
    - max_uses: عدد مرات الاستعمال المسموحة للكود التجريبي (0 = بلا حدود)
    """
    if "keys" in st.secrets:
        return dict(st.secrets["keys"])
    return {}


def is_key_valid(key: str, keys_db: dict) -> tuple[bool, str]:
    if key not in keys_db:
        return False, "الكود غير صحيح. تأكد من كتابته بشكل صحيح أو تواصل معنا."

    info = keys_db[key]
    expires = info.get("expires", "")
    if expires:
        try:
            expiry_date = datetime.strptime(expires, "%Y-%m-%d")
            if datetime.now() > expiry_date:
                return False, "هذا الكود انتهت صلاحيته."
        except ValueError:
            pass

    return True, ""


def gatekeeper():
    """شاشة الدخول: كتطلب كود التفعيل قبل عرض الأداة."""
    st.markdown(
        "<h2 style='text-align:center;'>🔒 أداة سحب بيانات المنتجات</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color:gray;'>أدخل كود التفعيل ديالك للمتابعة</p>",
        unsafe_allow_html=True,
    )

    key_input = st.text_input("كود التفعيل (Access Key)", type="password")
    col1, col2 = st.columns([1, 1])
    with col1:
        submit = st.button("دخول ✅", use_container_width=True)

    if submit:
        keys_db = load_valid_keys()
        valid, message = is_key_valid(key_input.strip(), keys_db)
        if valid:
            st.session_state["authenticated"] = True
            st.session_state["active_key"] = key_input.strip()
            st.session_state["key_type"] = keys_db[key_input.strip()].get("type", "trial")
            st.rerun()
        else:
            st.error(message)

    st.markdown("---")
    st.caption(
        "ماعندكش كود؟ تواصل معنا فـ صفحة الفيسبوك أو الواتساب باش تجرب الأداة مجانا."
    )


# ---------------------------------------------------------------------------
# تصدير Excel
# ---------------------------------------------------------------------------
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """كنحولو DataFrame لملف Excel (bytes) بترميز متوافق مع العربية."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Products")
        worksheet = writer.sheets["Products"]
        # عرض تلقائي للأعمدة
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 4
            worksheet.column_dimensions[chr(65 + i)].width = min(max_len, 60)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# الواجهة الرئيسية (بعد الدخول)
# ---------------------------------------------------------------------------
def main_app():
    st.markdown(
        "<h2 style='text-align:center;'>📦 أداة سحب بيانات المنتجات</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color:gray;'>"
        "دخل رابط منتج أو متجر (Shopify / YouCan) وسحب البيانات فـ ثواني</p>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.success(f"✅ تم الدخول بنجاح")
        st.caption(f"نوع الكود: {st.session_state.get('key_type', 'trial')}")
        if st.button("تسجيل الخروج 🚪"):
            st.session_state.clear()
            st.rerun()

    st.markdown("### 1️⃣ أدخل الرابط")
    url = st.text_input(
        "رابط المنتج أو المتجر",
        placeholder="https://example-store.com/products/some-product",
    )

    max_products = st.slider(
        "أقصى عدد من المنتجات (فـ حالة رابط متجر/كاتيغوري)",
        min_value=5,
        max_value=200,
        value=MAX_PRODUCTS_DEFAULT,
        step=5,
    )

    scrape_clicked = st.button("🚀 سحب البيانات", type="primary", use_container_width=True)

    if scrape_clicked:
        if not url or not url.startswith("http"):
            st.error("خاصك تدخل رابط صحيح يبدأ بـ http:// أو https://")
            return

        progress_bar = st.progress(0, text="جاري السحب...")
        status_text = st.empty()

        def update_progress(current, total, message):
            pct = int((current / total) * 100) if total else 0
            progress_bar.progress(min(pct, 100), text=f"تم سحب {current}/{total} منتج")
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

        progress_bar.empty()
        status_text.empty()

        if not products:
            st.warning("ما لقيناش شي منتج فهاد الرابط. تأكد من الرابط وعاود جرب.")
            return

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

        st.success(f"✅ تم سحب {len(df)} منتج بنجاح!")
        st.dataframe(df, use_container_width=True, hide_index=True)

        excel_bytes = to_excel_bytes(df)
        st.download_button(
            label="⬇️ تحميل ملف Excel",
            data=excel_bytes,
            file_name=f"products_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


# ---------------------------------------------------------------------------
# نقطة الدخول
# ---------------------------------------------------------------------------
def main():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        gatekeeper()
    else:
        main_app()


if __name__ == "__main__":
    main()
