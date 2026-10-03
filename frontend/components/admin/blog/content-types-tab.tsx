"use client";

/**
 * Custom post types tab (WordPress parity).
 *
 * Editors define new content types (portfolio, testimonial, event…) with a
 * field schema, then create entries under each type. Entries store their
 * values in a flexible JSON object, so no migration is needed per type.
 */

import { useCallback, useEffect, useState } from "react";
import { Plus, Database, RefreshCw, FileText, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import {
  contentTypesApi,
  type CustomPostEntryRevision,
  type CustomPostType,
  type CustomPostEntry,
  type ContentTypeField,
} from "@/lib/api/wp-parity";

export function ContentTypesTab() {
  const { toast } = useToast();
  const [types, setTypes] = useState<CustomPostType[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<CustomPostType | null>(null);
  const [entries, setEntries] = useState<CustomPostEntry[]>([]);
  // Which entry the edit form is bound to. Without it the tab could create
  // an entry but never change one, so a typo in a field could only be fixed
  // by deleting the entry and making another — and there was no revision
  // history to go back to, because nothing could be edited.
  const [editingEntry, setEditingEntry] = useState<CustomPostEntry | null>(null);
  const [entrySched, setEntrySched] = useState("");
  const [revisionsFor, setRevisionsFor] = useState<CustomPostEntry | null>(null);
  const [revisions, setRevisions] = useState<CustomPostEntryRevision[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(false);

  const [typeName, setTypeName] = useState("");
  const [typeIcon, setTypeIcon] = useState("");
  const [fieldSchema, setFieldSchema] = useState<ContentTypeField[]>([]);
  const [fieldLabel, setFieldLabel] = useState("");
  const [fieldType, setFieldType] = useState<ContentTypeField["type"]>("text");
  const [creating, setCreating] = useState(false);

  const [entryTitle, setEntryTitle] = useState("");
  const [entryFields, setEntryFields] = useState<Record<string, string>>({});
  const [creatingEntry, setCreatingEntry] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setTypes(await contentTypesApi.list());
    } catch {
      toast({ title: "خطا در بارگذاری تایپ‌های محتوا", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const loadEntries = useCallback(
    async (type: CustomPostType) => {
      setEntriesLoading(true);
      try {
        setEntries(await contentTypesApi.listEntries(type.id));
      } catch {
        toast({ title: "خطا در بارگذاری ورودی‌ها", variant: "destructive" });
      } finally {
        setEntriesLoading(false);
      }
    },
    [toast],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const addField = () => {
    if (!fieldLabel.trim()) return;
    const key = fieldLabel.trim().toLowerCase().replace(/\s+/g, "_");
    setFieldSchema((prev) => [...prev, { key, label: fieldLabel.trim(), type: fieldType }]);
    setFieldLabel("");
    setFieldType("text");
  };

  const handleCreateType = async () => {
    if (!typeName.trim()) return;
    setCreating(true);
    try {
      await contentTypesApi.create({
        name: typeName.trim(),
        icon: typeIcon.trim() || undefined,
        field_schema: fieldSchema.length ? fieldSchema : undefined,
      });
      toast({ title: "تایپ محتوا ساخته شد" });
      setTypeName("");
      setTypeIcon("");
      setFieldSchema([]);
      await load();
    } catch {
      toast({ title: "ساخت تایپ محتوا ناموفق بود", variant: "destructive" });
    } finally {
      setCreating(false);
    }
  };

  /** ISO instant -> the "YYYY-MM-DDTHH:mm" a datetime-local input expects.
 *
 *  `toISOString()` is UTC and would shift the operator's chosen wall-clock time
 *  by their offset, so picking 09:00 stores 05:30 and the entry goes live at
 *  the wrong hour. The value is read back in the browser's own zone, so the
 *  round trip lands on what was typed.
 */
const toLocalInput = (iso?: string | null): string => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

/** Put an entry into the edit form. Clears whatever the create form held, so
   *  switching between create and edit does not show the previous row's values
   *  under a heading that says "new entry". */
  const startEditing = (entry: CustomPostEntry) => {
    setEditingEntry(entry);
    setEntryTitle(entry.title);
    setEntryFields(
      Object.fromEntries(
        Object.entries(entry.fields ?? {}).map(([k, v]) => [k, String(v)]),
      ),
    );
    // The row's own schedule, not a blank. The save only sends the field when
    // it is non-empty, so starting from "" would drop a schedule the operator
    // opened the form to change the title of.
    setEntrySched(toLocalInput(entry.scheduled_publish_at));
  };

  const cancelEditing = () => {
    setEditingEntry(null);
    setEntryTitle("");
    setEntryFields({});
    setEntrySched("");
  };

  const handleUpdateEntry = async () => {
    if (!selected || !editingEntry || !entryTitle.trim()) return;
    setCreatingEntry(true);
    try {
      await contentTypesApi.updateEntry(selected.id, editingEntry.id, {
        title: entryTitle.trim(),
        fields: entryFields,
        // Sent even when empty: an emptied field means "unschedule", and
        // omitting the key would leave the old time in place with no way to
        // clear it from the form.
        scheduled_publish_at: entrySched
          ? new Date(entrySched).toISOString()
          : null,
      });
      toast({ title: "ورودی به‌روزرسانی شد" });
      cancelEditing();
      await loadEntries(selected);
    } catch {
      toast({ title: "به‌روزرسانی ناموفق بود", variant: "destructive" });
    } finally {
      setCreatingEntry(false);
    }
  };

  /** Load an entry's revisions into the panel under the list. */
  const toggleRevisions = async (entry: CustomPostEntry) => {
    if (revisionsFor?.id === entry.id) {
      setRevisionsFor(null);
      setRevisions([]);
      return;
    }
    setRevisionsFor(entry);
    setRevisions([]);
    try {
      setRevisions(await contentTypesApi.entryRevisions(entry.id));
    } catch {
      toast({ title: "تاریخچه بارگذاری نشد", variant: "destructive" });
    }
  };

  const handleRestoreRevision = async (revisionNumber: number) => {
    if (!selected || !revisionsFor) return;
    try {
      await contentTypesApi.restoreEntryRevision(revisionsFor.id, revisionNumber);
      toast({ title: `نسخهٔ ${revisionNumber} بازگردانده شد` });
      setRevisionsFor(null);
      setRevisions([]);
      await loadEntries(selected);
    } catch {
      toast({ title: "بازگردانی ناموفق بود", variant: "destructive" });
    }
  };

  const handleCreateEntry = async () => {
    if (!selected || !entryTitle.trim()) return;
    setCreatingEntry(true);
    try {
      await contentTypesApi.createEntry(selected.id, {
        title: entryTitle.trim(),
        fields: entryFields,
      });
      toast({ title: "ورودی ساخته شد" });
      setEntryTitle("");
      setEntryFields({});
      await loadEntries(selected);
    } catch {
      toast({ title: "ساخت ورودی ناموفق بود", variant: "destructive" });
    } finally {
      setCreatingEntry(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {/* Type list + create form */}
      <Card className="p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <Database className="h-4 w-4" /> تایپ‌های محتوای سفارشی
          </h3>
          <Button variant="ghost" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>

        <div className="space-y-3 rounded-lg border border-border p-3">
          <div className="space-y-1.5">
            <Label htmlFor="ct-name" className="text-xs">
              نام تایپ
            </Label>
            <Input
              id="ct-name"
              value={typeName}
              onChange={(e) => setTypeName(e.target.value)}
              placeholder="مثلاً: نمونه‌کار، نظر مشتری، رویداد"
              className="text-xs"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">فیلدهای سفارشی</Label>
            {fieldSchema.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {fieldSchema.map((f, i) => (
                  <Badge key={i} variant="secondary" className="gap-1 text-[10px]">
                    {f.label}
                    <span className="text-muted-foreground">({f.type})</span>
                  </Badge>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <Input
                value={fieldLabel}
                onChange={(e) => setFieldLabel(e.target.value)}
                placeholder="نام فیلد"
                className="text-xs"
              />
              <select
                value={fieldType}
                onChange={(e) => setFieldType(e.target.value as ContentTypeField["type"])}
                className="h-9 rounded-md border border-input bg-background px-2 text-xs"
              >
                <option value="text">متن</option>
                <option value="rich">متن غنی</option>
                <option value="number">عدد</option>
                <option value="image">تصویر</option>
                <option value="boolean">بله/خیر</option>
                <option value="date">تاریخ</option>
              </select>
              <Button size="sm" variant="outline" onClick={addField} disabled={!fieldLabel.trim()}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <Button
            size="sm"
            className="w-full"
            onClick={() => void handleCreateType()}
            disabled={creating || !typeName.trim()}
          >
            {creating ? "در حال ساخت…" : "ساخت تایپ محتوا"}
          </Button>
        </div>

        {loading ? (
          <p className="py-6 text-center text-xs text-muted-foreground">در حال بارگذاری…</p>
        ) : types.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            هنوز تایپ محتوای سفارشی وجود ندارد.
          </p>
        ) : (
          <div className="space-y-2">
            {types.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  setSelected(t);
                  void loadEntries(t);
                }}
                className={`flex w-full items-center justify-between rounded-lg border p-3 text-start transition-colors ${
                  selected?.id === t.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-muted/50"
                }`}
              >
                <div>
                  <div className="text-xs font-medium">{t.name}</div>
                  <div className="text-[11px] text-muted-foreground" dir="ltr">
                    /{t.slug}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {t.field_schema && t.field_schema.length > 0 && (
                    <Badge variant="outline" className="text-[10px]">
                      {t.field_schema.length} فیلد
                    </Badge>
                  )}
                  <ChevronRight className="h-4 w-4 text-muted-foreground rtl:rotate-180" />
                </div>
              </button>
            ))}
          </div>
        )}
      </Card>

      {/* Entries of the selected type */}
      <Card className="p-4 space-y-4">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <FileText className="h-4 w-4" />
          {selected ? `ورودی‌های «${selected.name}»` : "ورودی‌ها"}
        </h3>

        {!selected ? (
          <p className="py-8 text-center text-xs text-muted-foreground">
            یک تایپ محتوا را از فهرست کنار انتخاب کنید.
          </p>
        ) : (
          <>
            <div className="space-y-2 rounded-lg border border-border p-3">
              <Input
                value={entryTitle}
                onChange={(e) => setEntryTitle(e.target.value)}
                placeholder="عنوان ورودی"
                className="text-xs"
              />
              {(selected.field_schema ?? []).map((field) => (
                <div key={field.key} className="space-y-1">
                  <Label className="text-[11px]">{field.label}</Label>
                  {field.type === "rich" ? (
                    <Textarea
                      value={entryFields[field.key] ?? ""}
                      onChange={(e) =>
                        setEntryFields((prev) => ({ ...prev, [field.key]: e.target.value }))
                      }
                      rows={3}
                      className="text-xs"
                    />
                  ) : field.type === "boolean" ? (
                    <input
                      type="checkbox"
                      checked={entryFields[field.key] === "true"}
                      onChange={(e) =>
                        setEntryFields((prev) => ({
                          ...prev,
                          [field.key]: String(e.target.checked),
                        }))
                      }
                      className="h-4 w-4"
                    />
                  ) : (
                    <Input
                      type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
                      value={entryFields[field.key] ?? ""}
                      onChange={(e) =>
                        setEntryFields((prev) => ({ ...prev, [field.key]: e.target.value }))
                      }
                      className="text-xs"
                    />
                  )}
                </div>
              ))}
              {/* Schedule only when editing. A schedule on an entry that does
                  not exist yet has nothing to publish, and offering the field
                  during create invites a date that is silently dropped. */}
              {editingEntry && (
                <div className="space-y-1.5">
                  <Label htmlFor="ct-sched" className="text-xs">
                    انتشار زمان‌بندی‌شده (اختیاری)
                  </Label>
                  <Input
                    id="ct-sched"
                    type="datetime-local"
                    value={entrySched}
                    onChange={(e) => setEntrySched(e.target.value)}
                    className="text-xs"
                    dir="ltr"
                  />
                </div>
              )}
              {editingEntry ? (
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    className="flex-1"
                    onClick={() => void handleUpdateEntry()}
                    disabled={creatingEntry || !entryTitle.trim()}
                  >
                    ذخیرهٔ تغییرات
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={cancelEditing}
                    disabled={creatingEntry}
                  >
                    انصراف
                  </Button>
                </div>
              ) : (
                <Button
                  size="sm"
                  className="w-full"
                  onClick={() => void handleCreateEntry()}
                  disabled={creatingEntry || !entryTitle.trim()}
                >
                  <Plus className="h-4 w-4" /> افزودن ورودی
                </Button>
              )}
            </div>

            {entriesLoading ? (
              <p className="py-6 text-center text-xs text-muted-foreground">در حال بارگذاری…</p>
            ) : entries.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted-foreground">
                این تایپ هنوز ورودی ندارد.
              </p>
            ) : (
              <div className="space-y-2">
                {entries.map((e) => (
                  <div key={e.id} className="rounded-lg border border-border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-medium">{e.title}</span>
                      <div className="flex items-center gap-1.5">
                        <Badge variant="outline" className="text-[10px]">
                          {e.status}
                        </Badge>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 px-2 text-[10px]"
                          onClick={() =>
                            editingEntry?.id === e.id
                              ? cancelEditing()
                              : startEditing(e)
                          }
                        >
                          {editingEntry?.id === e.id ? "انصراف" : "ویرایش"}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 px-2 text-[10px]"
                          onClick={() => void toggleRevisions(e)}
                        >
                          {revisionsFor?.id === e.id ? "بستن تاریخچه" : "تاریخچه"}
                        </Button>
                      </div>
                    </div>
                    {e.scheduled_publish_at && (
                      <p className="mt-1 text-[10px] text-amber-600">
                        زمان‌بندی انتشار:{" "}
                        {new Date(e.scheduled_publish_at).toLocaleString("fa-IR")}
                      </p>
                    )}
                    {revisionsFor?.id === e.id && (
                      <div className="mt-2 space-y-1 rounded border border-border p-2">
                        {revisions.length === 0 ? (
                          <p className="text-[10px] text-muted-foreground">
                            هنوز نسخه‌ای ثبت نشده — اولین ویرایش، مبنای بعدی را
                            می‌سازد.
                          </p>
                        ) : (
                          revisions.map((r) => (
                            <div
                              key={r.revision_number}
                              className="flex items-center justify-between text-[10px]"
                            >
                              <span>
                                نسخهٔ {r.revision_number}
                                {r.created_at
                                  ? ` — ${new Date(r.created_at).toLocaleString("fa-IR")}`
                                  : ""}
                              </span>
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-5 px-2 text-[10px]"
                                onClick={() =>
                                  void handleRestoreRevision(r.revision_number)
                                }
                              >
                                بازگردانی
                              </Button>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                    {e.fields && Object.keys(e.fields).length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">
                        {Object.entries(e.fields).map(([k, v]) => (
                          <span key={k}>
                            {k}: {String(v).slice(0, 30)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
