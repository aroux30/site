target = ".arena/run-20261125-190622-s622418/r0/a008.md"
part = """#### 5.2 Layer 2: Studio Inspector Panel (`frontend/components/admin/builder/inspector-panel.tsx`)

```diff
--- a/frontend/components/admin/builder/inspector-panel.tsx
+++ b/frontend/components/admin/builder/inspector-panel.tsx
@@ -638,7 +638,7 @@ export function InspectorPanel() {
                 value={String(props.input_type || "text")}
                 onValueChange={(val) => handlePropChange("input_type", val)}
               >
-                <SelectTrigger className="h-8 text-xs">
+                <SelectTrigger data-testid="form-input-type-select" className="h-8 text-xs">
                   <SelectValue />
                 </SelectTrigger>
-                <SelectContent>
+                <SelectContent className="z-[150]">
                   <SelectItem value="text">متن عادی (Text)</SelectItem>
                   <SelectItem value="email">ایمیل (Email)</SelectItem>
                   <SelectItem value="tel">تلفن همراه (Tel)</SelectItem>
@@ -654,6 +654,7 @@ export function InspectorPanel() {
             <div className="flex items-center justify-between pt-1">
               <Label className="text-xs">فیلد اجباری (Required)</Label>
               <Switch
+                data-testid="form-input-required-switch"
                 checked={Boolean(props.required)}
                 onCheckedChange={(val) => handlePropChange("required", val)}
               />
@@ -1164,7 +1165,7 @@ export function InspectorPanel() {
               <Label className="text-xs">آدرس اندپوینت ثبت فرم (Action URL)</Label>
               <Input
                 data-testid="form-container-submit-url"
-                value={String(props.submit_url || "/api/v1/content/forms/submit")}
+                value={String(props.submit_url ?? "/api/v1/content/forms/submit")}
                 onChange={(e) => handlePropChange("submit_url", e.target.value)}
                 className="h-8 text-xs font-mono"
                 dir="ltr"
@@ -1174,7 +1175,7 @@ export function InspectorPanel() {
               <Label className="text-xs">پیام موفقیت‌آمیز ثبت</Label>
               <Input
                 data-testid="form-container-success-input"
-                value={String(props.success_message || "پیام شما با موفقیت ثبت شد.")}
+                value={String(props.success_message ?? "پیام شما با موفقیت ثبت شد.")}
                 onChange={(e) => handlePropChange("success_message", e.target.value)}
                 className="h-8 text-xs"
               />
@@ -1182,7 +1183,7 @@ export function InspectorPanel() {
             <div className="space-y-1.5">
               <Label className="text-xs">پیام خطا در ارسال</Label>
               <Input
-                value={String(props.error_message || "خطا در ارسال فرم. لطفاً فیلدها را بررسی نمایید.")}
+                data-testid="form-container-error-input"
                 value={String(props.error_message ?? "خطا در ارسال فرم. لطفاً فیلدها را بررسی نمایید.")}
                 onChange={(e) => handlePropChange("error_message", e.target.value)}
                 className="h-8 text-xs"
@@ -1197,6 +1198,7 @@ export function InspectorPanel() {
               <Label className="text-xs">متن چک‌باکس</Label>
               <Input
+                data-testid="form-checkbox-label-input"
                 value={String(props.label || "شرایط و قوانین را مطالعه کرده و می‌پذیرم")}
                 onChange={(e) => handlePropChange("label", e.target.value)}
                 className="h-8 text-xs"
@@ -1205,6 +1207,7 @@ export function InspectorPanel() {
             <div className="space-y-1.5">
               <Label className="text-xs">نام فیلد (Field Name)</Label>
               <Input
+                data-testid="form-checkbox-name-input"
                 value={String(props.name || "accept_terms")}
                 onChange={(e) => handlePropChange("name", e.target.value)}
                 className="h-8 text-xs font-mono"
@@ -1320,6 +1323,7 @@ export function InspectorPanel() {
               <Label className="text-xs">عنوان شمارنده</Label>
               <Input
+                data-testid="countdown-title-input"
                 value={String(props.title || "مهلت تخفیف ویژه")}
                 onChange={(e) => handlePropChange("title", e.target.value)}
                 className="h-8 text-xs"
@@ -1328,6 +1332,7 @@ export function InspectorPanel() {
             <div className="space-y-1.5">
               <Label className="text-xs">تاریخ و ساعت پایان (ISO 8601)</Label>
               <Input
+                data-testid="countdown-date-input"
                 value={String(props.target_date || "")}
                 onChange={(e) => handlePropChange("target_date", e.target.value)}
                 className="h-8 text-xs font-mono"
@@ -2436,7 +2441,7 @@ export function InspectorPanel() {
                 <SelectTrigger data-testid="offcanvas-position-select" className="h-8 text-xs">
                   <SelectValue />
                 </SelectTrigger>
-                <SelectContent>
+                <SelectContent className="z-[150]">
                   <SelectItem value="right">راست (Right - پیش‌فرض RTL)</SelectItem>
                   <SelectItem value="left">چپ (Left)</SelectItem>
                   <SelectItem value="top">بالا (Top)</SelectItem>
@@ -2448,6 +2453,7 @@ export function InspectorPanel() {
               <Label className="text-xs">عرض کشو (پیکسل)</Label>
               <Input
+                data-testid="offcanvas-width-input"
                 type="number"
                 min={200}
                 max={800}
@@ -2471,7 +2477,7 @@ export function InspectorPanel() {
                 <SelectTrigger data-testid="popup-trigger-select" className="h-8 text-xs">
                   <SelectValue />
                 </SelectTrigger>
-                <SelectContent>
+                <SelectContent className="z-[150]">
                   <SelectItem value="on_scroll">هنگام اسکرول به درصد معین</SelectItem>
                   <SelectItem value="on_load">بلافاصله پس از بارگذاری برگه</SelectItem>
                   <SelectItem value="exit_intent">هنگام خروج ماوس از صفحه</SelectItem>
@@ -2482,6 +2488,7 @@ export function InspectorPanel() {
               <Label className="text-xs">درصد اسکرول تریگر</Label>
               <Input
+                data-testid="popup-scroll-pct-input"
                 type="number"
                 min={10}
                 max={90}
@@ -2506,7 +2513,7 @@ export function InspectorPanel() {
                 <SelectTrigger data-testid="nested-tabs-active-select" className="h-8 text-xs">
                   <SelectValue />
                 </SelectTrigger>
-                <SelectContent>
+                <SelectContent className="z-[150]">
                   {rawTabTitles.map((t: string, idx: number) => (
                     <SelectItem key={idx} value={String(idx)}>
                       {t || `تب ${idx + 1}`}
```

"""
with open(target, "a", encoding="utf-8") as f:
    f.write(part)
print("Part 5B appended successfully")
