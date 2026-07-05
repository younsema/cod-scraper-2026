"""
scraper.py
----------
منطق سحب بيانات المنتجات من متاجر Shopify و YouCan.

الفكرة العامة:
1. نكتشفو نوع المنصة (Shopify / YouCan / غير معروف).
2. إلا كان رابط "صفحة منتج واحد" -> كنسحبو JSON-LD أو meta tags.
3. إلا كان رابط "متجر / كولكسيون" -> كنجربو endpoint ديال Shopify (/products.json)
   أو كنقرأو صفحة الـ listing وكنسحبو الروابط ديال المنتجات ثم نزورهم واحد واحد.

كل الدوال كترجع dict موحد بهاد الشكل:
{
    "title": str,
    "price": str,
    "currency": str,
    "image": str,
    "url": str,
    "source": "Shopify" / "YouCan" / "Unknown"
}
"""

import json
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15
DELAY_BETWEEN_REQUESTS = 1.0  # ثانية، باش ما نضغطوش بزاف على السيرفر ديال الموقع


class ScrapeError(Exception):
    pass


def _get(url):
    """طلب GET آمن مع معالجة الأخطاء."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp
    except requests.exceptions.RequestException as e:
        raise ScrapeError(f"تعذر الوصول للرابط: {url} — {e}")


def detect_platform(html_text: str, url: str) -> str:
    """كنحاولو نعرفو شنو هي المنصة اعتمادا على محتوى الصفحة."""
    lower = html_text.lower()
    if "cdn.shopify.com" in lower or "shopify" in lower or "myshopify.com" in url:
        return "Shopify"
    if "youcan" in lower or "youcanbuild" in lower:
        return "YouCan"
    return "Unknown"


def _extract_json_ld_product(soup: BeautifulSoup):
    """كنقرأو الـ JSON-LD (schema.org/Product) إلا كان موجود، خدام مزيان مع Shopify و YouCan."""
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type", "")
            if isinstance(item_type, list):
                is_product = "Product" in item_type
            else:
                is_product = item_type == "Product"
            if not is_product:
                continue

            title = item.get("name")
            image = item.get("image")
            if isinstance(image, list):
                image = image[0] if image else None
            elif isinstance(image, dict):
                image = image.get("url")

            offers = item.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = offers.get("price") if isinstance(offers, dict) else None
            currency = offers.get("priceCurrency") if isinstance(offers, dict) else None

            if title:
                return {
                    "title": title,
                    "price": price,
                    "currency": currency,
                    "image": image,
                }
    return None


def _extract_meta_fallback(soup: BeautifulSoup):
    """إلا ما لقيناش JSON-LD، كنرجعو لـ meta tags (og:title, og:image, og:price...)."""

    def meta(name_or_prop):
        tag = soup.find("meta", attrs={"property": name_or_prop}) or soup.find(
            "meta", attrs={"name": name_or_prop}
        )
        return tag.get("content") if tag else None

    title = meta("og:title") or (soup.title.string.strip() if soup.title else None)
    image = meta("og:image")
    price = meta("product:price:amount") or meta("og:price:amount")
    currency = meta("product:price:currency") or meta("og:price:currency")

    return {
        "title": title,
        "price": price,
        "currency": currency,
        "image": image,
    }


def scrape_single_product(url: str) -> dict:
    """كنسحبو معلومات منتج واحد من رابطو المباشر (Shopify أو YouCan أو أي موقع آخر)."""
    resp = _get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    platform = detect_platform(resp.text, url)

    data = _extract_json_ld_product(soup)
    if not data or not data.get("title"):
        data = _extract_meta_fallback(soup)

    if not data.get("title"):
        # آخر محاولة: أول h1 فالصفحة
        h1 = soup.find("h1")
        data["title"] = h1.get_text(strip=True) if h1 else "بدون عنوان"

    # تنظيف الثمن (إزالة رموز العملة والفراغات إلا كان الثمن نص وماشي رقم صافي)
    price_raw = data.get("price")
    price_clean = None
    if price_raw:
        match = re.search(r"[\d]+([.,]\d+)?", str(price_raw))
        price_clean = match.group(0) if match else str(price_raw)

    return {
        "title": (data.get("title") or "").strip(),
        "price": price_clean or "",
        "currency": data.get("currency") or "",
        "image": urljoin(url, data.get("image")) if data.get("image") else "",
        "url": url,
        "source": platform,
    }


def get_shopify_products_json(store_url: str, max_products: int = 250) -> list:
    """
    كنستعملو الـ endpoint العمومي ديال Shopify: /products.json
    كايخدم مع أي متجر Shopify بدون الحاجة لمفتاح API.
    """
    parsed = urlparse(store_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    products = []
    page = 1
    per_page = 50  # الحد الأقصى لـ Shopify فـ كل صفحة

    while len(products) < max_products:
        endpoint = f"{base}/products.json?limit={per_page}&page={page}"
        resp = _get(endpoint)
        try:
            payload = resp.json()
        except ValueError:
            break

        items = payload.get("products", [])
        if not items:
            break

        for p in items:
            title = p.get("title", "")
            handle = p.get("handle", "")
            product_url = f"{base}/products/{handle}"
            image = ""
            images = p.get("images", [])
            if images:
                image = images[0].get("src", "")

            price = ""
            currency = ""
            variants = p.get("variants", [])
            if variants:
                price = variants[0].get("price", "")

            products.append(
                {
                    "title": title,
                    "price": price,
                    "currency": currency,
                    "image": image,
                    "url": product_url,
                    "source": "Shopify",
                }
            )

        page += 1
        time.sleep(DELAY_BETWEEN_REQUESTS)

        if len(items) < per_page:
            break  # ما بقاش صفحات أخرى

    return products[:max_products]


def discover_product_links(listing_url: str, max_links: int = 100) -> list:
    """
    كنقرأو صفحة "متجر / كاتيغوري" (غالبا YouCan أو أي منصة أخرى)
    وكنلقاطو الروابط لي فيها "/product" أو "/products" فـ الـ href.
    """
    resp = _get(listing_url)
    soup = BeautifulSoup(resp.text, "html.parser")

    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/(product|products)/", href):
            full_url = urljoin(listing_url, href)
            links.add(full_url)
        if len(links) >= max_links:
            break

    return list(links)


def scrape_store(url: str, max_products: int = 60, progress_callback=None) -> list:
    """
    الدالة الرئيسية: كتاخد رابط (منتج واحد، أو متجر/كاتيغوري) وكترجع
    لستة ديال المنتجات (dict لكل منتج).

    progress_callback(current, total, message) -> اختياري، باش نحدثو progress bar فـ Streamlit
    """
    resp = _get(url)
    platform = detect_platform(resp.text, url)

    # 1) إلا كان Shopify -> نجربو /products.json مباشرة (الأسرع والأدق)
    if platform == "Shopify":
        try:
            products = get_shopify_products_json(url, max_products=max_products)
            if products:
                return products
        except ScrapeError:
            pass  # نكملو بالطريقة العادية إلا فشل

    # 2) صفحة منتج واحد مباشرة (فيها JSON-LD ديال Product)
    soup = BeautifulSoup(resp.text, "html.parser")
    single = _extract_json_ld_product(soup)
    looks_like_listing = len(soup.find_all("a", href=re.compile(r"/(product|products)/"))) > 3

    if single and not looks_like_listing:
        return [scrape_single_product(url)]

    # 3) صفحة listing (كاتيغوري / متجر) -> نلقاطو الروابط ونزورهم واحد واحد
    links = discover_product_links(url, max_links=max_products)
    if not links:
        # ماكاينش روابط -> نعتبروها صفحة منتج واحد بأي حال
        return [scrape_single_product(url)]

    results = []
    total = len(links)
    for i, link in enumerate(links, start=1):
        try:
            product = scrape_single_product(link)
            results.append(product)
        except ScrapeError:
            continue
        if progress_callback:
            progress_callback(i, total, link)
        time.sleep(DELAY_BETWEEN_REQUESTS)

    return results
