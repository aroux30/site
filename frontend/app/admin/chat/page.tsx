"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Bot,
  ChevronDown,
  ChevronUp,
  ClipboardList,
  Clock,
  FileText,
  Globe,
  Headset,
  Loader2,
  Mail,
  MessageCircle,
  MessagesSquare,
  Mic,
  Monitor,
  Paperclip,
  Phone,
  RefreshCw,
  Send,
  Settings,
  Smile,
  Trash2,
  User,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn, toPersianDigits } from "@/lib/utils";
import { useAdminQuery } from "@/lib/api/admin-query";
import { useConfirm } from "@/components/ui/confirm-dialog";
import { EmojiPicker } from "@/components/chat/emoji-picker";
import {
  fetchChatConversations,
  fetchChatAdminHistory,
  pollChatAdmin,
  sendChatAdminMessage,
  fetchChatSessionInfo,
  deleteChatSession,
  toggleChatHandoff,
  fetchChatOnlineUsers,
  fetchChatAdminConfig,
  updateChatAdminConfig,
  uploadChatFile,
  type ChatConversation,
  type ChatMessage,
  type ChatOnlineUser,
} from "@/lib/api/chat";
import { ChatSettingsPanel } from "@/components/chat/chat-settings-panel";
import { ChatMessageContent } from "@/components/chat/chat-message-content";

/**
 * میز کار گفتگوی زنده — the WordPress plugin's live console, ported.
 *
 * Left: conversation list (online first, unread badges). Right: the thread, a
 * composer, per-session pre-chat info, a hand-off toggle, and delete. A second
 * tab lists live online visitors. Polls every 5s (list) / 4s (active thread),
 * paused when the tab is hidden.
 */

type Tab = "chat" | "online" | "settings";

// N2: Web Audio two-tone beep for the console (plugin admin-chat.js playBeep).
// Guards against multi-tab beep storms with a 3s localStorage window, like the
// widget (chat_last_beep) but under its own key.
let adminAudioCtx: AudioContext | null = null;
function playAdminBeep() {
  try {
    const last = parseInt(localStorage.getItem("chat_admin_last_beep") || "0", 10);
    if (Date.now() - last < 3000) return;
    localStorage.setItem("chat_admin_last_beep", String(Date.now()));
    if (!adminAudioCtx) {
      const Ctx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctx) return;
      adminAudioCtx = new Ctx();
    }
    const ctx = adminAudioCtx;
    const now = ctx.currentTime;
    const tones: [number, number][] = [
      [880, 0],
      [1320, 0.12],
    ];
    tones.forEach(([freq, delay]) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.3, now + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, now + delay + 0.15);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now + delay);
      osc.stop(now + delay + 0.15);
    });
  } catch {
    /* audio unavailable */
  }
}

