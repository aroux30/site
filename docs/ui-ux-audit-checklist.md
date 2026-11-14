# UI/UX Audit Checklist — port vs WordPress plugin (LIVING DOCUMENT)

**Purpose:** the single source of truth for UI/UX parity. Every element, every
value, every state — with plugin file:line, port status, and how it was
verified. NOTHING is "done" until the Verify column shows a measured result.

**Plugin:** `C:\Users\Administrator\Desktop\chat-bot`
**Port:** `C:\Users\Administrator\Desktop\site`
**Reference render:** `.claude/tmp/plugin-reference-widget.html` (plugin markup
+ CSS verbatim) — render it and compare screenshots for anything visual.
**Rule:** a checklist row closes ONLY with a live measurement (Playwright
computed style / screenshot), never by reading code.

Legend: ✅ verified by measurement · 🟡 implemented, awaiting measurement ·
❌ missing/wrong · ⚪ not applicable

---

## A. STRUCTURAL ELEMENTS (plugin script.js:192-235)

| # | Element | Plugin spec | Port status | Verify method |
|---|---------|-------------|-------------|---------------|
| A1 | Widget root | `position:fixed, z 999999, font Vazirmatn,Inter,Segoe UI` | ✅ | computed style |
| A2 | Halos container | 56×56 at btnBottom/btnSide, z 999997, display none→fadeIn with proactive | ✅ (gated proactive) | z-index + visibility |
| A3 | Pro ring | 64×64, border 2px color_button, opacity .35, z 999996, `n8nBreath 2.5s` | ✅ ALWAYS (owner override) | computed (proactive OFF test done) |
| A4 | Toggle wrap | 56×56 at btnBottom/btnSide, z 999999 | ✅ | bounding box |
| A5 | Toggle button | 56×56, radius 50%, bg color_button (or transparent if icon), shadow `0 8px 25px rgba(95,70,248,.4)`, transition transform .3s/opacity .3s, overflow hidden | ✅ | computed |
| A6 | Toggle icons | chat icon 28×28 / down icon 28×28, swapped on open | 🟡 | screenshot open/closed |
| A7 | Badge | 14×14, #ef4444, border 2px white, `n8nPulse 1.5s`, top-inline-end -2px | ✅ (D7) | computed with unread |
| A8 | Proactive wrap | bottom btnBottom+14, side btnSide+76, z 999998, transform-origin per side, `n8nBreath 2.5s` | ✅ | computed |
| A9 | Proactive bubble | bg color_proactive_bg, padding 6px [12 6 24 / 24 6 12], radius 22, shadow `0 2px 10px rgba(0,0,0,.06)`, border 1.5px, font 12/600, nowrap | 🟡 | computed |
| A10 | Proactive tail | 6px triangle per side | 🟡 | screenshot |
| A11 | Proactive close | ✕ absolute, opacity .5→1 + color→#ef4444 on hover, font 13, padding 4 | 🟡 | hover computed |
| A12 | Window | W=min(widget_width,600) H=widget_height, bottom 90/20, radius 20, shadow `0 12px 48px rgba(0,0,0,.15)`, border 1px | ✅ (D6/RB2) | computed |
| A13 | Header | bg color_header, padding 14px 18px, title 15/700, handoff pill `6px 20px r20 11/700` bg rgba(255,255,255,.15), close `4px 8px r8 16px` | ✅ (D5) | computed |
| A14 | Body | flex 1, overflow-y auto, bg color_viewbg | 🟡 | computed |
| A15 | Tabs bar | height 58, bg surface, opacity .98, backdrop-blur 20, border-top | 🟡 | computed |
| A16 | Tab button | flex 1, column, gap 1, padding 4px 0, font 9, color #8d94b5 inactive / primary active, `.tw` wrapper padding 6 radius 10, active bg #edf0f5 | ✅ (D9) | computed |
| A17 | Minimize tab | same + color #ccc, label «بستن», chevron 20×20 | ✅ (D10) | computed |

## B. VIEWS (plugin script.js:236-347)

