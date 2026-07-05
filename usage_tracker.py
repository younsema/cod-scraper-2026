"""
usage_tracker.py
-----------------
كنتبعو عدد مرات استعمال كل كود تجريبي (trial) عبر قاعدة بيانات Supabase،
باش العداد يبقى دائم حتى ملي التطبيق يعاود deploy أو ينعس فـ Streamlit
Cloud المجاني (المشكل اللي كان كاين مع الملف المحلي data/usage.json).

الإعداد المطلوب فـ secrets.toml:

[supabase]
url = "https://xxxxxxxxxxxx.supabase.co"
key = "eyJhbGciOi....."   # service_role key

⚠️ ملاحظة أمان مهمة:
service_role key كيدير bypass للـ Row Level Security ديال Supabase.
هادشي آمن هنا لأن هاد الكود كيخدم فـ السيرفر (Python/Streamlit backend)
وماشي فـ متصفح الزبون — يعني هاد المفتاح أبدا ما غادي يوصل لجهاز الزبون.
غير تأكد بلي:
  1. secrets.toml ماشي مرفوع لـ GitHub (موجود فـ .gitignore).
  2. ما تديرش print() ولا st.write() لهاد المفتاح فـ أي رسالة خطأ.

قبل الاستعمال، خاصك تشغل السكريبت supabase_setup.sql مرة وحدة فـ
Supabase > SQL Editor باش يتخلق الجدول والدالة اللي محتاجهم هاد الملف.
"""

from __future__ import annotations

import streamlit as st
import requests

REQUEST_TIMEOUT = 10


def _get_config() -> tuple[str, str]:
    """كنقراو url و key ديال Supabase من secrets، مع رسالة واضحة إلا كانوا ناقصين."""
    try:
        cfg = st.secrets["supabase"]
        return cfg["url"].rstrip("/"), cfg["key"]
    except (KeyError, AttributeError) as e:
        raise RuntimeError(
            "إعدادات Supabase ناقصة فـ secrets.toml. خاصك تزيد قسم [supabase] "
            "فيه url و key (شوف secrets.toml.example)."
        ) from e


def _headers(api_key: str) -> dict:
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def get_uses(key: str) -> int:
    """عدد المرات لي تسحب بيها هاد الكود لحد الآن."""
    base_url, api_key = _get_config()
    try:
        resp = requests.get(
            f"{base_url}/rest/v1/usage_counters",
            headers=_headers(api_key),
            params={"key": f"eq.{key}", "select": "count"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        rows = resp.json()
        return int(rows[0]["count"]) if rows else 0
    except (requests.RequestException, ValueError, KeyError, IndexError):
        # إلا وقع مشكل مؤقت فالاتصال بـ Supabase، كنرجعو 0 باش ما نوقفوش
        # الأداة كاملة بسبب مشكل خارجي عابر (ثمن بسيط: احتمال يستافد
        # الزبون بمحاولة زيادة إلا صادف outage قصير جدا).
        return 0


def has_remaining_uses(key: str, max_uses: int) -> bool:
    """max_uses == 0 يعني بلا حدود."""
    if not max_uses:
        return True
    return get_uses(key) < max_uses


def remaining_uses(key: str, max_uses: int):
    """كترجع None إلا كان بلا حدود، ولا عدد المرات الباقية."""
    if not max_uses:
        return None
    return max(max_uses - get_uses(key), 0)


def record_use(key: str) -> int:
    """
    كنزيدو 1 فعداد الاستعمال ديال الكود عبر دالة SQL atomic (increment_usage)
    باش نتفاداو مشاكل التزامن إلا كان أكثر من زبون كيسحب فنفس الوقت.
    """
    base_url, api_key = _get_config()
    try:
        resp = requests.post(
            f"{base_url}/rest/v1/rpc/increment_usage",
            headers=_headers(api_key),
            json={"key_input": key},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return int(resp.json())
    except (requests.RequestException, ValueError):
        # إلا فشل التسجيل، الأحسن نخليو الزبون يكمل عمليتو بدل ما نوقفوها،
        # وغير هاد المرة بالذات ماغاديش تتحسب فالعداد.
        return get_uses(key)
