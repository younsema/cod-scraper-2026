import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
import io

# 1. إعدادات وتسمية الصفحة
st.set_page_config(page_title="COD Scraper Pro", page_icon="🚀", layout="centered")

# لستة الأكواد المقبولة (تقدر تبدلها أو تزيد فيها مستقبلاً)
VALID_KEYS = ["TEST-FREE-00", "VIP-COD-2026", "USER-150DH"]

# 2. نظام حماية الجلسة (قفل الموقع)
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 نظام سحب المنتجات - تسجيل الدخول")
    st.write("مرحباً بك! يرجى إدخال كود التفعيل للولوج إلى الأداة.")
    
    access_key = st.text_input("كود التفعيل (Access Key):", type="password")
    login_btn = st.button("تفعيل الدخول 🚀")
    
    if login_btn:
        if access_key in VALID_KEYS:
            st.session_state["authenticated"] = True
            st.success("تم التفعيل بنجاح! جاري تحويلك...")
            st.rerun()
        else:
            st.error("الكود غير صحيح! يرجى التواصل مع الدعم للحصول على كود شغّال.")
    st.stop()

# -------------------------------------------------------------
# الواجهة الرئيسية (كتظهر فقط يلا كان الكود صحيح)
# -------------------------------------------------------------

st.title("🚀 COD Product Scraper")
st.subheader("اسحب منتجات منافسيك في أقل من دقيقة وحولها لملف Excel منظم")

# زر تسجيل الخروج ف الجنب
if st.sidebar.button("تسجيل الخروج 🚪"):
    st.session_state["authenticated"] = False
    st.rerun()

# خانات إدخال البيانات للزبون
target_url = st.text_input("ضع رابط المتجر المنافس هنا (مثال: https://store.com):")
platform = st.selectbox("نوع المنصة:", ["Shopify", "YouCan"])

def scrape_shopify(url):
    if not url.endswith("/"):
        url += "/"
    json_url = f"{url}products.json?limit=50"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(json_url, headers=headers)
    
    if response.status_code != 200:
        return None
        
    data = response.json()
    products_list = []
    
    for prod in data.get("products", []):
        title = prod.get("title")
        handle = prod.get("handle")
        prod_url = f"{url}products/{handle}"
        
        images = prod.get("images", [])
        image_url = images[0].get("src") if images else "لا توجد صورة"
        
        variants = prod.get("variants", [])
        price = variants[0].get("price") if variants else "غير محدد"
        
        products_list.append({
            "العنوان": title,
            "الثمن": price,
            "رابط الصورة": image_url,
            "رابط المنتج": prod_url
        })
    return products_list

def scrape_youcan(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if "/products" not in url:
        if not url.endswith("/"): url += "/"
        url += "products"
        
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
        
    soup = BeautifulSoup(response.text, 'html.parser')
    products_list = []
    
    items = soup.find_all('div', class_='product-item') or soup.find_all('div', class_='product')
    
    for item in items:
        try:
            title_tag = item.find('h3') or item.find('h2') or item.find('a', class_='title')
            title = title_tag.text.strip() if title_tag else "منتج بدون عنوان"
            
            link_tag = item.find('a')
            prod_url = link_tag['href'] if link_tag else url
            if prod_url.startswith('/'):
                prod_url = url.split('/products')[0] + prod_url
                
            price_tag = item.find('span', class_='price') or item.find('div', class_='price')
            price = price_tag.text.strip() if price_tag else "غير محدد"
            
            img_tag = item.find('img')
            image_url = img_tag['src'] if img_tag else "لا توجد صورة"
            
            products_list.append({
                "العنوان": title,
                "الثمن": price,
                "رابط الصورة": image_url,
                "رابط المنتج": prod_url
            })
        except Exception as e:
            continue
            
    return products_list

# زر تشغيل السكرايبر
if st.button("ابدأ السحب الآن ⚡"):
    if not target_url:
        st.warning("المرجو إدخال رابط أولاً!")
    else:
        with st.spinner("جاري جلب البيانات وتحليل المتجر..."):
            try:
                if platform == "Shopify":
                    results = scrape_shopify(target_url)
                else:
                    results = scrape_youcan(target_url)
                
                if results:
                    df = pd.DataFrame(results)
                    st.success(f"🎉 تم سحب {len(df)} منتج بنجاح!")
                    
                    st.dataframe(df)
                    
                    # تحويل البيانات لملف Excel يقبل العربية بوضوح
                    towrite = io.BytesIO()
                    df.to_excel(towrite, index=False, header=True, engine='openpyxl')
                    towrite.seek(0)
                    
                    st.download_button(
                        label="📥 تحميل ملف Excel المنظم",
                        data=towrite,
                        file_name="cod_products_extracted.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.error("لم نتمكن من سحب البيانات. تأكد من الرابط أو نوع المنصة.")
            except Exception as e:
                st.error(f"حدث خطأ غير متوقع: {e}")