function AdminChatPageInner() {
  const [tab, setTab] = useState<Tab>("chat");
  const [active, setActive] = useState<ChatConversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [info, setInfo] = useState<{ label: string; value: string }[]>([]);
  const [showInfo, setShowInfo] = useState(false);
  const [handoffUntil, setHandoffUntil] = useState(0);
  const [handoffBusy, setHandoffBusy] = useState(false);
  const [tick, setTick] = useState(0);
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const lastIdRef = useRef(0);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const confirm = useConfirm();
  const searchParams = useSearchParams();
  // N9: role avatar URLs for the thread (plugin admin-chat.js reads these from
  // n8nAdminChat). Loaded once from the admin config.
  const [avatars, setAvatars] = useState({ user: "", ai: "", admin: "" });
  // G10: ?session=<key> deep-links straight into that conversation (the online
  // cards' "ارسال پیام" button links here).
  const deepLinkSession = searchParams.get("session");

  const {
    data: conversations = [],
    loading: listLoading,
    reload: reloadList,
  } = useAdminQuery<ChatConversation[]>({
    queryKey: ["admin", "chat", "conversations"],
    queryFn: fetchChatConversations,
    fallbackError: "خطا در بارگذاری گفتگوها",
    options: { refetchInterval: 5000, refetchIntervalInBackground: false },
  });

  const {
    data: online,
    reload: reloadOnline,
  } = useAdminQuery<{ users: ChatOnlineUser[]; show_fields: string[] }>({
    queryKey: ["admin", "chat", "online"],
    queryFn: fetchChatOnlineUsers,
    fallbackError: "خطا در بارگذاری کاربران آنلاین",
    enabled: tab === "online",
    options: { refetchInterval: 5000, refetchIntervalInBackground: false },
  });

  // N9: avatar URLs for the thread bubbles (from the widget config).
  useEffect(() => {
    let cancelled = false;
    void fetchChatAdminConfig()
      .then((cfg) => {
        if (cancelled) return;
        const c = cfg as Record<string, unknown>;
        setAvatars({
          user: String(c.user_avatar_url ?? ""),
          ai: String(c.ai_avatar_url ?? ""),
          admin: String(c.admin_avatar_url ?? ""),
        });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // N2: beep when another session's unread total rises (plugin
  // admin-chat-core.js:84-94) — staff notices a new conversation without
  // watching the list.
  const prevUnreadOtherRef = useRef(-1);
  useEffect(() => {
    let total = 0;
    for (const c of conversations) {
      if (c.session_key !== active?.session_key) total += c.unread_count || 0;
    }
    if (prevUnreadOtherRef.current >= 0 && total > prevUnreadOtherRef.current) {
      playAdminBeep();
    }
    prevUnreadOtherRef.current = total;
  }, [conversations, active]);

  const openConversation = useCallback(async (conv: ChatConversation) => {
    setActive(conv);
    setShowInfo(false);
    setMessages([]);
    lastIdRef.current = 0;
    try {
      const data = await fetchChatAdminHistory(conv.session_key);
      setMessages(data.messages);
      lastIdRef.current = data.messages.reduce((m, x) => Math.max(m, x.id), 0);
      setHandoffUntil(data.handoff_until);
    } catch {
      /* keep empty */
    }
    try {
      const si = await fetchChatSessionInfo(conv.session_key);
      setInfo(si.fields);
    } catch {
      setInfo([]);
    }
  }, []);

  // G10: auto-open the deep-linked session once the list has loaded. If it is
  // not in the list yet (a brand-new visitor), synthesise a row so the console
  // can still open it.
  useEffect(() => {
    if (!deepLinkSession || active) return;
    const found = conversations.find((c) => c.session_key === deepLinkSession);
    if (found) {
      void openConversation(found);
    } else if (conversations.length > 0) {
      void openConversation({
        session_key: deepLinkSession,
        user_name: `کاربر ${deepLinkSession.slice(-4)}`,
        time_ago: "جدید",
        last_message: "",
        unread_count: 0,
        is_online: false,
        last_seen_text: "",
        current_page: "",
      });
    }
  }, [deepLinkSession, conversations, active, openConversation]);

  // Poll the active thread.
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(async () => {
      if (document.hidden) return;
      try {
        const res = await pollChatAdmin(active.session_key, lastIdRef.current);
        if (res.messages.length) {
          setMessages((prev) => {
            const seen = new Set(prev.map((m) => m.id));
            return [...prev, ...res.messages.filter((m) => !seen.has(m.id))];
          });
          lastIdRef.current = Math.max(lastIdRef.current, ...res.messages.map((m) => m.id));
          // N2: beep when a new visitor message lands in the open thread.
          if (res.messages.some((m) => m.role === "user")) playAdminBeep();
        }
        setHandoffUntil(res.handoff_until);
      } catch {
        /* silent */
      }
    }, 4000);
    return () => clearInterval(timer);
  }, [active]);

  useEffect(() => {
    const el = scrollerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (handoffUntil <= 0) return;
    const t = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [handoffUntil]);

  const handoffActive = handoffUntil > Math.floor(Date.now() / 1000);
  const handoffRemaining = (() => {
    void tick;
    if (!handoffActive) return "";
    const diff = handoffUntil - Math.floor(Date.now() / 1000);
    return `${Math.floor(diff / 60)}:${String(diff % 60).padStart(2, "0")}`;
  })();

  // ── Voice recording (G6) ────────────────────────────────────────────
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.start(1000);
      recorderRef.current = recorder;
      setRecording(true);
      setRecordSeconds(0);
      recTimerRef.current = setInterval(() => setRecordSeconds((s) => s + 1), 1000);
    } catch {
      /* mic denied */
    }
  };

  const stopRecording = (send: boolean) => {
    const recorder = recorderRef.current;
    if (recTimerRef.current) clearInterval(recTimerRef.current);
    recTimerRef.current = null;
    setRecording(false);
    if (!recorder) return;
    if (send) {
      recorder.onstop = async () => {
        recorder.stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        if (blob.size > 500) {
          const tmp = tempUpload("🎤 در حال ارسال ویس...");
          try {
            const file = new File([blob], `admin_voice_${Date.now()}.webm`, {
              type: "audio/webm",
            });
            const up = await uploadChatFile(file);
            dropTemp(tmp);
            await sendRaw(`[Voice Message](${up.url})`);
          } catch {
            dropTemp(tmp);
          }
        }
      };
      recorder.stop();
    } else {
      recorder.stream.getTracks().forEach((t) => t.stop());
      recorder.stop();
    }
  };

  // E3: show an optimistic placeholder bubble while an upload/voice note is in
  // flight (plugin admin-chat.js:484 «📎 در حال آپلود...» / «🎤 در حال ارسال ویس...»),
  // then drop it and send the real message once the file has a URL.
  const tempUpload = (label: string): number => {
    const id = -Date.now();
    setMessages((prev) => [
      ...prev,
      { id, role: "admin", message: label, time: "", is_read: false, sender_name: "" },
    ]);
    return id;
  };
  const dropTemp = (id: number) =>
    setMessages((prev) => prev.filter((m) => m.id !== id));

  const sendRaw = async (text: string) => {
    if (!active || !text.trim()) return;
    const body = text.trim();
    setMessages((prev) => [
      ...prev,
      { id: -Date.now(), role: "admin", message: body, time: "الان", is_read: false, sender_name: "" },
    ]);
    try {
      const { id } = await sendChatAdminMessage(active.session_key, body);
      if (id > lastIdRef.current) lastIdRef.current = id;
    } catch {
      /* ignore */
    }
  };

  const send = async () => {
    if (!active || !input.trim()) return;
    const text = input.trim();
    setInput("");
    setSending(true);
    await sendRaw(text);
    setSending(false);
  };

  const onDelete = async () => {
    if (!active) return;
    const ok = await confirm({
      title: "حذف گفتگو",
      description: "تمام پیام‌های این گفتگو برای کاربر هم حذف خواهد شد.",
      confirmLabel: "حذف",
      destructive: true,
    });
    if (!ok) return;
    await deleteChatSession(active.session_key);
    setActive(null);
    setMessages([]);
    void reloadList();
  };

  const onToggleHandoff = async () => {
    if (!active || handoffBusy) return;
    // E1: show a pending state + guard the double-click race (plugin
    // admin-chat.js:218 shows «در حال انجام...» while the request is in flight).
    setHandoffBusy(true);
    try {
      const next = handoffActive ? 0 : 1;
      const res = await toggleChatHandoff(active.session_key, next);
      setHandoffUntil(res.handoff_until);
    } finally {
      setHandoffBusy(false);
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
          <MessagesSquare className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">گفتگوی زنده</h1>
          <p className="text-xs text-muted-foreground sm:text-sm">
            مشاهده و پاسخ‌گویی به گفتگوهای زندهٔ مشتریان
          </p>
        </div>
      </div>

      {/* Tabs — AD1: plugin php:993-999 shape (rounded-2xl pills, hover lift),
          OPTION 2: project palette — active = primary, inactive = muted. */}
      <div className="mt-5 mb-5 flex gap-3 border-b px-2 pb-4">
        {(
          [
            { t: "chat" as Tab, label: "لایو چت", Icon: MessageCircle },
            { t: "online" as Tab, label: "کاربران آنلاین", Icon: Users },
            { t: "settings" as Tab, label: "تنظیمات", Icon: Settings },
          ] as const
        ).map(({ t, label, Icon }) => {
          const on = tab === t;
          return (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={cn(
                "relative flex items-center gap-2 rounded-2xl px-6 py-2.5 text-sm font-bold transition-all duration-300 hover:-translate-y-0.5",
                on
                  ? "bg-primary text-primary-foreground shadow-lg"
                  : "bg-muted text-muted-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
              {t === "online" && online && (
                <span className="me-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-extrabold text-primary shadow-sm">
                  {toPersianDigits(online.users.length)}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {tab === "chat" ? (
        <div
          className="flex flex-col overflow-hidden rounded-lg border bg-card shadow-xl md:flex-row"
          style={{ height: "calc(100vh - 160px)", maxHeight: "800px" }}
        >
          {/* Conversation list — AD3: plugin php:1006 — w-80 sidebar. */}
          <div className="flex w-full shrink-0 flex-col border-e bg-muted/40 md:w-80">
            <div className="flex h-12 shrink-0 items-center justify-between border-b bg-card p-3 text-sm font-bold md:h-14">
              <span>کاربران فعال</span>
              <button
                onClick={() => void reloadList()}
                className="flex items-center gap-1 rounded bg-muted px-2 py-1 text-xs"
              >
                <RefreshCw className="h-3 w-3" /> بروزرسانی
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              {listLoading && conversations.length === 0 ? (
                <div className="flex justify-center p-6">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : conversations.length === 0 ? (
                <p className="p-4 text-center text-xs text-muted-foreground">
                  هنوز گفتگویی ثبت نشده است
                </p>
              ) : (
                conversations.map((c) => (
                  <button
                    key={c.session_key}
                    type="button"
                    onClick={() => void openConversation(c)}
                    className={cn(
                      // AD3: plugin admin-chat.js:101 — active row carries a 4px
                      // indicator bar; unread rows carry a red tint + 4px red
                      // border (admin-chat.js:103 `#fef2f2` + `border-left:4px
                      // solid #ef4444`). These are semantic state markers, not
                      // palette — the row background/indicator keep the plugin's
                      // meaning while the active tint uses the project token.
                      "block w-full border-b p-3 text-right transition-colors hover:bg-muted/50",
                      active?.session_key === c.session_key &&
                        "border-s-4 border-primary bg-primary/5",
                      c.unread_count > 0 &&
                        active?.session_key !== c.session_key &&
                        "border-e-4 border-red-500 bg-red-50 dark:bg-red-950/20",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="truncate text-sm font-bold">{c.user_name}</span>
                      {/* AD3: plugin admin-chat.js:110-114 — the unread badge sits
                          in the top row immediately before the time chip. */}
                      <div className="flex shrink-0 items-center gap-1.5">
                        {c.unread_count > 0 && (
                          <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[11px] font-bold text-white">
                            {toPersianDigits(c.unread_count)}
                          </span>
                        )}
                        <span className="text-[10px] text-muted-foreground">{c.time_ago}</span>
                      </div>
                    </div>
                    {c.is_online ? (
                      <div className="mt-1 flex items-center gap-1 text-[11px] font-bold text-green-600">
                        <span className="inline-block h-2 w-2 rounded-full bg-green-500" /> آنلاین
                        {c.current_page ? ` — ${c.current_page}` : ""}
                      </div>
                    ) : (
                      c.last_seen_text && (
                        <div className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground">
                          <Clock className="h-3 w-3" /> {c.last_seen_text}
                        </div>
                      )
                    )}
                    <div className="mt-1 flex items-center justify-between gap-2">
                      <span className="truncate text-xs text-muted-foreground" dir="auto">
                        {c.last_message}
                      </span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Thread — AD2 shape; OPTION 2: subtle project bg (muted), not the
              foreign beige. */}
          <div className="relative flex min-h-[40vh] flex-1 flex-col bg-muted/30 md:h-full">
            {!active ? (
              <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
                یک گفتگو را انتخاب کنید
              </div>
            ) : (
              <>
                {/* Thread header — AD4: plugin php:1015-1023 shape. */}
                <div
                  className="z-10 flex shrink-0 items-center justify-between border-b bg-card p-3 shadow-sm"
                  style={{ minHeight: "56px" }}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold">{active.user_name}</span>
                    <button
                      type="button"
                      disabled={handoffBusy}
                      onClick={() => void onToggleHandoff()}
                      className={cn(
                        "flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-bold shadow-sm transition-all",
                        handoffActive ? "bg-primary text-primary-foreground" : "bg-card",
                      )}
                    >
                      {handoffBusy ? (
                        <>
                          <Loader2 className="h-3 w-3 animate-spin" /> در حال انجام...
                        </>
                      ) : handoffActive ? (
                        <>
                          <Headset className="h-3 w-3" />
                          {`پشتیبانی دستی (${handoffRemaining})`}
                        </>
                      ) : (
                        <>
                          <Bot className="h-3 w-3" /> انتقال به انسان
                        </>
                      )}
                    </button>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setShowInfo((s) => !s)}
                      className="flex items-center gap-1 rounded-lg border border-primary/20 bg-primary/5 px-3 py-1.5 text-xs font-bold text-primary transition hover:bg-primary/10"
                    >
                      <User className="h-3 w-3" /> اطلاعات کاربر
                    </button>
                    <button
                      type="button"
                      onClick={() => void onDelete()}
                      className="flex items-center gap-1 rounded-lg bg-destructive px-3 py-1 text-xs text-destructive-foreground transition hover:bg-destructive/90"
                    >
                      <Trash2 className="h-3 w-3" /> حذف
                    </button>
                  </div>
                </div>

                {/* Session info panel — AD5: plugin php:1026-1031 shape
                    (full-width slide-down, responsive grid). */}
                {showInfo && (
                  <div className="shrink-0 border-b bg-muted/40 px-4 py-3 shadow-inner" dir="rtl">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="flex items-center gap-1 text-xs font-bold text-primary">
                        <ClipboardList className="h-3 w-3" /> اطلاعات فرم پیش از چت
                      </span>
                      <button
                        type="button"
                        onClick={() => setShowInfo(false)}
                        className="text-lg leading-none text-muted-foreground hover:text-foreground"
                      >
                        ×
                      </button>
                    </div>
                    <div className="mt-3 grid grid-cols-1 gap-3 text-xs text-muted-foreground md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                      {info.length === 0 ? (
                        <span className="text-xs">اطلاعاتی ثبت نشده</span>
                      ) : (
                        info.map((f, i) => (
                          <div key={i} className="rounded border bg-card px-2 py-1">
                            <div className="text-[10px] text-muted-foreground">{f.label}</div>
                            <div className="truncate text-xs font-medium" dir="auto">
                              {f.value}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}

                {/* Messages — AD2: plugin php:1034 — p-4 space-y-3. */}
                <div ref={scrollerRef} className="flex flex-1 flex-col space-y-3 overflow-y-auto p-4">
                  {messages.map((m) => (
                    <AdminBubble key={m.id} message={m} avatars={avatars} />
                  ))}
                </div>

                {/* Composer — AD6: plugin php:1051-1066 shape (p-2 border-t
                    min-h 50px); OPTION 2: project tokens. When recording, the
                    plugin HIDES the composer and shows a dedicated voice bar
                    (php:1037-1047 `#n8n-voice-ui`, admin-chat.js:400-401). */}
                <div
                  className={cn(
                    "relative z-10 shrink-0 items-center gap-2 border-t bg-card p-2",
                    recording ? "hidden" : "flex",
                  )}
                  style={{ minHeight: "50px" }}
                >
                  <input
                    ref={fileRef}
                    type="file"
                    className="hidden"
                    onChange={async (e) => {
                      const f = e.target.files?.[0];
                      e.target.value = "";
                      if (!f || !active) return;
                      const tmp = tempUpload("📎 در حال آپلود...");
                      try {
                        const up = await uploadChatFile(f);
                        dropTemp(tmp);
                        await sendRaw(`[Attachment: ${up.name}](${up.url})`);
                      } catch {
                        dropTemp(tmp);
                      }
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => fileRef.current?.click()}
                    className="rounded-full p-1.5 text-muted-foreground transition hover:bg-muted"
                    aria-label="پیوست"
                    title="پیوست فایل"
                  >
                    <Paperclip className="h-[18px] w-[18px]" />
                  </button>
                  {/* G6: staff voice notes */}
                  <button
                    type="button"
                    onClick={() => (recording ? stopRecording(true) : void startRecording())}
                    className={cn(
                      "rounded-full p-1.5 transition hover:bg-muted",
                      recording ? "text-destructive" : "text-muted-foreground",
                    )}
                    aria-label="ضبط صدا"
                    title="ضبط صدا"
                  >
                    <Mic className="h-[18px] w-[18px]" />
                  </button>
                  <div className="relative flex shrink-0 items-center">
                    <button
                      type="button"
                      onClick={() => setEmojiOpen((o) => !o)}
                      className="flex items-center justify-center rounded-full p-1.5 text-muted-foreground outline-none transition hover:bg-muted"
                      aria-label="ایموجی"
                      title="ایموجی"
                    >
                      <Smile className="h-5 w-5" />
                    </button>
                    <EmojiPicker
                      open={emojiOpen}
                      onClose={() => setEmojiOpen(false)}
                      onPick={(em) => {
                        setInput((v) => v + em);
                        setEmojiOpen(false);
                      }}
                    />
                  </div>
                  <textarea
                    rows={1}
                    value={recording ? `در حال ضبط... ${recordSeconds}s` : input}
                    onChange={(e) => {
                      setInput(e.target.value);
                      // Auto-resize — plugin admin-chat.js:363-367
                      // (min 34px, cap 80px).
                      const el = e.currentTarget;
                      el.style.height = "auto";
                      el.style.height = `${Math.min(Math.max(el.scrollHeight, 34), 80)}px`;
                    }}
                    disabled={recording}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        void send();
                      }
                    }}
                    placeholder="پیام..."
                    className="flex-1 resize-none rounded-xl border p-2 text-sm transition focus:outline-none"
                    style={{ height: "34px", minHeight: "34px", maxHeight: "80px", lineHeight: 1.3 }}
                  />
                  <button
                    type="button"
                    disabled={sending}
                    onClick={() => void send()}
                    aria-label="ارسال"
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary p-1.5 text-primary-foreground shadow-md transition hover:bg-primary/90"
                  >
                    {sending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </button>
                </div>

                {/* Voice bar — plugin php:1037-1047 (`#n8n-voice-ui`): red pulsing
                    timer + «لغو» + «ارسال»; shown only while recording, in place
                    of the composer (admin-chat.js:400-401 / 421-422). */}
                {recording && (
                  <div className="relative z-10 flex shrink-0 items-center justify-between border-t bg-card p-2 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)]">
                    <div className="flex items-center gap-2 font-bold text-destructive">
                      <Mic className="h-4 w-4 animate-pulse" />
                      <span className="text-sm">
                        {String(Math.floor(recordSeconds / 60)).padStart(2, "0")}:
                        {String(recordSeconds % 60).padStart(2, "0")}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => stopRecording(false)}
                        className="rounded px-3 py-1 text-xs text-muted-foreground transition hover:bg-muted"
                      >
                        لغو
                      </button>
                      <button
                        type="button"
                        onClick={() => stopRecording(true)}
                        className="flex items-center gap-1 rounded-lg bg-destructive px-3 py-1 text-xs font-bold text-destructive-foreground transition hover:bg-destructive/90"
                      >
                        ارسال
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      ) : tab === "online" ? (
        // AD: plugin php:1073-1082 — white card (border gray-300, radius-lg,
        // shadow-sm, p-6, min-h 500px) with a title + refresh button.
        <div className="min-h-[500px] rounded-lg border bg-card p-6 shadow-sm">
          <div className="mb-6 flex items-center justify-between">
            <h2 className="text-xl font-bold">مانیتورینگ کاربران آنلاین</h2>
            <button
              onClick={() => void reloadOnline()}
              className="flex items-center gap-1.5 rounded-lg bg-muted px-3 py-2 text-xs font-bold text-muted-foreground transition hover:bg-muted/70"
            >
              <RefreshCw className="h-3.5 w-3.5" /> بروزرسانی
            </button>
          </div>
          <OnlineUsersGrid users={online?.users || []} showFields={online?.show_fields || []} />
        </div>
      ) : (
        <ChatSettingsPanel
          load={fetchChatAdminConfig}
          save={updateChatAdminConfig}
        />
      )}
    </div>
  );
}

function AdminBubble({
  message,
  avatars,
}: {
  message: ChatMessage;
  avatars?: { user: string; ai: string; admin: string };
}) {
  const isUser = message.role === "user";
  const isAI = message.role === "ai";
  const isAdminOrAI = !isUser;
  // N9/AD: per-role avatar (admin-chat.js:305-320) — 38px, role-tinted bg.
  const avatarUrl = isUser ? avatars?.user : isAI ? avatars?.ai : avatars?.admin;
  const emoji = isUser ? "👤" : isAI ? "🤖" : "👨‍💼";
  const avatarBg = isUser ? "#dbeafe" : isAI ? "#d1fae5" : "#ffedd5";
  // Bubble bg per role (admin-chat.js:292-296); OPTION 2 project palette.
  const bubbleStyle: React.CSSProperties = isUser
    ? { background: "hsl(var(--card))", color: "hsl(var(--foreground))", border: "1px solid hsl(var(--border))" }
    : isAI
      ? { background: "hsl(142 70% 92%)", color: "hsl(150 30% 15%)" }
      : { background: "hsl(var(--primary) / 0.12)", color: "hsl(var(--foreground))" };
  // Tail: one flat corner (admin-chat.js:293-296). Border-radius shorthand is
  // "TL TR BR BL". Plugin: user → `rounded-bl-none` (flat bottom-LEFT); admin/ai
  // → `rounded-br-none` (flat bottom-RIGHT). The bubble row is `dir=ltr`
  // ([avatar][bubble] for user, [bubble][avatar] for admin), so the flat corner
  // always points at the avatar.
  const bubbleRadius = isUser ? "12px 12px 12px 0" : "12px 12px 0 12px";
  const tick =
    message.role === "admin" ? (
      <span style={{ fontSize: "10px", color: "hsl(var(--primary))" }}>
        {message.is_read ? " ✓✓" : " ✓"}
      </span>
    ) : null;
  // Sender name: red, underlined (admin-chat.js:328-335).
  let senderInfo: React.ReactNode = null;
  if (message.role === "admin" && message.sender_name) {
    const parts = message.sender_name.split("|");
    const aName = parts[1] || parts[0];
    if (aName) {
      senderInfo = (
        <>
          {" | "}
          <span
            style={{
              fontWeight: "bold",
              color: "hsl(var(--destructive))",
              borderBottom: "1px solid hsl(var(--destructive))",
              paddingBottom: "1px",
            }}
          >
            {aName}
          </span>
        </>
      );
    }
  }
  const avatarEl = avatarUrl ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={avatarUrl}
      alt=""
      style={{ width: "38px", height: "38px", borderRadius: "50%", objectFit: "cover", flexShrink: 0 }}
    />
  ) : (
    <div
      style={{
        width: "38px",
        height: "38px",
        borderRadius: "50%",
        background: avatarBg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "17px",
        flexShrink: 0,
      }}
    >
      {emoji}
    </div>
  );
  const bubble = (
    <div
      className="px-3 py-2 text-sm leading-relaxed shadow-sm"
      style={{ minWidth: "60px", maxWidth: "100%", wordWrap: "break-word", direction: "rtl", textAlign: "right", borderRadius: bubbleRadius, ...bubbleStyle }}
    >
      <ChatMessageContent text={message.message} previewImages />
    </div>
  );
  return (
    // AD: plugin admin-chat.js:342-352 — inner flex row avatar+bubble, timestamp
    // BELOW with 46px padding on the avatar side; outer wrapper pushed to the
    // right (admin/ai) or left (user).
    <div
      dir="ltr"
      style={{
        display: "flex",
        flexDirection: "column",
        maxWidth: "80%",
        marginBottom: "10px",
        marginLeft: isAdminOrAI ? "auto" : undefined,
        marginRight: isUser ? "auto" : undefined,
        alignItems: isAdminOrAI ? "flex-end" : "flex-start",
      }}
    >
      <div dir="ltr" style={{ display: "flex", flexDirection: "row", alignItems: "flex-end", gap: "8px" }}>
        {isAdminOrAI ? (
          <>
            {bubble}
            {avatarEl}
          </>
        ) : (
          <>
            {avatarEl}
            {bubble}
          </>
        )}
      </div>
      <div
        style={{
          fontSize: "10px",
          color: "#9ca3af",
          marginTop: "2px",
          paddingRight: isAdminOrAI ? "46px" : undefined,
          paddingLeft: isUser ? "46px" : undefined,
        }}
      >
        {message.time} {tick}
        {senderInfo}
      </div>
    </div>
  );
}

export default function AdminChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <AdminChatPageInner />
    </Suspense>
  );
}

// N4: parse a UA string into device / browser / OS labels — plugin parity
// (admin-online.js parseUA L5-23).
function parseUA(ua: string): { device: string; browser: string; os: string } {
  const s = ua || "";
  let os = "نامشخص";
  if (/windows/i.test(s)) os = "Windows";
  else if (/android/i.test(s)) os = "Android";
  else if (/iphone|ipad|ipod/i.test(s)) os = "iOS";
  else if (/mac os|macintosh/i.test(s)) os = "macOS";
  else if (/linux/i.test(s)) os = "Linux";

  let browser = "نامشخص";
  if (/edg\//i.test(s)) browser = "Edge";
  else if (/opr\/|opera/i.test(s)) browser = "Opera";
  else if (/samsungbrowser/i.test(s)) browser = "Samsung";
  else if (/firefox\//i.test(s)) browser = "Firefox";
  else if (/chrome\//i.test(s)) browser = "Chrome";
  else if (/safari\//i.test(s)) browser = "Safari";

  let device = "دسکتاپ";
  if (/mobile|iphone|android.*mobile/i.test(s)) device = "موبایل";
  else if (/tablet|ipad/i.test(s)) device = "تبلت";

  return { device, browser, os };
}

function OnlineUsersGrid({
  users,
  showFields,
}: {
  users: ChatOnlineUser[];
  showFields: string[];
}) {
  // Expanded extra-tabs state (plugin admin-online.js preserves this across the
  // 5s refresh L42-46).
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (key: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  if (users.length === 0) {
    // AD: plugin admin-online.js:38 — emoji 56px, title 18px, hint 12px, py-16.
    return (
      <div className="py-16 text-center text-muted-foreground">
        <div className="mb-3 text-[56px] leading-none">😴</div>
        <p className="text-lg font-bold text-muted-foreground/60">هیچ کاربری آنلاین نیست</p>
        <p className="mt-2 text-xs text-muted-foreground/60">
          به محض ورود کاربر، اینجا نمایش داده می‌شود
        </p>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {users.map((u) => {
        const extraTabs = u.tabs.slice(1);
        const isOpen = expanded.has(u.session_key);
        const ua = parseUA(u.user_agent);
        return (
          <div
            key={u.session_key}
            className="flex flex-col justify-between rounded-2xl border bg-card p-5 shadow-sm transition-shadow hover:shadow-md"
          >
            <div>
              <div className="mb-2 flex items-center justify-between">
                <div className="flex min-w-0 items-center gap-2">
                  {/* A3: the plugin's dot pulses opacity (n8nPulseGreen) AND
                      carries a green glow (box-shadow 0 0 8px #22c55e).
                      `animate-pulse` matches the opacity pulse; the arbitrary
                      shadow supplies the glow. */}
                  <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-green-500 shadow-[0_0_8px_#22c55e]" />
                  <span className="truncate text-sm font-bold">{u.user_name}</span>
                </div>
                <span className="shrink-0 rounded-full bg-green-50 px-2 py-0.5 text-[10px] font-bold text-green-600">
                  آنلاین
                </span>
              </div>
              <div className="rounded-xl border bg-muted/40 p-3">
                <div className="mb-1 flex items-center gap-1 text-xs font-bold text-muted-foreground">
                  <FileText className="h-3 w-3" /> صفحه فعلی:
                </div>
                {u.tabs[0] && (
                  <>
                    <a
                      href={u.tabs[0].url}
                      target="_blank"
                      rel="noreferrer"
                      className="block truncate text-sm font-medium text-primary hover:underline"
                      title={u.tabs[0].url}
                    >
                      {u.tabs[0].title}
                    </a>
                    <div className="mt-1 truncate text-[10px] text-muted-foreground" dir="ltr">
                      {u.tabs[0].url}
                    </div>
                  </>
                )}
                {extraTabs.length > 0 && (
                  <>
                    {isOpen && (
                      <div className="mt-2 space-y-2 border-t pt-2">
                        {extraTabs.map((t, i) => (
                          <div key={i}>
                            <div className="mb-1 flex items-center gap-1 text-xs font-bold text-muted-foreground">
                              <FileText className="h-3 w-3" /> صفحه {i + 2}:
                            </div>
                            <a
                              href={t.url}
                              target="_blank"
                              rel="noreferrer"
                              className="block truncate text-sm font-medium text-primary hover:underline"
                              title={t.url}
                            >
                              {t.title}
                            </a>
                            <div className="mt-1 truncate text-[10px] text-muted-foreground" dir="ltr">
                              {t.url}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => toggle(u.session_key)}
                      className="mt-2 flex w-full items-center justify-center gap-1 text-center text-[10px] font-bold text-primary transition hover:brightness-75"
                    >
                      {isOpen ? (
                        <>
                          <ChevronUp className="h-3 w-3" /> بستن
                        </>
                      ) : (
                        <>
                          <ChevronDown className="h-3 w-3" /> مشاهده {extraTabs.length} صفحه دیگر
                        </>
                      )}
                    </button>
                  </>
                )}
              </div>
              <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                {showFields.includes("ip") && u.user_ip && (
                  <div className="flex items-center gap-1" dir="ltr">
                    <Globe className="h-3 w-3 font-bold text-foreground" />
                    <span className="font-bold text-foreground">IP:</span> {u.user_ip}
                  </div>
                )}
                {showFields.includes("ua") && u.user_agent && (
                  <div className="flex items-center gap-1 truncate">
                    <Monitor className="h-3 w-3" />
                    {ua.device} — {ua.browser} / {ua.os}
                  </div>
                )}
                {showFields.includes("phone") && u.user_phone && (
                  <div className="flex items-center gap-1" dir="ltr">
                    <Phone className="h-3 w-3 font-bold text-foreground" />
                    <span className="font-bold text-foreground">تلفن:</span> {u.user_phone}
                  </div>
                )}
                {showFields.includes("phone") && u.user_email && (
                  <div className="flex items-center gap-1" dir="ltr">
                    <Mail className="h-3 w-3 font-bold text-foreground" />
                    <span className="font-bold text-foreground">ایمیل:</span> {u.user_email}
                  </div>
                )}
              </div>
            </div>
            <Button
              size="sm"
              className="mt-3 flex h-8 w-full items-center justify-center gap-1 text-xs font-bold"
              onClick={() => {
                window.location.href = `/admin/chat?session=${encodeURIComponent(u.session_key)}`;
              }}
            >
              <MessageCircle className="h-3.5 w-3.5" /> ارسال پیام
            </Button>
          </div>
        );
      })}
    </div>
  );
}
