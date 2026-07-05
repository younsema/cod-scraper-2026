# 📦 أداة سحب بيانات المنتجات (COD Morocco Scraper)

أداة ويب بسيطة كتمكنك تسحب بيانات المنتجات (العنوان، الثمن، الصورة، الرابط)
من متاجر Shopify و YouCan فـ أقل من دقيقة، وتصدرها كملف Excel.

---

## 1) التشغيل محلياً (على جهازك) قبل النشر

```bash
# 1. ثبت المتطلبات
pip install -r requirements.txt

# 2. سمي secrets.toml.example ب secrets.toml
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# 3. بدل الأكواد بالأكواد ديالك فـ .streamlit/secrets.toml

# 4. شغل التطبيق
streamlit run app.py
```

غادي يفتح فـ المتصفح على `http://localhost:8501`

---

## 2) النشر المجاني 100% (GitHub + Streamlit Cloud)

### الخطوة أ: رفع الكود لـ GitHub

1. أنشئ حساب فـ [github.com](https://github.com) إلا ماعندكش.
2. أنشئ Repository جديد (يقدر يكون **Public**، لا مشكل، لأن الأكواد السرية
   ماغاديش تكون فـ الكود بفضل نظام secrets).
3. ارفع ليه هاد الملفات:
   - `app.py`
   - `scraper.py`
   - `requirements.txt`
   - `.gitignore`
   - **ملا ترفعش** `.streamlit/secrets.toml` (الملف الحقيقي فيه الأكواد ديال الزبناء)

```bash
git init
git add app.py scraper.py requirements.txt .gitignore README.md
git commit -m "أول نسخة من الأداة"
git branch -M main
git remote add origin https://github.com/USERNAME/REPO_NAME.git
git push -u origin main
```

### الخطوة ب: الربط مع Streamlit Cloud

1. دخل لـ [share.streamlit.io](https://share.streamlit.io)
2. اربط حساب GitHub ديالك.
3. اختار الـ Repository لي رفعتي، والملف الرئيسي: `app.py`
4. قبل ما تدوس Deploy، دوس على **Advanced settings > Secrets** وحط:

```toml
[keys]
"TEST-FREE-00" = { type = "trial", expires = "2026-12-31", max_uses = 0 }
"CLIENT-AHMED-01" = { type = "paid", expires = "", max_uses = 0 }
```

5. دوس **Deploy**. بعد دقيقة أو دقيقتين غادي يعطيك رابط من نوع:
   `https://your-app-name.streamlit.app`

هاد الرابط هو لي غادي تبعتو للزبناء ديالك.

---

## 3) كيفاش تزيد / تحذف كود تفعيل لزبون جديد (بلا ماتلمس الكود)

1. دخل لـ [share.streamlit.io](https://share.streamlit.io) > التطبيق ديالك
2. Settings > Secrets
3. زيد سطر جديد بهاد الشكل:

```toml
"CLIENT-FATIMA-02" = { type = "paid", expires = "", max_uses = 0 }
```

4. Save. التطبيق غادي يتحدث لايف فـ ثوانٍ، بلا ما تعاود تدير Deploy.

**لحذف كود**: غير امسح السطر ديالو من الـ Secrets و Save.

**لكود تجربة بتاريخ محدود**: حط `expires = "2026-08-15"` مثلا، والكود
غادي يخرج من الخدمة أوتوماتيكيا بعد هاد التاريخ.

---

## 4) كيفاش تخدم الأداة

1. الزبون كيدخل الرابط ديال الموقع (`*.streamlit.app`)
2. كيدخل كود التفعيل ديالو
3. كيلصق رابط منتج واحد، أو رابط متجر/كاتيغوري كامل
4. الأداة كتسحب البيانات وتعرضها فـ جدول
5. زر "تحميل ملف Excel" كيعطيه ملف `.xlsx` جاهز

### أنواع الروابط المدعومة

| نوع الرابط | كيفاش كتخدم |
|---|---|
| رابط منتج Shopify واحد | كتسحب JSON-LD مباشرة |
| رابط متجر Shopify كامل | كتستعمل `/products.json` (الأسرع، كيجيب المتجر كامل) |
| رابط منتج YouCan واحد | كتسحب meta tags / JSON-LD |
| رابط كاتيغوري/متجر YouCan | كتلقط روابط المنتجات وتزورهم واحد واحد |

---

## 5) ملاحظات مهمة

- **الأداء**: سحب متجر كامل (100+ منتج) يقدر ياخد بضع دقائق حسب سرعة الموقع
  المستهدف، لأن الأداة كتحترم delay بين الطلبات باش ما تبانش كـ هجوم.
- **الحماية القانونية**: الأداة كتسحب غير المعلومات العمومية المعروضة للزوار
  (العنوان، الثمن، الصورة)، وماكتدخلش لأي حساب أو معلومات خاصة.
- **حدود Streamlit Cloud المجاني**: التطبيقات المجانية عندها حدود فـ الموارد
  (RAM/CPU)، إلا كبر عدد المستخدمين بزاف يمكن تحتاج نسخة مدفوعة أو استضافة
  أخرى (Render, Railway...).

---

## 6) البنية التقنية

```
cod-scraper-app/
├── app.py                          # الواجهة + نظام الحماية + التصدير
├── scraper.py                      # منطق سحب البيانات (Shopify + YouCan)
├── requirements.txt                # المكتبات المطلوبة
├── .gitignore                      # باش ما نرفعوش secrets.toml الحقيقي
└── .streamlit/
    └── secrets.toml.example        # مثال، ديرو نسخة بلا .example محليا
```