| # | View | Plugin spec | Port status | Verify |
|---|------|-------------|-------------|--------|
| B1 | Welcome banner | bg primary, padding 28 22 45, radius 0 0 28 28, title 20/700 white, sub 12 opacity .85 | ✅ (D4) | computed |
| B2 | Welcome search | margin -22px 18px 0, surface, radius 16, shadow-sm, padding 10 14, icon 16, input 12 | 🟡 | computed |
| B3 | Welcome card | padding 18px wrapper, card radius 16 padding 18 shadow-sm border, helpText 11 muted, button full width r20 13/700 shadow `0 8px 20px primary40` | ✅ (D12-14) | computed |
| B4 | Conversations list | padding 14, rows: radius 16, padding 12 16, gap 10, mb 8, shadow-sm, border primary when active; number circle 38×38 13/700 + unread dot 10×10 | ✅ (G3) | computed |
| B5 | New-chat button | full width, primary, white 13/700, padding 12, radius 20, shadow `0 8px 20px primary40`, margin-top 10 | 🟡 | computed |
| B6 | Conversations empty | 💬 40px + 13/600 + 11 hint, padding 40 20 | ✅ (E2) | screenshot |
| B7 | Prechat form | card radius 16 padding 20 shadow-sm; title 15/700 center mb 14; inputs padding 9 12 radius 10 font 12 bg body-bg; textarea h 50; submit r20 13/700 padding 12 shadow `0 6px 16px rgba(95,70,248,.2)` | ✅ (D11-14) | computed |
| B8 | Prechat error | bg #ffdfdf, border #ffcfcf, color #885e5e, padding 6 10, radius 8, font 11, center, mb 10 | ✅ (D11) | computed |
| B9 | FAQ view | padding 14; card r16 p 14 18 mb 12 shadow-sm border; header 13/700 + count chip 9/700 r6 bg surface-alt p 2 6; details mt 6 border-top pt 6; summary 12/500 + ❓ primary; answer 11 muted lh 1.7 ml 18 | ✅ (N7) | computed |
| B10 | FAQ empty | «سوالی نیست» #ccc 12px padding 50 20 | 🟡 | screenshot |
| B11 | News view | card r16 p 16 18 mb 12; icon 18 + title 13/700; desc 12 muted lh 1.5; link 11/700 primary mt 6 with → | 🟡 | computed |
| B12 | News empty | «خبری نیست» #ccc 12 padding 50 20 | 🟡 | screenshot |
| B13 | Chat messages area | padding 12, bg color_chatbg | 🟡 | computed |
| B14 | Message row | gap 8, align-end, mb 8 | 🟡 | computed |
| B15 | Avatar | 40×40 circle; user primary bg, others #e2e8f0; emoji 18 | 🟡 | computed |
| B16 | Bubble | padding 10 14, font 13, lh 1.6, min-width 60, max-width calc(100%-56px), radius 18 18 [18 4 / 4 18] per side+dir, shadow per type | ✅ | computed |
| B17 | Meta line | font 8, opacity .45, margin-top 3, opposite text-align, time + ✓/✓✓ | ✅ (code L1893) | computed after poll |
| B18 | Sender label | font 10, 700, primary, mb 4, opacity .9 (admin msgs) | 🟡 | computed |
| B19 | Composer pill | margin 10 14 14, padding 6, border 1px, radius 26, min-h 50 max-h 120, shadow-sm, bg surface | ✅ | computed |
| B20 | Composer buttons | clip/mic/emoji: padding 6, color primary, bg none | 🟡 | computed |
| B21 | Emoji panel | bottom 40, side -60, surface, border #e5e7eb, radius 20, shadow `0 10px 25px rgba(0,0,0,.15)`, padding 8, width 240, max-h 180; items 18px in 24×24 r4, hover #f3f4f6 | 🟡 | computed |
| B22 | Textarea | padding 4 8, h 28 max 60 min 28, font 12, lh 1.3, no border/bg | ✅ + **KB1 autosize** (verify) | typing test |
| B23 | Send button | 30×30 circle, bg primary, white, icon 16 mirrored RTL | 🟡 | computed |
| B24 | Voice bar | padding 10 16, border-top, shadow `0 -2px 10px rgba(0,0,0,.04)`; timer #ef4444 12/700 🎙; cancel #999 11; send #ef4444 white 4 14 r8 11/700 | 🟡 | computed |

## C. ANIMATIONS & MICRO-INTERACTIONS

