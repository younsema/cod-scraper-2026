"""
usage_tracker.py
-----------------
كنتبعو عدد مرات استعمال كل كود تجريبي (trial) باش نطبقو حد "max_uses"
لي كنحطوه فـ secrets.toml.

⚠️ ملاحظة مهمة (حدود التخزين فـ Streamlit Cloud المجاني):
الملف اللي كنخزنو فيه العداد (data/usage.json) موجود فـ الـ disk المؤقت
ديال الـ instance. هادشي كايخدم مزيان بحال التطبيق خدام، ولكن إلا التطبيق
تعاود عليه deploy أو نام (sleep) وتفاق، العداد يمكن يترجع لـ صفر.
باش يكون العداد دائم 100%، خاصك تخزنو فـ قاعدة بيانات خارجية (مثلا
Supabase / Google Sheets / Firebase) — هادشي خارج نطاق هاد النسخة.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from threading import Lock

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_USAGE_FILE = os.path.join(_DATA_DIR, "usage.json")
_LOCK = Lock()


def _ensure_data_dir() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)


def _load() -> dict:
    _ensure_data_dir()
    if not os.path.exists(_USAGE_FILE):
        return {}
    try:
        with open(_USAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    _ensure_data_dir()
    tmp_path = _USAGE_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, _USAGE_FILE)


def get_uses(key: str) -> int:
    """عدد المرات لي تسحب بيها هاد الكود لحد الآن."""
    with _LOCK:
        data = _load()
        return int(data.get(key, {}).get("count", 0))


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
    """كنزيدو 1 فعداد الاستعمال ديال الكود، وكنرجعو العدد الجديد."""
    with _LOCK:
        data = _load()
        entry = data.get(key, {"count": 0, "first_used": None, "last_used": None})
        entry["count"] = int(entry.get("count", 0)) + 1
        now = datetime.now().isoformat(timespec="seconds")
        if not entry.get("first_used"):
            entry["first_used"] = now
        entry["last_used"] = now
        data[key] = entry
        _save(data)
        return entry["count"]
