jQuery(document).ready(function ($) {
    const S = n8nChat.settings;
    const isFa = S.lang === 'fa';
    const C = {
        primary: S.color_primary || '#007ACC',
        header: S.color_header || '#007ACC',
        button: S.color_button || '#007ACC',
        chatbg: 'var(--n8n-bg)',
        viewbg: 'var(--n8n-bg)'
    };
    const wpUser = n8nChat.user || {};
    const isMobile = window.innerWidth <= 640;
    const W = Math.min(S.widget_width || 394, isMobile ? 9999 : 600);
    const H = S.widget_height || 650;
    const btnBottom = isMobile ? (S.btn_bottom_mobile || 70) : (S.btn_bottom_desktop || 20);
    const btnSide = isMobile ? (S.btn_side_mobile || 12) : (S.btn_side_desktop || 20);
    const dir = isFa ? 'rtl' : 'ltr', side = isFa ? 'right' : 'left';

    const t = isFa ? {
        welcome: 'خوش‌آمدید', conversations: 'گفتگوها', faqs: 'سوالات متداول', news: 'اخبار',
        minimize: 'بستن', sendMsg: 'ارسال پیام به ما', searchFaq: 'جستجو در سوالات...',
        newChat: 'شروع گفتگوی جدید', typeMsg: 'پیام خود را بنویسید...',
        cancel: 'لغو', send: 'ارسال', helpText: 'ما اینجا هستیم تا به شما کمک کنیم',
        activeSession: 'جلسه فعال', continueChat: 'ادامه گفتگو...', supportChat: 'چت پشتیبانی',
        readMore: 'مشاهده بیشتر', liveSupport: 'پشتیبانی زنده',
        formTitle: 'اطلاعات شما', formSubmit: 'شروع گفتگو', formRequired: 'لطفاً فیلدهای اجباری را پر کنید', guest: 'مهمان'
    } : {
        welcome: 'Welcome', conversations: 'Conversations', faqs: 'FAQs', news: 'News',
        minimize: 'Minimize', sendMsg: 'Send us a message', searchFaq: 'Search FAQs...',
        newChat: 'Start New Conversation', typeMsg: 'Type a message...',
        cancel: 'Cancel', send: 'Send', helpText: "We're here to help you",
        activeSession: 'Active', continueChat: 'Continue...', supportChat: 'Support Chat',
        readMore: 'Read more', liveSupport: 'Live Support',
        formTitle: 'Your Information', formSubmit: 'Start Chat', formRequired: 'Please fill required fields', guest: 'Guest'
    };

    // STATE
    const state = {
        isOpen: false, view: 'welcome',
        sessionId: localStorage.getItem('n8n_chat_session_id'),
        sessions: JSON.parse(localStorage.getItem('n8n_chat_sessions') || '[]'),
        lastMsgId: 0, mediaRecorder: null, audioChunks: [], voiceTimer: null,
        unreadSessions: {}, prevTotalUnread: -1,
        flowContext: [],
        sessionCreatedAt: 0 // timestamp آخرین ایجاد session — برای جلوگیری از حذف زودهنگام
    };

    // NOTIFICATION SOUND (Web Audio API - no file needed)
    // NOTIFICATION SOUND
    let audioCtx = null;
    function playBeep() {
        try {
            if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const now = audioCtx.currentTime;
            [[880, 0], [1320, 0.12]].forEach(([freq, delay]) => {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'sine'; osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.3, now + delay);
                gain.gain.exponentialRampToValueAtTime(0.001, now + delay + 0.15);
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.start(now + delay); osc.stop(now + delay + 0.15);
            });
        } catch (e) { }
    }
    function playNotifSound() {
        // Prevent multi-tab beep storms if user has 3 tabs open
        const lastBeep = parseInt(localStorage.getItem('n8n_last_beep') || '0');
        if (Date.now() - lastBeep < 3000) return;
        localStorage.setItem('n8n_last_beep', Date.now());

        if (S.sound_url && S.sound_url.length > 5 && !S.sound_url.includes('notification.mp3')) {
            const a = new Audio(S.sound_url);
            a.volume = 1.0;
            const p = a.play();
            if (p !== undefined) p.catch(() => playBeep());
        } else {
            playBeep();
        }
    }
    // Generate a tracking ID if we don't have one (for online monitoring)
    // BUT DO NOT push it to state.sessions (so it doesn't show as a chat)
    if (!state.sessionId) {
        state.sessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
        localStorage.setItem('n8n_chat_session_id', state.sessionId);
    }

    // VALIDATE SESSIONS ON LOAD
    if (state.sessions.length > 0) {
        setTimeout(validateLocalSessions, 3000);
    }

    // TAB ID for grouping multiple tabs
    let tabId = sessionStorage.getItem('n8n_chat_tab_id');
    if (!tabId) {
        tabId = 't_' + Math.random().toString(36).substr(2, 5);
        sessionStorage.setItem('n8n_chat_tab_id', tabId);
    }

    // HEARTBEAT - track online presence
    function sendHeartbeat() {
        if (!state.sessionId) return;
        const d = {
            action: 'n8n_chat_heartbeat',
            nonce: n8nChat.nonce,
            session_id: state.sessionId,
            tab_id: tabId,
            page_url: window.location.href,
            page_title: document.title,
            _t: Date.now()
        };
        if (wpUser && wpUser.id) {
            d.user_id = wpUser.id;
            d.user_name = wpUser.name;
            d.user_email = wpUser.email;
        }
        $.post(n8nChat.ajax_url, d);
    }
    // Always send heartbeat to show online users
    sendHeartbeat();
    setInterval(sendHeartbeat, 5000);

    // ICONS
    const icons = {
        welcome: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>',
        conversations: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/></svg>',
        faqs: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        news: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"/></svg>',
        chat: '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/></svg>',
        down: '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>',
        downSm: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>',
        clip: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/></svg>',
        mic: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"/></svg>',
        search: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="#999"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>',
        sendArr: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="transform:${isFa ? 'scaleX(-1)' : 'none'};"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`
    };

    // BUILD
    $('body').append(`
    <style>
        :root {
            --n8n-bg: #EEEEEE;
            --n8n-fg: #101010;
            --n8n-accent: ${C.primary};
            --n8n-surface: #FFFFFF;
            --n8n-surface-alt: #F8F8F8;
            --n8n-border: rgba(0,0,0,0.08);
            --n8n-muted: #666666;
            --n8n-shadow: 0 12px 48px rgba(0,0,0,0.15);
            --n8n-shadow-sm: 0 4px 16px rgba(0,0,0,0.08);
            --n8n-radius: 20px;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --n8n-bg: #101010;
                --n8n-fg: #CCCCCC;
                --n8n-surface: #1E1E1E;
                --n8n-surface-alt: #282828;
                --n8n-border: rgba(255,255,255,0.08);
                --n8n-muted: #999999;
                --n8n-shadow: 0 12px 48px rgba(0,0,0,0.4);
                --n8n-shadow-sm: 0 4px 16px rgba(0,0,0,0.3);
            }
        }
        
        #n8n-win { background: var(--n8n-bg) !important; box-shadow: var(--n8n-shadow) !important; border-radius: var(--n8n-radius) !important; border: 1px solid var(--n8n-border) !important; }
        .n8n-surface { background: var(--n8n-surface) !important; border: 1px solid var(--n8n-border) !important; box-shadow: var(--n8n-shadow-sm) !important; color: var(--n8n-fg) !important; }
        .n8n-text { color: var(--n8n-fg) !important; }
        .n8n-muted { color: var(--n8n-muted) !important; }
        .n8n-input { background: var(--n8n-surface) !important; color: var(--n8n-fg) !important; border: 1px solid var(--n8n-border) !important; }
        .n8n-input:focus { border-color: var(--n8n-accent) !important; }
        .n8n-bubble-me { background: var(--n8n-accent) !important; color: #fff !important; border-radius: 18px 18px 4px 18px !important; box-shadow: 0 4px 12px rgba(0,122,204,0.3) !important; }
        .n8n-bubble-me-fa { border-radius: 18px 18px 18px 4px !important; }
        .n8n-bubble-other { background: var(--n8n-surface) !important; color: var(--n8n-fg) !important; border: 1px solid var(--n8n-border) !important; border-radius: 18px 18px 18px 4px !important; box-shadow: var(--n8n-shadow-sm) !important; }
        .n8n-bubble-other-fa { border-radius: 18px 18px 4px 18px !important; }

        @keyframes n8nWiggle { 0% { transform: rotate(0deg); } 25% { transform: rotate(-16deg); } 50% { transform: rotate(16deg); } 75% { transform: rotate(-8deg); } 100% { transform: rotate(0deg); } }
        .ntab:hover svg, #n8n-min:hover svg, #n8n-toggle:hover svg { animation: n8nWiggle 0.4s ease-in-out infinite; }
        #cm { display: flex !important; flex-direction: column !important; }
        .n8n-msg-me { margin-left: auto !important; margin-right: 0 !important; }
        .n8n-msg-other { margin-right: auto !important; margin-left: 0 !important; }
        #n8n-badge { position:absolute; top:-2px; right:-2px; width:14px; height:14px; background:#ef4444; border-radius:50%; border:2px solid #fff; display:none; animation: n8nPulse 1.5s ease-in-out infinite; z-index:1000001; }
        @keyframes n8nPulse { 0%,100% { transform:scale(1); } 50% { transform:scale(1.3); } }
        @keyframes n8nHalo { 0% { transform: scale(1); opacity: 0.5; } 100% { transform: scale(1.6); opacity: 0; } }
        .n8n-halo { position:absolute; inset:0; border-radius:50%; background:${C.button}; opacity:0; pointer-events:none; }
        .n8n-halo-1 { animation: n8nHalo 2s infinite ease-out; }
        .n8n-halo-2 { animation: n8nHalo 2s infinite ease-out 1s; }
        @keyframes n8nBreath { 0%,100% { transform:scale(1); } 50% { transform:scale(1.06); } }
        #n8n-proactive-wrap { animation: n8nBreath 2.5s ease-in-out infinite; }
        #n8n-pro-ring { animation: n8nBreath 2.5s ease-in-out infinite; }
    </style>
    <div id="n8n-w" style="direction:${dir};position:fixed;z-index:999999;font-family:Vazirmatn,Inter,Segoe UI,sans-serif;">
        <!-- Halos -->
        <div id="n8n-halos" style="display:none;position:fixed;bottom:${btnBottom}px;${side}:${btnSide}px;width:56px;height:56px;z-index:999997;pointer-events:none;">
            <div class="n8n-halo n8n-halo-1"></div><div class="n8n-halo n8n-halo-2"></div>
        </div>
        
        <!-- Thin ring around button (shows with proactive) -->
        <div id="n8n-pro-ring" style="display:none;position:fixed;bottom:${btnBottom - 4}px;${side}:${btnSide - 4}px;width:64px;height:64px;border-radius:50%;border:2px solid ${C.button};opacity:0.35;z-index:999996;pointer-events:none;"></div>

        <!-- Toggle Button Wrapper (overflow:visible for badge) -->
        <div id="n8n-toggle-wrap" style="position:fixed;bottom:${btnBottom}px;${side}:${btnSide}px;width:56px;height:56px;z-index:999999;">
            <button id="n8n-toggle" aria-label="${t.supportChat || 'گفتگوی آنلاین'}" style="width:56px;height:56px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;background:${S.widget_icon_url ? 'transparent' : C.button};color:#fff;box-shadow:0 8px 25px rgba(95,70,248,0.4);transition:transform 0.3s,opacity 0.3s;overflow:hidden;">
                <span id="ico-o" style="position:absolute;top:0;left:0;width:100%;height:100%;display:flex;align-items:center;justify-content:center;">${S.widget_icon_url ? `<img src="${S.widget_icon_url}" style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;border-radius:50%;" />` : icons.chat}</span><span id="ico-c" style="display:none;position:absolute;top:0;left:0;width:100%;height:100%;align-items:center;justify-content:center;">${icons.down}</span>
            </button>
            <span id="n8n-badge" style="display:none;position:absolute;top:-2px;${side === 'right' ? 'left' : 'right'}:-2px;width:14px;height:14px;background:#ef4444;border-radius:50%;border:2px solid #fff;z-index:2;pointer-events:none;animation:n8nPulse 1.5s ease-in-out infinite;"></span>
        </div>

        <!-- Proactive Bubble -->
        <div id="n8n-proactive-wrap" style="display:none;position:fixed;bottom:${btnBottom + 14}px;${side}:${btnSide + 76}px;z-index:999998;transform-origin:${side === 'right' ? 'right' : 'left'} center;">
            <div id="n8n-proactive" style="background:${S.color_proactive_bg || '#ffffff'};padding:6px ${side === 'right' ? '12px 6px 24px' : '24px 6px 12px'};border-radius:22px;box-shadow:0 2px 10px rgba(0,0,0,0.06);color:${S.color_proactive_text || C.primary};font-size:12px;font-weight:600;white-space:nowrap;cursor:pointer;border:1.5px solid rgba(0,0,0,0.06);animation:n8nUp .4s ease;">
                <span id="n8n-pro-text"></span>
                <div style="position:absolute;top:50%;transform:translateY(-50%);${side === 'right' ? 'right:-5px;border-left:6px solid '+(S.color_proactive_bg || '#ffffff')+';border-top:6px solid transparent;border-bottom:6px solid transparent;' : 'left:-5px;border-right:6px solid '+(S.color_proactive_bg || '#ffffff')+';border-top:6px solid transparent;border-bottom:6px solid transparent;'}"></div>
                <button class="n8n-proactive-close" style="position:absolute;top:50%;transform:translateY(-50%);${side === 'right' ? 'left:4px;' : 'right:4px;'};background:none;border:none;color:${S.color_proactive_text || C.primary};opacity:0.5;font-size:13px;display:flex;align-items:center;justify-content:center;cursor:pointer;line-height:1;padding:4px;transition:all .2s;">✕</button>
            </div>
        </div>

        <div id="n8n-win" style="display:none;position:fixed;bottom:${isMobile ? 0 : 90}px;${isMobile ? 'left:0;right:0;top:0;' : ''}${!isMobile ? side + ':20px;width:' + W + 'px;height:' + H + 'px;border-radius:var(--n8n-radius);' : ''}background:var(--n8n-bg);box-shadow:var(--n8n-shadow);border:1px solid var(--n8n-border);overflow:hidden;flex-direction:column;z-index:999998;">
            <div id="n8n-hdr" style="background:${C.header};padding:14px 18px;display:flex;justify-content:space-between;align-items:center;color:#fff;flex-shrink:0;">
                <h3 id="n8n-title" style="font-weight:700;font-size:15px;margin:0;">${t.welcome}</h3>
                <div style="display:flex;align-items:center;gap:18px;">
                    <button id="n8n-user-handoff" style="display:none;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);color:#fff;padding:6px 20px;border-radius:var(--n8n-radius);cursor:pointer;font-size:11px;font-weight:700;font-family:inherit;transition:all 0.2s;">${S.handoff_button_text || 'انتقال به انسان'}</button>
                    <button id="n8n-x" style="background:rgba(255,255,255,0.15);border:none;color:#fff;padding:4px 8px;border-radius:8px;cursor:pointer;font-size:16px;">✕</button>
                </div>
            </div>
            <div id="n8n-body" style="flex:1;overflow-y:auto;background:${C.viewbg};"></div>
            <div id="n8n-tabs" style="display:flex;align-items:center;height:58px;flex-shrink:0;background:var(--n8n-surface); opacity:0.98;backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-top:1px solid var(--n8n-border);">
                ${['welcome', 'conversations', 'faqs', 'news'].map(v => `<button data-v="${v}" class="ntab" style="flex:1;display:flex;flex-direction:column;align-items:center;gap:1px;padding:4px 0;border:none;background:none;cursor:pointer;color:var(--n8n-muted);font-size:9px;font-family:inherit;"><div class="tw" style="padding:6px;border-radius:10px;">${icons[v]}</div><span>${t[v]}</span></button>`).join('')}
                <button id="n8n-min" style="flex:1;display:flex;flex-direction:column;align-items:center;gap:1px;padding:4px 0;border:none;background:none;cursor:pointer;color:#ccc;font-size:9px;font-family:inherit;">
                    <div style="padding:6px;">${icons.downSm}</div><span>${t.minimize}</span>
                </button>
            </div>
        </div>
    </div>`);

    // ============ VIEWS ============
    const V = {
        welcome: () => `<div style="animation:n8nUp .3s ease;">
            <div style="background:${C.primary};padding:28px 22px 45px;text-align:center;color:#fff;border-radius:0 0 28px 28px;">
                <h2 style="font-size:20px;font-weight:700;margin:0 0 4px;">${S.welcome_title || t.welcome}</h2>
                <p style="font-size:12px;opacity:0.85;margin:0;">${S.welcome_sub || ''}</p>
            </div>
            <div style="margin:-22px 18px 0;position:relative;z-index:2;">
                <div style="background:var(--n8n-surface);border-radius:16px;box-shadow:var(--n8n-shadow-sm);display:flex;align-items:center;padding:10px 14px;border:1px solid #f0f0f0;">
                    <span style="margin-${isFa ? 'left' : 'right'}:8px;flex-shrink:0;">${icons.search}</span>
                    <input type="text" placeholder="${t.searchFaq}" style="border:none;background:transparent;outline:none;font-size:12px;width:100%;color:var(--n8n-fg);font-family:inherit;">
                </div>
            </div>
            <div style="padding:18px;">
                <div style="background:var(--n8n-surface);border-radius:16px;padding:18px;text-align:center;box-shadow:var(--n8n-shadow-sm);border:1px solid var(--n8n-border);">
                    <p style="font-size:11px;color:var(--n8n-muted);margin:0 0 12px;">${t.helpText}</p>
                    <button id="btn-start" style="width:100%;background:${C.primary};color:#fff;font-weight:700;font-size:13px;padding:12px;border:none;border-radius:var(--n8n-radius);cursor:pointer;box-shadow:0 8px 20px ${C.primary}40;font-family:inherit;">${t.sendMsg}</button>
                </div>
            </div>
        </div>`,

        conversations: () => {
            let h = '';
            if (state.sessions.length === 0) {
                h = `<div style="text-align:center;padding:40px 20px;color:var(--n8n-muted);">
                    <div style="font-size:40px;margin-bottom:12px;">💬</div>
                    <p style="font-size:13px;font-weight:600;color:var(--n8n-fg);margin:0 0 6px;">${isFa ? 'هنوز گفتگویی ندارید' : 'No conversations yet'}</p>
                    <p style="font-size:11px;margin:0;">${isFa ? 'برای شروع گفتگو، دکمه زیر را بزنید' : 'Click the button below to start a conversation'}</p>
                </div>`;
            } else {
                state.sessions.forEach((sid, i) => {
                    const on = sid === state.sessionId;
                    h += `<div class="cv" data-sid="${sid}" style="background:var(--n8n-surface);border-radius:16px;padding:12px 16px;display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:8px;box-shadow:var(--n8n-shadow-sm);border:1px solid ${on ? C.primary : 'var(--n8n-border)'};transition:all .2s;">
                        <div style="width:38px;height:38px;background:var(--n8n-surface-alt);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;color:${C.primary};font-size:13px;flex-shrink:0;position:relative;">${i + 1}${(state.unreadSessions[sid] || 0) > 0 ? '<span style="position:absolute;top:-2px;right:-2px;width:10px;height:10px;background:#ef4444;border-radius:50%;border:2px solid #fff;"></span>' : ''}</div>
                        <div style="flex:1;text-align:${isFa ? 'right' : 'left'};"><div style="font-weight:600;font-size:12px;color:var(--n8n-fg);">${t.supportChat} #${i + 1}</div><div style="font-size:10px;color:var(--n8n-muted);">${on ? t.activeSession : t.continueChat}</div></div>
                    </div>`;
                });
            }
            return `<div style="height:100%;display:flex;flex-direction:column;padding:14px;box-sizing:border-box;animation:n8nUp .3s ease;"><div style="flex:1;overflow-y:auto;">${h}</div><button id="btn-new" style="width:100%;background:${C.primary};color:#fff;font-weight:700;font-size:13px;padding:12px;border:none;border-radius:var(--n8n-radius);cursor:pointer;box-shadow:0 8px 20px ${C.primary}40;font-family:inherit;margin-top:10px;">${t.newChat}</button></div>`;
        },

        prechat: () => {
            const fields = S.prechat_fields || [];
            let fh = '';
            fields.forEach(f => {
                const req = f.required ? 'required' : '', star = f.required ? '<span style="color:red;">*</span>' : '';
                const st = 'width:100%;padding:9px 12px;border:1px solid var(--n8n-border);border-radius:10px;font-size:12px;font-family:inherit;outline:none;background:var(--n8n-bg);color:var(--n8n-fg);border:1px solid var(--n8n-border);box-sizing:border-box;';
                if (f.type === 'textarea') fh += `<div style="margin-bottom:10px;"><label style="display:block;font-size:11px;font-weight:600;color:var(--n8n-fg);margin-bottom:3px;">${f.label} ${star}</label><textarea name="pcf_${f.key}" ${req} style="${st}resize:none;height:50px;"></textarea></div>`;
                else fh += `<div style="margin-bottom:10px;"><label style="display:block;font-size:11px;font-weight:600;color:var(--n8n-fg);margin-bottom:3px;">${f.label} ${star}</label><input type="${f.type}" name="pcf_${f.key}" ${req} style="${st}" ${f.type === 'tel' || f.type === 'email' ? 'dir="ltr"' : ''}></div>`;
            });
            return `<div style="padding:18px;animation:n8nUp .3s ease;"><div style="background:var(--n8n-surface);border-radius:16px;padding:20px;box-shadow:var(--n8n-shadow-sm);border:1px solid var(--n8n-border);">
                <h3 style="font-size:15px;font-weight:700;color:var(--n8n-fg);margin:0 0 14px;text-align:center;">${t.formTitle}</h3>
                <div id="pcf-err" style="display:none;background:#ffdfdf;border:1px solid #ffcfcf;color:#885e5e;padding:6px 10px;border-radius:8px;font-size:11px;margin-bottom:10px;text-align:center;">${t.formRequired}</div>
                <form id="pcf">${fh}<button type="submit" style="width:100%;background:${C.primary};color:#fff;font-weight:700;font-size:13px;padding:12px;border:none;border-radius:var(--n8n-radius);cursor:pointer;font-family:inherit;margin-top:4px;box-shadow:0 6px 16px rgba(95,70,248,0.2);">${t.formSubmit}</button></form>
            </div></div>`;
        },

        faqs: () => {
            const faqs = S.faqs || [];
            if (!faqs.length) return `<div style="text-align:center;padding:50px 20px;color:#ccc;font-size:12px;">${isFa ? 'سوالی نیست' : 'No FAQs'}</div>`;
            let g = {}; faqs.forEach(f => { const c = f.cat || (isFa ? 'عمومی' : 'General'); if (!g[c]) g[c] = []; g[c].push(f); });
            let h = '<div style="padding:14px;animation:n8nUp .3s ease;">';
            for (const cat in g) {
                h += `<div style="background:var(--n8n-surface);border-radius:16px;padding:14px 18px;margin-bottom:12px;box-shadow:var(--n8n-shadow-sm);border:1px solid var(--n8n-border);">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><h4 style="font-weight:700;font-size:13px;color:var(--n8n-fg);margin:0;">${cat}</h4><span style="font-size:9px;font-weight:700;color:var(--n8n-muted);background:var(--n8n-surface-alt);padding:2px 6px;border-radius:6px;">${g[cat].length}</span></div>`;
                g[cat].forEach(f => { h += `<details style="margin-top:6px;border-top:1px solid var(--n8n-border);padding-top:6px;"><summary style="font-size:12px;font-weight:500;color:var(--n8n-fg);cursor:pointer;list-style:none;display:flex;align-items:center;gap:4px;"><span style="color:${C.primary};">❓</span>${f.q}</summary><p style="font-size:11px;color:var(--n8n-muted);line-height:1.7;margin:4px 0 0 18px;">${f.a}</p></details>`; });
                h += '</div>';
            }
            return h + '</div>';
        },

        news: () => {
            const news = S.news || [];
            if (!news.length) return `<div style="text-align:center;padding:50px 20px;color:#ccc;font-size:12px;">${isFa ? 'خبری نیست' : 'No news'}</div>`;
            let h = '<div style="padding:14px;animation:n8nUp .3s ease;">';
            news.forEach(n => {
                h += `<div style="background:var(--n8n-surface);border-radius:16px;padding:16px 18px;margin-bottom:12px;box-shadow:var(--n8n-shadow-sm);border:1px solid var(--n8n-border);">
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;"><span style="font-size:18px;">${n.icon || '🚀'}</span><h4 style="font-weight:700;font-size:13px;color:var(--n8n-fg);margin:0;">${n.title}</h4></div>
                <p style="font-size:12px;color:var(--n8n-muted);line-height:1.5;margin:0;">${n.desc}</p>
                ${n.link ? `<a href="${n.link}" target="_blank" style="display:inline-block;margin-top:6px;font-size:11px;font-weight:700;color:${C.primary};text-decoration:none;">${t.readMore} →</a>` : ''}
            </div>`;
            });
            return h + '</div>';
        },

        chat: () => {
            const EMOJIS = ["😀", "😁", "😂", "🤣", "😃", "😄", "😅", "😆", "😉", "😊", "😋", "😎", "😍", "😘", "😗", "😙", "😚", "☺️", "🙂", "🤗", "🤔", "😐", "😑", "😶", "🙄", "😏", "😣", "😥", "😮", "🤐", "😯", "😪", "😫", "😴", "😌", "😛", "😜", "😝", "🤤", "😒", "😓", "😔", "😕", "🙃", "🤑", "😲", "☹️", "🙁", "😖", "😞", "😟", "😤", "😢", "😭", "😦", "😧", "😨", "😩", "😬", "😰", "😱", "😳", "😵", "😡", "😠", "😷", "🤒", "🤕", "🤢", "🤧", "😇", "🤠", "🤡", "🤥", "🤓", "😈", "👿", "👹", "👺", "💀", "👻", "👽", "👾", "🤖", "💩", "😺", "😸", "😹", "😻", "😼", "😽", "🙀", "😿", "😾", "👋", "🤚", "🖐", "✋", "🖖", "👌", "✌️", "🤞", "🤟", "🤘", "🤙", "👈", "👉", "👆", "🖕", "👇", "☝️", "👍", "👎", "✊", "👊", "🤛", "🤜", "👏", "🙌", "👐", "🤝", "🙏", "✍️", "💅", "🤳", "💪", "❤️", "💛", "💚", "💙", "💜", "🖤", "💔", "❣️", "💕", "💞", "💓", "💗", "💖", "💘", "💝"];
            let emHtml = EMOJIS.map(e => `<span class="emoji-it" style="cursor:pointer;font-size:18px;width:24px;height:24px;display:flex;align-items:center;justify-content:center;border-radius:4px;user-select:none;transition:background 0.2s;" onmouseover="this.style.background='#f3f4f6'" onmouseout="this.style.background='transparent'">${e}</span>`).join('');
            return `<div id="cw" style="display:flex;flex-direction:column;height:100%;">
            <div id="cm" style="flex:1;overflow-y:auto;padding:12px;background:${C.chatbg};"></div>
            <div style="--km-font-family: Inter,Segoe UI,-apple-system,sans-serif; color: var(--n8n-fg); text-rendering: optimizeLegibility; visibility: visible; border-spacing: 0; font-size: 14px; line-height: normal; font-weight: 400; width: auto !important; outline: 0 !important; margin: 10px 14px 14px !important; text-align: left; box-shadow: var(--n8n-shadow-sm); min-height: 50px !important; max-height: 120px !important; display: flex !important; align-items: center !important; gap: 0 !important; padding: 6px !important; border: 1px solid var(--n8n-border) !important; border-radius: 26px !important; background-color: var(--n8n-surface) !important; box-sizing: border-box !important; transition: border-color .2s ease,box-shadow .2s ease; font-family: var(--km-font-family); flex-shrink: 0 !important;">
                <button id="ba" style="background:none !important;border:none !important;cursor:pointer !important;padding:6px !important;color:${C.primary} !important;display:flex !important;flex-shrink:0 !important;margin:0 !important;">${icons.clip}</button>
                <button id="bm" style="background:none !important;border:none !important;cursor:pointer !important;padding:6px !important;color:${C.primary} !important;display:flex !important;flex-shrink:0 !important;margin:0 !important;">${icons.mic}</button>
                
                <div style="position:relative;display:flex;align-items:center;">
                    <button id="be" style="background:none !important;border:none !important;cursor:pointer !important;padding:6px !important;color:${C.primary} !important;display:flex !important;flex-shrink:0 !important;margin:0 !important;"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M8 14s1.5 2 4 2 4-2 4-2"></path><line x1="9" y1="9" x2="9.01" y2="9"></line><line x1="15" y1="9" x2="15.01" y2="9"></line></svg></button>
                    <div id="bep" style="display:none;position:absolute;bottom:40px;${dir === 'rtl' ? 'right:-60px;' : 'left:-60px;'}background:var(--n8n-surface);border:1px solid #e5e7eb;border-radius:var(--n8n-radius);box-shadow:0 10px 25px rgba(0,0,0,0.15);padding:8px;width:240px;max-height:180px;overflow-y:auto;z-index:9999;flex-wrap:wrap;gap:4px;align-content:flex-start;">${emHtml}</div>
                </div>

                <textarea id="ci" rows="1" placeholder="${t.typeMsg}" style="flex:1 !important;padding:4px 8px !important;border:none !important;background:transparent !important;resize:none !important;height:28px !important;max-height:60px !important;min-height:28px !important;font-size:12px !important;font-family:inherit !important;outline:none !important;line-height:1.3 !important;color:var(--n8n-fg) !important;margin:0 !important;box-shadow:none !important;"></textarea>
                <button id="bs" style="background:${C.primary} !important;color:#fff !important;border:none !important;cursor:pointer !important;padding:0 !important;border-radius:50% !important;display:flex !important;align-items:center !important;justify-content:center !important;width:30px !important;height:30px !important;min-width:30px !important;min-height:30px !important;flex-shrink:0 !important;margin:0 !important;">${icons.sendArr}</button>
            </div>
            <div id="vbar" style="display:none;position:absolute;bottom:0;left:0;right:0;background:var(--n8n-surface);padding:10px 16px;border-top:1px solid var(--n8n-border);z-index:40;justify-content:space-between;align-items:center;box-shadow:0 -2px 10px rgba(0,0,0,0.04);">
                <div style="display:flex;align-items:center;gap:4px;color:#ef4444;font-weight:700;font-size:12px;">🎙 <span id="vt">00:00</span></div>
                <div style="display:flex;gap:6px;">
                    <button id="vc" style="background:none;border:none;color:#999;cursor:pointer;font-size:11px;font-family:inherit;">${t.cancel}</button>
                    <button id="vs" style="background:#ef4444;color:#fff;border:none;padding:4px 14px;border-radius:8px;cursor:pointer;font-weight:700;font-size:11px;font-family:inherit;">${t.send}</button>
                </div>
            </div>
            <input type="file" id="fi" style="display:none;">
        </div>`;
        }
    };

    // ============ NAVIGATE ============
    function go(view) {
        state.view = view;
        const titles = { welcome: t.welcome, conversations: t.conversations, faqs: t.faqs, news: t.news, chat: t.liveSupport, prechat: t.formTitle };
        $('#n8n-title').text(titles[view] || '');
        $('#n8n-body').html(V[view]());
        $('.ntab').each(function () {
            const v = $(this).data('v');
            const on = (v === view) || (view === 'chat' && v === 'conversations') || (view === 'prechat' && v === 'conversations');
            $(this).css('color', on ? C.primary : '#8d94b5');
            $(this).find('.tw').css('background', on ? '#edf0f5' : 'transparent');
        });
        if (view === 'welcome') {
            // "ارسال پیام به ما" → go to LAST session, not new
            $('#btn-start').click(() => {
                if (state.sessions.length > 0) {
                    // Go to last session
                    state.sessionId = state.sessions[state.sessions.length - 1];
                    state.lastMsgId = 0;
                    localStorage.setItem('n8n_chat_session_id', state.sessionId);
                    go('chat');
                } else {
                    // No sessions, create first one. Pass `false` so it shows Pre-chat form!
                    createNewSession(false);
                }
            });
        }
        if (view === 'conversations') {
            $('#btn-new').click(() => createNewSession(false));
            $('.cv').click(function () { state.sessionId = $(this).data('sid'); state.lastMsgId = 0; localStorage.setItem('n8n_chat_session_id', state.sessionId); go('chat'); });
        }
        if (view === 'prechat') {
            $('#pcf').submit(function (e) {
                e.preventDefault();
                let ok = true; $(this).find('[required]').each(function () { if (!$(this).val().trim()) ok = false; });
                if (!ok) { $('#pcf-err').show(); return; } $('#pcf-err').hide();
                const data = {}; $(this).find('input,textarea').each(function () { const k = $(this).attr('name'); if (k && k.startsWith('pcf_')) data[k.replace('pcf_', '')] = $(this).val().trim(); });
                
                state.isCreatingSession = true;
                state.sessionCreatedAt = Date.now(); // زمان ایجاد session را ثبت کن

                // ثبت session فوری در localStorage — قبل از پاسخ سرور
                if (!state.sessions.includes(state.sessionId)) {
                    state.sessions.push(state.sessionId);
                    localStorage.setItem('n8n_chat_sessions', JSON.stringify(state.sessions));
                }

                // رفتن فوری به چت بدون انتظار برای سرور
                go('chat');

                // ارسال اطلاعات session به سرور در پس‌زمینه
                $.post(n8nChat.ajax_url, { 
                    action: 'n8n_chat_start_session', 
                    nonce: n8nChat.nonce, 
                    session_id: state.sessionId, 
                    user_name: data.name || data['نام'] || wpUser.name || '', 
                    user_email: data.email || data['ایمیل'] || wpUser.email || '', 
                    user_phone: data.phone || data['تلفن'] || data['موبایل'] || '', 
                    user_data: JSON.stringify(data) 
                }).fail(function() {
                    // اگر سرور خطا داد session را از لیست حذف کن
                    const idx = state.sessions.indexOf(state.sessionId);
                    if (idx !== -1) { state.sessions.splice(idx, 1); localStorage.setItem('n8n_chat_sessions', JSON.stringify(state.sessions)); }
                    alert(isFa ? 'خطا در ارتباط با سرور. لطفاً دوباره تلاش کنید.' : 'Connection error. Please try again.');
                }).always(function() {
                    state.isCreatingSession = false;
                });
            });
        }
        if (view === 'chat') {
            $('#n8n-user-handoff')
                .css({ display: 'flex', opacity: 1, pointerEvents: 'auto', background: 'rgba(255,255,255,0.15)', borderColor: 'rgba(255,255,255,0.3)' })
                .text(S.handoff_button_text || 'انتقال به انسان');
            initChat(); loadHist(); 
        } else {
            $('#n8n-user-handoff').hide();
        }
    }

    function createNewSession(skipForm) {
        const fields = S.prechat_fields || [];
        // Reuse unattached tracking sessionId or generate a new one
        let newSid;
        if (state.sessionId && !state.sessions.includes(state.sessionId)) {
            newSid = state.sessionId;
        } else {
            newSid = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
        }
        state.sessionId = newSid; state.lastMsgId = 0;
        localStorage.setItem('n8n_chat_session_id', newSid);

        if (!skipForm && fields.length > 0) {
            go('prechat');
        } else {
            state.isCreatingSession = true;
            state.sessionCreatedAt = Date.now();
            // ثبت session فوری و رفتن بلافاصله به چت
            if (!state.sessions.includes(state.sessionId)) {
                state.sessions.push(state.sessionId);
                localStorage.setItem('n8n_chat_sessions', JSON.stringify(state.sessions));
            }
            go('chat');
            $.post(n8nChat.ajax_url, { action: 'n8n_chat_start_session', nonce: n8nChat.nonce, session_id: newSid, user_name: wpUser.name || '', user_email: wpUser.email || '', user_phone: '', user_data: '{}' }).always(function() { state.isCreatingSession = false; });
        }
    }

    // ============ TOGGLE ============
    let proTimer;
    const $tog = $('#n8n-toggle'), $togWrap = $('#n8n-toggle-wrap'), $win = $('#n8n-win');
    $tog.click(() => {
        state.isOpen = !state.isOpen;
        if (state.isOpen) {
            clearTimeout(proTimer);
            $('#n8n-proactive-wrap, #n8n-halos, #n8n-pro-ring').fadeOut(200);
            localStorage.setItem('n8n_proactive_seen', Date.now().toString());
            
            // Open: Hide button+badge wrapper, show window
            $togWrap.css({ opacity: 0, pointerEvents: 'none' });
            const bBottom = isMobile ? btnBottom : (S.btn_bottom_desktop || 20);
            $win.css({ display: 'flex', opacity: 1, transform: 'scale(1)', bottom: bBottom + 'px' });
            $('#ico-o').hide(); $('#ico-c').show();
            go(state.view);
        } else {
            // Close: Show button+badge wrapper, hide window
            $win.css({ opacity: 0, transform: 'scale(0.95)' });
            setTimeout(() => { if (!state.isOpen) $win.hide(); }, 300);
            $('#ico-o').show(); $('#ico-c').hide();
            $togWrap.css({ opacity: 1, pointerEvents: 'auto' });
        }
    });
    $tog.hover(function () { $(this).css('transform', 'scale(1.1)'); }, function () { $(this).css('transform', 'scale(1)'); });
    $('.ntab').click(function () { go($(this).data('v')); });
    $('#n8n-min').click(() => $tog.click());
    $('#n8n-x').click(() => $tog.click());

    // ============ PROACTIVE CHAT ============
    const PROACTIVE_COOLDOWN_MS = (parseInt(S.proactive_cooldown, 10) || 6) * 60 * 60 * 1000;
    function isProactiveCooledDown() {
        const last = parseInt(localStorage.getItem('n8n_proactive_seen') || '0', 10);
        return (Date.now() - last) > PROACTIVE_COOLDOWN_MS;
    }
    if (S.proactive_enabled === '1' && isProactiveCooledDown() && !state.isOpen && S.proactive_text) {
        proTimer = setTimeout(() => {
            if (!state.isOpen && isProactiveCooledDown()) {
                let txt = S.proactive_text.replace('{page_title}', document.title);
                $('#n8n-pro-text').text(txt);
                $('#n8n-halos').fadeIn(300);
                $('#n8n-pro-ring').fadeIn(300);
                $('#n8n-proactive-wrap').css('display', 'block').hide().fadeIn(300);
            }
        }, (isNaN(S.proactive_delay) || S.proactive_delay < 0 ? 5 : S.proactive_delay) * 1000);
    }
    $('.n8n-proactive-close').click((e) => {
        e.stopPropagation();
        $('#n8n-proactive-wrap, #n8n-halos, #n8n-pro-ring').fadeOut(200);
        localStorage.setItem('n8n_proactive_seen', Date.now().toString());
    });
    $('.n8n-proactive-close').hover(function() { $(this).css({opacity:1,color:'#ef4444'}); }, function() { $(this).css({opacity:0.5,color: S.color_proactive_text || C.primary}); });
    $('#n8n-proactive').click(() => {
        $tog.click();
    });

    // ============ CHAT ============
    function initChat() {
        const inp = $('#ci');
        inp.on('input', function () { this.style.height = 'auto'; this.style.height = Math.min(this.scrollHeight, 60) + 'px'; if (!this.value) this.style.height = '28px'; });
        $('#bs').click(doSend);
        inp.keydown(e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSend(); } });

        // Handoff user click
        $('body').off('click', '#n8n-user-handoff').on('click', '#n8n-user-handoff', function(e) {
            e.preventDefault();
            if (!state.sessionId) return;
            const btn = $(this);
            btn.text('⏳').css({opacity: 0.7, pointerEvents: 'none'});
            $.post(n8nChat.ajax_url, {
                action: 'n8n_chat_user_handoff',
                nonce: n8nChat.nonce,
                session_id: state.sessionId
            }, function(r) {
                btn.text(S.handoff_success_text || '✅ وصل شد').css({background: 'rgba(255,255,255,0.15)', borderColor: 'rgba(255,255,255,0.3)', opacity: 1, pointerEvents: 'none'});
            });
        });

        $('#ba').click(() => $('#fi').click());
        $('#fi').change(function () { if (this.files[0]) uploadFile(this.files[0], 'file'); this.value = ''; });
        $('#bm').click(startVoice); $('#vc').click(cancelVoice); $('#vs').click(sendVoice);

        // Emoji
        $('#be').click(function (e) { e.preventDefault(); e.stopPropagation(); const $p = $('#bep'); $p.css('display', $p.css('display') === 'none' ? 'flex' : 'none'); });
        $(document).click(function (e) { if (!$(e.target).closest('#be, #bep').length) $('#bep').hide(); });
        $('.emoji-it').click(function (e) {
            e.preventDefault(); e.stopPropagation();
            const em = $(this).text();
            const input = inp[0];
            const start = input.selectionStart, end = input.selectionEnd, text = input.value;
            input.value = text.substring(0, start) + em + text.substring(end);
            input.selectionStart = input.selectionEnd = start + em.length;
            input.focus();
            inp.trigger('input');
        });
    }
    function doSend() {
        const txt = $('#ci').val().trim(); if (!txt) return;
        $('#ci').val('').css('height', '28px');
        $('#n8n-quick-replies, #n8n-quick-flow').fadeOut(300, function() { $(this).remove(); });
        if (state.flowContext && state.flowContext.length > 0) {
            finishFlow(txt);
            return;
        }
        const tempId = 'tmp' + Date.now();
        addMsg({ id: tempId, role: 'user', message: txt, time: 'now', is_read: 0 });
        $.post(n8nChat.ajax_url, { action: 'n8n_chat_send', nonce: n8nChat.nonce, session_id: state.sessionId, message: txt }, function (r) {
            if (r.success && r.data && r.data.id) {
                $('#m-' + tempId).attr('id', 'm-' + r.data.id);
                $('#t-' + tempId).attr('id', 't-' + r.data.id);
                if (parseInt(r.data.id) > state.lastMsgId) state.lastMsgId = parseInt(r.data.id);
            }
        });
    }
    function addMsg(m, anim) {
        if ($('#m-' + m.id).length) return;

        if (m.role === 'user' && !isNaN(parseInt(m.id))) {
            let upgraded = false;
            $('#cm > div[id^="m-tmp"]').each(function() {
                if ($(this).data('raw-txt') === m.message) {
                    $(this).attr('id', 'm-' + m.id);
                    $(this).find('[id^="t-tmp"]').attr('id', 't-' + m.id);
                    $(this).removeData('raw-txt');
                    upgraded = true;
                    return false;
                }
            });
            if (upgraded) {
                const numId = parseInt(m.id);
                if (numId > state.lastMsgId) state.lastMsgId = numId;
                return;
            }
        }
        const me = m.role === 'user';
        const bs = me ? `background:${C.primary};color:#fff;border-radius:14px 14px 2px 14px;` : `background:var(--n8n-surface);color:var(--n8n-fg);border-radius:14px 14px 14px 2px;border:1px solid #f0f0f0;`;
        const cls = me ? 'n8n-msg-me' : 'n8n-msg-other';
        // Avatar logic
        const userAvUrl = S.user_avatar_url || '';
        const aiAvUrl = S.ai_avatar_url || '';
        const adminAvUrl = S.admin_avatar_url || '';
        
        let avUrl = '';
        let avEmoji = '👤';
        if (m.role === 'user') { avUrl = userAvUrl; avEmoji = '👤'; }
        else if (m.role === 'ai') { avUrl = aiAvUrl; avEmoji = '🤖'; }
        else { avUrl = adminAvUrl; avEmoji = '👨‍💼'; } // admin/human

        const avHtml = avUrl
            ? `<img src="${avUrl}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;flex-shrink:0;" />`
            : `<div style="width:40px;height:40px;border-radius:50%;background:${me ? C.primary : '#e2e8f0'};display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;">${avEmoji}</div>`;
        const rowDir = me ? 'flex-direction:row;' : 'flex-direction:row-reverse;';
        
        // Handle explicit sender name (Admin/Telegram)
        let senderLabel = '';
        if (!me && m.sender_name) {
            let sName = m.sender_name;
            if (sName.includes('|')) sName = sName.split('|')[0];
            if (sName) {
                senderLabel = `<div style="font-size:10px;font-weight:700;color:${C.primary};margin-bottom:4px;opacity:0.9;">${sName}</div>`;
            }
        }

        const $el = $(`<div id="m-${m.id}" class="${cls}" style="width:100%;display:flex;align-items:flex-end;gap:8px;${rowDir}margin-bottom:8px;animation:n8nUp .25s ease;box-sizing:border-box;">
            ${avHtml}
            <div class="${me ? (isFa ? 'n8n-bubble-me-fa n8n-bubble-me' : 'n8n-bubble-me') : (isFa ? 'n8n-bubble-other-fa n8n-bubble-other' : 'n8n-bubble-other')}" style="padding:10px 14px;font-size:13px;line-height:1.6;min-width:60px;max-width:calc(100% - 56px);text-align:${isFa ? 'right' : 'left'};word-break:break-word;">
                ${senderLabel}
                ${fmtC(m.message)}
                <div style="font-size:8px;opacity:0.45;text-align:${isFa ? 'left' : 'right'};margin-top:3px;">${m.time}${me ? `<span id="t-${m.id}">` + (m.is_read == 1 ? ' ✓✓' : ' ✓') + `</span>` : ''}</div>
            </div>
        </div>`);
        if (me) $el.data('raw-txt', m.message);
        $('#cm').append($el);
        const numId = parseInt(m.id);
        if (!isNaN(numId) && numId > state.lastMsgId) state.lastMsgId = numId;
        if (anim !== false) { const b = $('#cm'); if (b.length) b.scrollTop(b[0].scrollHeight); }
    }

    function fmtC(txt) {
        if (!txt) return ''; let c = txt; const ph = [];
        c = c.replace(/\[Voice Message\]\((.*?)\)/g, (m, u) => { const i = ph.length; ph.push(`<audio controls preload="metadata" src="${u}" style="width:160px;height:24px;margin-top:3px;"></audio>`); return `%%P${i}%%`; });
        c = c.replace(/\[Attachment: (.*?)\]\((.*?)\)/g, (m, n, u) => { const i = ph.length; ph.push(`<a href="${u}" target="_blank" style="color:inherit;text-decoration:underline;">📎 ${n}</a>`); return `%%P${i}%%`; });
        c = c.replace(/\n/g, '<br>'); for (let i = 0; i < ph.length; i++)c = c.replace(`%%P${i}%%`, ph[i]); return c;
    }
    let handoffTimer;
    function updateHandoffBtn(handoffTime) {
        if (handoffTime === undefined) return;
        clearInterval(handoffTimer);
        const updateTick = () => {
            const nowSec = Math.floor(Date.now() / 1000);
            if (handoffTime > nowSec) {
                const diff = handoffTime - nowSec;
                const m = Math.floor(diff / 60); const s = diff % 60;
                const timeStr = String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
                const txt = (S.handoff_success_text || '✅ وصل شد') + ' (' + timeStr + ')';
                $('#n8n-user-handoff').text(txt).css({background: 'rgba(255,255,255,0.15)', borderColor: 'rgba(255,255,255,0.3)', opacity: 1, pointerEvents: 'none'});
            } else {
                clearInterval(handoffTimer);
                $('#n8n-user-handoff').text(S.handoff_button_text || 'انتقال به انسان').css({background: 'rgba(255,255,255,0.15)', borderColor: 'rgba(255,255,255,0.3)', opacity: 1, pointerEvents: 'auto'});
            }
        };
        updateTick();
        if (handoffTime > Math.floor(Date.now() / 1000)) handoffTimer = setInterval(updateTick, 1000);
    }

    function loadHist() {
        if (state.isCreatingSession) {
            $('#cm').empty();
            if (S.welcome_message) {
                addMsg({ id: 'welcome', role: 'ai', message: S.welcome_message, time: '', is_read: 1 }, false);
            }
            const qf = S.quick_flow;
            const qr = S.quick_replies || [];
            if (qf && Array.isArray(qf) && qf.length > 0) {
                showQuickFlow(qf);
            } else if (qr.length > 0) {
                showQuickReplies(qr);
            }
            return;
        }

        $.post(n8nChat.ajax_url, { action: 'n8n_chat_history', nonce: n8nChat.nonce, session_id: state.sessionId }, r => {
            if (r.success) {
                $('#cm').empty();
                const msgs = r.data.messages || (Array.isArray(r.data) ? r.data : []);
                if (msgs.length) {
                    msgs.forEach(m => addMsg(m, false));
                } else {
                    // چت خالی است — فقط پیام خوش‌آمدگویی نمایش بده
                    if (S.welcome_message) {
                        addMsg({ id: 'welcome', role: 'ai', message: S.welcome_message, time: '', is_read: 1 }, false);
                    }
                }
                const b = $('#cm'); if (b.length) b.scrollTop(b[0].scrollHeight);
                updateHandoffBtn(r.data.handoff_until);

                // Show quick flow only if no real user message exists yet
                const hasUserMsg = msgs.some(m => m.role === 'user');
                const qf = S.quick_flow;
                const qr = S.quick_replies || [];
                if (!hasUserMsg) {
                    if (qf && Array.isArray(qf) && qf.length > 0) {
                        showQuickFlow(qf);
                    } else if (qr.length > 0) {
                        showQuickReplies(qr);
                    }
                }
            }
        });
    }
    function showQuickFlow(nodes) {
        $('#n8n-quick-replies, #n8n-quick-flow').remove();
        if (!nodes || nodes.length === 0) return;
        
        let btns = '';
        nodes.forEach((node, i) => {
            const spanStyle = (nodes.length % 2 !== 0 && i === nodes.length - 1) ? 'grid-column: 1 / -1;' : '';
            const nodeJson = JSON.stringify(node).replace(/'/g, "&#39;").replace(/"/g, "&quot;");
            btns += `<button class="n8n-qf-btn" data-node="${nodeJson}" style="display:flex;align-items:center;justify-content:center;width:100%;padding:10px 14px;border-radius:10px;border:1.5px solid ${C.primary}22;background:linear-gradient(135deg, ${C.primary}08, ${C.primary}03);color:${C.primary};font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .25s ease;direction:rtl;opacity:0;transform:translateY(8px);animation:n8nQrIn .35s ease ${i * 0.08}s forwards;${spanStyle}"><span style="text-align:center;line-height:1.4;">${node.text}</span></button>`;
        });
        const container = $(`<div id="n8n-quick-flow" style="padding:10px 14px;display:grid;grid-template-columns:repeat(2, 1fr);gap:6px;"><style>
        :root {
            --n8n-bg: #EEEEEE;
            --n8n-fg: #101010;
            --n8n-accent: ${C.primary};
            --n8n-surface: #FFFFFF;
            --n8n-surface-alt: #F8F8F8;
            --n8n-border: rgba(0,0,0,0.08);
            --n8n-muted: #666666;
            --n8n-shadow: 0 12px 48px rgba(0,0,0,0.15);
            --n8n-shadow-sm: 0 4px 16px rgba(0,0,0,0.08);
            --n8n-radius: 20px;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --n8n-bg: #101010;
                --n8n-fg: #CCCCCC;
                --n8n-surface: #1E1E1E;
                --n8n-surface-alt: #282828;
                --n8n-border: rgba(255,255,255,0.08);
                --n8n-muted: #999999;
                --n8n-shadow: 0 12px 48px rgba(0,0,0,0.4);
                --n8n-shadow-sm: 0 4px 16px rgba(0,0,0,0.3);
            }
        }
        
        #n8n-win { background: var(--n8n-bg) !important; box-shadow: var(--n8n-shadow) !important; border-radius: var(--n8n-radius) !important; border: 1px solid var(--n8n-border) !important; }
        .n8n-surface { background: var(--n8n-surface) !important; border: 1px solid var(--n8n-border) !important; box-shadow: var(--n8n-shadow-sm) !important; color: var(--n8n-fg) !important; }
        .n8n-text { color: var(--n8n-fg) !important; }
        .n8n-muted { color: var(--n8n-muted) !important; }
        .n8n-input { background: var(--n8n-surface) !important; color: var(--n8n-fg) !important; border: 1px solid var(--n8n-border) !important; }
        .n8n-input:focus { border-color: var(--n8n-accent) !important; }
        .n8n-bubble-me { background: var(--n8n-accent) !important; color: #fff !important; border-radius: 18px 18px 4px 18px !important; box-shadow: 0 4px 12px rgba(0,122,204,0.3) !important; }
        .n8n-bubble-me-fa { border-radius: 18px 18px 18px 4px !important; }
        .n8n-bubble-other { background: var(--n8n-surface) !important; color: var(--n8n-fg) !important; border: 1px solid var(--n8n-border) !important; border-radius: 18px 18px 18px 4px !important; box-shadow: var(--n8n-shadow-sm) !important; }
        .n8n-bubble-other-fa { border-radius: 18px 18px 4px 18px !important; }
@keyframes n8nQrIn{to{opacity:1;transform:translateY(0);}}</style>${btns}</div>`);
        $('#cm').append(container);
        const b = $('#cm'); if (b.length) b.scrollTop(b[0].scrollHeight);

        // Hover effect
        container.on('mouseenter', '.n8n-qf-btn', function() {
            $(this).css({ background: `linear-gradient(135deg, ${C.primary}, ${C.primary}dd)`, color: '#fff', borderColor: C.primary, transform: 'translateY(-1px)', boxShadow: `0 4px 12px ${C.primary}30` });
        }).on('mouseleave', '.n8n-qf-btn', function() {
            $(this).css({ background: `linear-gradient(135deg, ${C.primary}08, ${C.primary}03)`, color: C.primary, borderColor: `${C.primary}22`, transform: 'translateY(0)', boxShadow: 'none' });
        });

        // Click handler
        container.on('click', '.n8n-qf-btn', function() {
            const node = JSON.parse($(this).attr('data-node').replace(/&quot;/g, '"').replace(/&#39;/g, "'"));
            $(this).css({ background: C.primary, color: '#fff', transform: 'scale(0.97)' });
            
            setTimeout(() => {
                $('#n8n-quick-flow').fadeOut(300, function() { $(this).remove(); });
            }, 150);

            // Add user message to UI and context
            const userMsgId = 'tmp_flow_' + Date.now();
            addMsg({ id: userMsgId, role: 'user', message: node.text, time: 'now', is_read: 1 });
            state.flowContext.push({ role: 'user', message: node.text, tmp_id: userMsgId });

            if (node.actionType === 'menu') {
                // Show children
                setTimeout(() => {
                    showQuickFlow(node.children);
                }, 400);
            } else {
                // It's a reply
                const aiMsgId = 'tmp_flow_ai_' + Date.now();
                setTimeout(() => {
                    addMsg({ id: aiMsgId, role: 'ai', message: node.replyText, time: 'now', is_read: 1 });
                    state.flowContext.push({ role: 'ai', message: node.replyText, tmp_id: aiMsgId });
                    
                    // Finish flow, send context to backend
                    finishFlow('');
                }, 500);
            }
        });
    }

    function finishFlow(finalMsgText) {
        if (!state.sessionId) return;
        
        const localCtx = [...state.flowContext];
        const ctx = JSON.stringify(localCtx);
        state.flowContext = []; // Clear immediately to prevent duplicate sends
        $('#n8n-quick-flow, #n8n-quick-replies').remove();

        let tempId = null;
        if (finalMsgText) {
            tempId = 'tmp' + Date.now();
            addMsg({ id: tempId, role: 'user', message: finalMsgText, time: 'now', is_read: 0 });
            localCtx.push({ role: 'user', message: finalMsgText, tmp_id: tempId });
        }

        $.post(n8nChat.ajax_url, {
            action: 'n8n_chat_flow_complete',
            nonce: n8nChat.nonce,
            session_id: state.sessionId,
            flow_context: ctx,
            final_msg: finalMsgText || ''
        }, function(r) {
            if (r.success && r.data) {
                const savedIds = r.data.saved_ids || [];
                let idIdx = 0;
                localCtx.forEach(entry => {
                    if (idIdx < savedIds.length && entry.tmp_id) {
                        const realId = savedIds[idIdx];
                        $('#m-' + entry.tmp_id).attr('id', 'm-' + realId);
                        $('#t-' + entry.tmp_id).attr('id', 't-' + realId);
                        if (parseInt(realId) > state.lastMsgId) state.lastMsgId = parseInt(realId);
                        idIdx++;
                    }
                });

                if (r.data.last_id && parseInt(r.data.last_id) > state.lastMsgId) {
                    state.lastMsgId = parseInt(r.data.last_id);
                }
            }
        });
    }
    function showQuickReplies(replies) {
        // Remove old QR container if exists
        $('#n8n-quick-replies').remove();
        let btns = '';
        replies.forEach((txt, i) => {
            const spanStyle = (replies.length % 2 !== 0 && i === replies.length - 1) ? 'grid-column: 1 / -1;' : '';
            btns += `<button class="n8n-qr-btn" style="display:flex;align-items:center;justify-content:center;width:100%;padding:10px 14px;border-radius:10px;border:1.5px solid ${C.primary}22;background:linear-gradient(135deg, ${C.primary}08, ${C.primary}03);color:${C.primary};font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .25s ease;direction:rtl;opacity:0;transform:translateY(8px);animation:n8nQrIn .35s ease ${i * 0.08}s forwards;${spanStyle}"><span style="text-align:center;line-height:1.4;">${txt}</span></button>`;
        });
        const container = $(`<div id="n8n-quick-replies" style="padding:10px 14px;display:grid;grid-template-columns:repeat(2, 1fr);gap:6px;"><style>
        :root {
            --n8n-bg: #EEEEEE;
            --n8n-fg: #101010;
            --n8n-accent: ${C.primary};
            --n8n-surface: #FFFFFF;
            --n8n-surface-alt: #F8F8F8;
            --n8n-border: rgba(0,0,0,0.08);
            --n8n-muted: #666666;
            --n8n-shadow: 0 12px 48px rgba(0,0,0,0.15);
            --n8n-shadow-sm: 0 4px 16px rgba(0,0,0,0.08);
            --n8n-radius: 20px;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --n8n-bg: #101010;
                --n8n-fg: #CCCCCC;
                --n8n-surface: #1E1E1E;
                --n8n-surface-alt: #282828;
                --n8n-border: rgba(255,255,255,0.08);
                --n8n-muted: #999999;
                --n8n-shadow: 0 12px 48px rgba(0,0,0,0.4);
                --n8n-shadow-sm: 0 4px 16px rgba(0,0,0,0.3);
            }
        }
        
        #n8n-win { background: var(--n8n-bg) !important; box-shadow: var(--n8n-shadow) !important; border-radius: var(--n8n-radius) !important; border: 1px solid var(--n8n-border) !important; }
        .n8n-surface { background: var(--n8n-surface) !important; border: 1px solid var(--n8n-border) !important; box-shadow: var(--n8n-shadow-sm) !important; color: var(--n8n-fg) !important; }
        .n8n-text { color: var(--n8n-fg) !important; }
        .n8n-muted { color: var(--n8n-muted) !important; }
        .n8n-input { background: var(--n8n-surface) !important; color: var(--n8n-fg) !important; border: 1px solid var(--n8n-border) !important; }
        .n8n-input:focus { border-color: var(--n8n-accent) !important; }
        .n8n-bubble-me { background: var(--n8n-accent) !important; color: #fff !important; border-radius: 18px 18px 4px 18px !important; box-shadow: 0 4px 12px rgba(0,122,204,0.3) !important; }
        .n8n-bubble-me-fa { border-radius: 18px 18px 18px 4px !important; }
        .n8n-bubble-other { background: var(--n8n-surface) !important; color: var(--n8n-fg) !important; border: 1px solid var(--n8n-border) !important; border-radius: 18px 18px 18px 4px !important; box-shadow: var(--n8n-shadow-sm) !important; }
        .n8n-bubble-other-fa { border-radius: 18px 18px 4px 18px !important; }
@keyframes n8nQrIn{to{opacity:1;transform:translateY(0);}}</style>${btns}</div>`);
        $('#cm').append(container);
        const b = $('#cm'); if (b.length) b.scrollTop(b[0].scrollHeight);

        // Hover effect
        container.on('mouseenter', '.n8n-qr-btn', function() {
            $(this).css({ background: `linear-gradient(135deg, ${C.primary}, ${C.primary}dd)`, color: '#fff', borderColor: C.primary, transform: 'translateY(-1px)', boxShadow: `0 4px 12px ${C.primary}30` });
        }).on('mouseleave', '.n8n-qr-btn', function() {
            $(this).css({ background: `linear-gradient(135deg, ${C.primary}08, ${C.primary}03)`, color: C.primary, borderColor: `${C.primary}22`, transform: 'translateY(0)', boxShadow: 'none' });
        });

        // Click: send as user message
        container.on('click', '.n8n-qr-btn', function() {
            const txt = $(this).find('span:first').text();
            $(this).css({ background: C.primary, color: '#fff', transform: 'scale(0.97)' });
            setTimeout(() => {
                $('#n8n-quick-replies').fadeOut(300, function() { $(this).remove(); });
            }, 150);
            $('#ci').val(txt);
            doSend();
        });
    }

    // VOICE
    async function startVoice() {
        try {
            const s = await navigator.mediaDevices.getUserMedia({ audio: true }); state.mediaRecorder = new MediaRecorder(s); state.audioChunks = [];
            state.mediaRecorder.ondataavailable = e => { if (e.data.size > 0) state.audioChunks.push(e.data); };
            state.mediaRecorder.start(1000); $('#vbar').css('display', 'flex'); state.voiceStart = Date.now();
            state.voiceTimer = setInterval(() => { const d = Math.floor((Date.now() - state.voiceStart) / 1000); $('#vt').text(String(Math.floor(d / 60)).padStart(2, '0') + ':' + String(d % 60).padStart(2, '0')); }, 1000);
        } catch (e) { alert(isFa ? 'دسترسی میکروفون رد شد' : 'Mic denied'); }
    }
    function cancelVoice() { if (state.mediaRecorder) { state.mediaRecorder.stream.getTracks().forEach(t => t.stop()); state.mediaRecorder.stop(); } clearInterval(state.voiceTimer); $('#vbar').hide(); }
    function sendVoice() { if (state.mediaRecorder) { state.mediaRecorder.onstop = () => { state.mediaRecorder.stream.getTracks().forEach(t => t.stop()); const b = new Blob(state.audioChunks, { type: 'audio/webm' }); if (b.size > 500) uploadFile(new File([b], 'voice_' + Date.now() + '.webm', { type: 'audio/webm' }), 'voice'); }; state.mediaRecorder.stop(); } clearInterval(state.voiceTimer); $('#vbar').hide(); }
    function uploadFile(file, type) {
        const fd = new FormData(); fd.append('action', 'n8n_chat_upload'); fd.append('nonce', n8nChat.nonce); fd.append('file', file); $.ajax({ url: n8nChat.ajax_url, type: 'POST', data: fd, contentType: false, processData: false, success: r => { if (r.success) { const txt = type === 'voice' ? `[Voice Message](${r.data.url})` : `[Attachment: ${r.data.name}](${r.data.url})`; $.post(n8nChat.ajax_url, { action: 'n8n_chat_send', nonce: n8nChat.nonce, session_id: state.sessionId, message: txt }); } } });
    }

    // POLLING
    setInterval(() => {
        if (!state.isOpen || state.view !== 'chat' || !state.sessionId) return;
        $.post(n8nChat.ajax_url, { action: 'n8n_chat_poll', nonce: n8nChat.nonce, session_id: state.sessionId, last_id: state.lastMsgId, _t: Date.now() }, r => {
            if (r.success) {
                const msgs = r.data.messages || (Array.isArray(r.data) ? r.data : []);
                if (msgs.length) {
                    let hasNew = false;
                    msgs.forEach(m => {
                        if (m.role !== 'user' && $('#m-' + m.id).length === 0) {
                            hasNew = true;
                        }
                        addMsg(m);
                    });
                    if (hasNew) playNotifSound();
                }
                const upds = r.data.updates || [];
                if (upds.length) upds.forEach(u => {
                    if (u.is_read == 1) $('#t-' + u.id).text(' ✓✓');
                });
                if (r.data.handoff_until !== undefined) {
                    updateHandoffBtn(r.data.handoff_until);
                }
            }
        });
    }, 4000);

    // BACKGROUND POLLING - check ALL sessions for unread counts
    setInterval(() => {
        let checkSids = [...state.sessions];
        if (state.sessionId && !checkSids.includes(state.sessionId)) checkSids.push(state.sessionId);

        if (!checkSids.length) return;
        if (state.sessions.length > 0) validateLocalSessions();

        $.post(n8nChat.ajax_url, { action: 'n8n_chat_unread_counts', nonce: n8nChat.nonce, session_ids: checkSids }, r => {
            if (!r.success) return;
            state.unreadSessions = r.data;
            let totalUnread = 0;

            let newlyPromoted = false;
            // Auto-promote tracking session to real session if admin sent a message
            if (state.sessionId && !state.sessions.includes(state.sessionId) && (r.data[state.sessionId] || 0) > 0) {
                state.sessions.push(state.sessionId);
                localStorage.setItem('n8n_chat_sessions', JSON.stringify(state.sessions));
                newlyPromoted = true;
            }

            Object.values(r.data).forEach(c => { totalUnread += c; });

            if (totalUnread > 0) {
                if (!state.isOpen) $('#n8n-badge').show();
                if (state.prevTotalUnread >= 0 && totalUnread > state.prevTotalUnread) {
                    if (!state.isOpen || state.view !== 'chat' || newlyPromoted) playNotifSound();
                }
            } else {
                $('#n8n-badge').hide();
            }
            state.prevTotalUnread = totalUnread;

            // Re-render conversations or auto-open chat if promoted
            if (newlyPromoted && state.isOpen) {
                go('chat');
            } else if (state.isOpen && state.view === 'conversations') {
                go('conversations');
            }
        });
    }, 6000);

    // VALIDATE SESSION INTEGRITY
    // آیا session اخیراً ایجاد شده و باید از حذف محافظت شود؟ (۳۰ ثانیه grace period)
    function isSessionFresh() {
        return state.sessionCreatedAt > 0 && (Date.now() - state.sessionCreatedAt) < 30000;
    }

    function validateLocalSessions() {
        if (!state.sessions.length) return;
        
        // هرگز در این حالت‌ها validate نکن
        if (state.isCreatingSession) {
            return;
        }
        if (state.view === 'prechat') {
            return;
        }
        if (isSessionFresh()) {
            return; 
        }

        $.post(n8nChat.ajax_url, {
            action: 'n8n_chat_validate_sessions',
            nonce: n8nChat.nonce,
            session_ids: state.sessions
        }, function (res) {
            if (!res.success) {
                return;
            }
            
            // guard های async
            if (state.isCreatingSession) {
                return;
            }
            if (state.view === 'prechat') {
                return;
            }
            if (isSessionFresh()) {
                return;
            }

            const valid = res.data || [];
            const oldLen = state.sessions.length;

            // فقط session هایی که واقعاً در DB نیستند حذف کن
            state.sessions = state.sessions.filter(sid => valid.includes(sid));

            // اگر session فعلی هم invalid است
            if (state.sessionId && !valid.includes(state.sessionId)) {
                
                if (state.sessions.length > 0) {
                    state.sessionId = state.sessions[state.sessions.length - 1];
                    localStorage.setItem('n8n_chat_session_id', state.sessionId);
                } else {
                    // هیچ session معتبری نمانده — tracking ID جدید
                    state.sessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
                    localStorage.setItem('n8n_chat_session_id', state.sessionId);
                    sendHeartbeat();
                }
                
                // فقط اگر در view چت هستیم redirect بزن
                if (state.view === 'chat') {
                    state.lastMsgId = 0;
                    $('#cm').empty();
                    go('welcome');
                }
            }

            if (state.sessions.length !== oldLen) {
                localStorage.setItem('n8n_chat_sessions', JSON.stringify(state.sessions));
                if (state.isOpen && state.view === 'conversations') go('conversations');
            }
        });
    }
});