| # | Item | Plugin spec | Port status | Verify |
|---|------|-------------|-------------|--------|
| C1 | n8nWiggle | tabs/minimize/toggle svg on hover: 0→-16→16→-8→0, .4s infinite | ✅ (H1) | animationName on hover |
| C2 | n8nPulse | badge scale 1→1.3→1, 1.5s | ✅ (D7) | animationName |
| C3 | n8nHalo | scale 1→1.6 opacity .5→0, 2s, staggered 1s | ✅ (HB) | animationName |
| C4 | n8nBreath | scale 1→1.06→1, 2.5s on ring + popup | ✅ (HB) | computed |
| C5 | n8nQrIn | quick buttons: opacity 0→1 + translateY(8→0), .35s, delay i*.08 | ✅ (H7) | computed delay |
| C6 | Toggle hover | scale 1.1 in/out | ✅ (H3) | bounding box |
| C7 | Proactive close hover | opacity .5→1, color→#ef4444 | ✅ (H4) | hover computed |
| C8 | Quick-btn hover | solid primary fill + white + translateY(-1px) + shadow; press scale(.97) | ✅ (H2) | hover computed |
| C9 | Proactive fade-in | jQuery fadeIn(300) for halos/ring/popup | ✅ (H9) | animationName |
| C10 | View/message entrance | `n8nUp` — **undefined in plugin = NO-OP** | ⚪ (guard test exists) | n/a |
| C11 | Transition on conv rows | `transition: all .2s` | 🟡 | computed |

## D. BEHAVIOR

| # | Item | Plugin spec | Port status | Verify |
|---|------|-------------|-------------|--------|
| D1 | Enter send / Shift+Enter newline | script.js:517 | ✅ (KB3) | keypress test |
| D2 | Textarea autosize | script.js:515 min(scrollHeight,60) | 🟡 **KB1** | typing test |
| D3 | Auto-scroll to bottom | script.js:631 etc. | ✅ (KB2) | scrollTop check |
| D4 | Session per-tab id | sessionStorage tab_id | 🟡 | storage check |
| D5 | Heartbeat 5s | always (even closed) | 🟡 | network log |
| D6 | Poll 4s in chat / 6s unread | | 🟡 | network log |
| D7 | Session validate 3s after load | | 🟡 | network log |
| D8 | Optimistic send + id swap | temp id → real id | 🟡 | DOM id check |
| D9 | Read receipts ✓/✓✓ | poll updates | ✅ (earlier) | DOM |
| D10 | Handoff countdown mm:ss | | 🟡 | DOM after handoff |
| D11 | Proactive per-refresh (owner override) | not in plugin — owner's request | ✅ | reload test |
| D12 | Mic denied alert | script.js:911 | ✅ (ES2) | code + toast |

## E. ADMIN CONSOLE (option 2: plugin structure + project green)

| # | Item | Plugin ref | Port status | Verify |
|---|------|-----------|-------------|--------|
| E1 | Tab pills | php:993-999 shape (r16, p 10 24, f14) + project green | ✅ | computed |
| E2 | Sidebar | w-80 gray-50, header h-12/14, «کاربران فعال»+«بروزرسانی» | 🟡 | computed |
| E3 | Chat header | min-h 56, white, shadow-sm; info indigo-btn; delete red-btn | 🟡 | computed |
| E4 | Session-info panel | full-width slide-down, grid 1/2/3/4 | 🟡 | screenshot |
| E5 | Composer | p-2 min-h 50; buttons p-1.5 gray hover; send circle | 🟡 | computed |
| E6 | Voice bar | h-12, red timer, cancel/send | 🟡 | computed |
| E7 | Bubbles | 38px avatars, white/green-100/indigo-100, timestamp below | 🟡 | computed |
| E8 | Online cards | r-2xl p-5 shadow-sm hover:shadow-md, green dot+glow | ✅ (A1-A3) | computed |

---

## CURRENT VERDICT (updated 2026-10-12)

- Widget **structure + welcome + prechat + tabs + header + composer pill**:
  measured matching.
- **Open items:** A6 (icon swap), A9/A10 (proactive bubble details), B2/B5/B10-B12/
  B14/B15/B18/B20/B21/B23/B24 (per-element computed checks pending), C11, D2
  (KB1 autosize), D4-D8/D10, E2-E7.
- **Approach decision (owner, 2026-10-12):** replace the React widget with the
  plugin's `script.js` VERBATIM + a bridge endpoint. Under that approach most
  of section A/B/C rows become "verbatim = matched by construction"; the
  checklist remains the verification harness (each row still measured after the
  swap).
- The checklist is the arbiter: **every row must show a measured result before
  the work is called done.** No row closes by reading code alone.

## HOW TO USE (both sessions)

1. Pick rows with 🟡/❌, implement or fix.
2. Measure the row (Playwright computed style / screenshot).
3. Update the status cell + append the measurement to
   `docs/monitor-notes-1002.md` with the date.
4. Never flip a row to ✅ without the measurement recorded in the notes.
