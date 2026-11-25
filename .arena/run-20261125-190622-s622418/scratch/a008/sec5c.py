target = ".arena/run-20261125-190622-s622418/r0/a008.md"
part = """#### 5.3 Layer 3: Iframe Canvas Rendering (`frontend/components/admin/builder/canvas-element.tsx`)

```diff
--- a/frontend/components/admin/builder/canvas-element.tsx
+++ b/frontend/components/admin/builder/canvas-element.tsx
@@ -1355,7 +1355,10 @@ function CanvasElementComponent({
         const isRequired = Boolean(props.required);
         const customClass = String(props.customCssClass || element.styles?.customCssClass || "");
         return (
-          <div className={cn("space-y-1 w-full text-right pointer-events-none", customClass)} data-required={isRequired ? "true" : undefined}>
+          <div
+            className={cn("space-y-1 w-full text-right", !previewMode && "pointer-events-none", customClass)}
+            data-required={isRequired ? "true" : undefined}
+          >
             {label && (
               <label className="block text-xs font-semibold text-foreground">
                 {label}
@@ -1380,7 +1383,10 @@ function CanvasElementComponent({
         const isRequired = Boolean(props.required);
         const customClass = String(props.customCssClass || element.styles?.customCssClass || "");
         return (
-          <div className={cn("space-y-1 w-full text-right pointer-events-none", customClass)} data-required={isRequired ? "true" : undefined}>
+          <div
+            className={cn("space-y-1 w-full text-right", !previewMode && "pointer-events-none", customClass)}
+            data-required={isRequired ? "true" : undefined}
+          >
             {label && (
               <label className="block text-xs font-semibold text-foreground">
                 {label}
@@ -1403,7 +1409,10 @@ function CanvasElementComponent({
         const isRequired = Boolean(props.required);
         const customClass = String(props.customCssClass || element.styles?.customCssClass || "");
         return (
-          <div className={cn("space-y-1 w-full text-right pointer-events-none", customClass)} data-required={isRequired ? "true" : undefined}>
+          <div
+            className={cn("space-y-1 w-full text-right", !previewMode && "pointer-events-none", customClass)}
+            data-required={isRequired ? "true" : undefined}
+          >
             {label && (
               <label className="block text-xs font-semibold text-foreground">
                 {label}
@@ -1422,9 +1431,10 @@ function CanvasElementComponent({
         const label = String(props.label || "شرایط و قوانین را می‌پذیرم");
         const name = String(props.name || "terms");
         return (
-          <div className="flex items-center gap-2 text-right">
+          <div className={cn("flex items-center gap-2 text-right", !previewMode && "pointer-events-none")}>
             <input
               type="checkbox"
+              readOnly
               id={`chk_${element.id}`}
               name={name}
               defaultChecked={Boolean(props.checked)}
@@ -1443,12 +1453,13 @@ function CanvasElementComponent({
         const options = (props.options as string[]) || ["گزینه ۱", "گزینه ۲"];
         const name = String(props.name || "radio_group");
         return (
-          <div className="space-y-1.5 text-right w-full">
+          <div className={cn("space-y-1.5 text-right w-full", !previewMode && "pointer-events-none")}>
             <span className="block text-xs font-bold text-foreground">{label}</span>
             <div className="flex flex-col gap-1.5">
               {options.map((opt, i) => (
                 <label key={i} className="flex items-center gap-2 text-xs text-foreground cursor-pointer select-none">
                   <input
+                    readOnly
                     type="radio"
                     name={name}
                     defaultChecked={i === 0}
```

#### 5.4 Layer 4: SSR AST Compiler (`backend/app/modules/content/application/ast_compiler.py`)

```diff
--- a/backend/app/modules/content/application/ast_compiler.py
+++ b/backend/app/modules/content/application/ast_compiler.py
@@ -348,6 +348,7 @@ class ASTCompiler:
             if props.get("error_message"):
                 extra_attrs += f' data-error-message="{html.escape(str(props["error_message"]))}"'
+            if props.get("form_name"):
+                extra_attrs += f' data-form-name="{html.escape(str(props["form_name"]))}"'
             # Include anti-spam honeypot hidden field inside form
             hp_field = '<input type="text" name="_hp_website" style="display:none !important;" tabindex="-1" autocomplete="off" aria-hidden="true" />'
             children_html = overlay_html + shape_dividers_html + hp_field + "".join(
@@ -480,7 +481,7 @@ class ASTCompiler:
             return (
                 f'<div{id_attr} class="builder-form-group space-y-1 w-full {css_class}"{style_attr}>'
                 f'{label_html}<input type="{input_type}" name="{name}" placeholder="{placeholder}"{required} '
-                f'class="w-full rounded-xl border border-input bg-background px-4 py-2.5 text-sm transition focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary" /></div>'
+                f'class="w-full rounded-xl border border-input bg-background px-4 py-2.5 text-sm transition focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary" /></div>'
             )
 
         elif widget_type == "form_textarea":
```

---
"""
with open(target, "a", encoding="utf-8") as f:
    f.write(part)
print("Part 5C appended successfully")
