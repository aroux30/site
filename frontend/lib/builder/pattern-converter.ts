import type { BuilderElement } from "@/types/builder";

/**
 * Generates a unique element ID with an optional prefix.
 */
export function generateElementId(prefix = "el"): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Helpers for constructing typed AST elements.
 */
function createContainerNode(
  name: string,
  options: {
    layout?: Partial<BuilderElement["layout"]>;
    customCssClass?: string;
    children?: BuilderElement[];
  } = {}
): BuilderElement {
  const defaultLayout: BuilderElement["layout"] = {
    kind: "flex",
    direction: "column",
    justifyContent: "start",
    alignItems: "stretch",
    flexWrap: "nowrap",
    gap: { value: 16, unit: "px" },
    gridColumns: 1,
  };
  return {
    id: generateElementId("cont"),
    name,
    type: "container",
    isLocked: false,
    isHidden: false,
    layout: options.layout ? { ...defaultLayout, ...options.layout } as BuilderElement["layout"] : defaultLayout,
    styles: {
      mobile: {},
      customCssClass: options.customCssClass || undefined,
    },
    children: options.children || [],
  };
}

function createHeadingWidget(
  text: string,
  tag: "h1" | "h2" | "h3" | "h4" | "h5" | "h6" = "h2",
  customCssClass?: string
): BuilderElement {
  return {
    id: generateElementId("head"),
    name: `عنوان: ${text.slice(0, 20)}`,
    type: "widget",
    widgetType: "heading",
    widgetProps: { text, tag, customCssClass: customCssClass || undefined },
    isLocked: false,
    isHidden: false,
    styles: {
      mobile: {},
      customCssClass: customCssClass || undefined,
    },
    children: [],
  };
}

function createTextWidget(content: string, customCssClass?: string): BuilderElement {
  let derivedClass = customCssClass || "";

  // Extract class names if not explicitly provided
  if (!customCssClass) {
    const classMatches = content.matchAll(/class="([^"]*)"/gi);
    const classes: string[] = [];
    for (const m of classMatches) {
      if (m[1]) classes.push(m[1]);
    }
    if (classes.length > 0) derivedClass = classes.join(" ");
  }

  // Strip all HTML tags to produce pure clean text for inline editing and clean inspector input
  const cleanText = content.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();

  return {
    id: generateElementId("text"),
    name: "متن و پاراگراف",
    type: "widget",
    widgetType: "text_editor",
    widgetProps: { content: cleanText, customCssClass: derivedClass.trim() || undefined },
    isLocked: false,
    isHidden: false,
    styles: {
      mobile: {},
      customCssClass: derivedClass.trim() || undefined,
    },
    children: [],
  };
}

function createButtonWidget(
  label: string,
  url = "#",
  customCssClass?: string,
  newTab = false
): BuilderElement {
  return {
    id: generateElementId("btn"),
    name: `دکمه: ${label}`,
    type: "widget",
    widgetType: "button",
    widgetProps: { label, url, newTab, customCssClass: customCssClass || undefined },
    isLocked: false,
    isHidden: false,
    styles: {
      mobile: {},
      customCssClass: customCssClass || undefined,
    },
    children: [],
  };
}

function createImageWidget(
  url: string,
  alt = "تصویر شاخص",
  customCssClass?: string
): BuilderElement {
  return {
    id: generateElementId("img"),
    name: `تصویر: ${alt.slice(0, 20)}`,
    type: "widget",
    widgetType: "image",
    widgetProps: { url, alt, customCssClass: customCssClass || undefined },
    isLocked: false,
    isHidden: false,
    styles: {
      mobile: {},
      customCssClass: customCssClass || undefined,
    },
    children: [],
  };
}

function createHtmlCustomWidget(
  html: string,
  name = "کد سفارشی",
  customCssClass?: string
): BuilderElement {
  return {
    id: generateElementId("html"),
    name,
    type: "widget",
    widgetType: "html_custom",
    widgetProps: { html },
    isLocked: false,
    isHidden: false,
    styles: {
      mobile: {},
      customCssClass: customCssClass || undefined,
    },
    children: [],
  };
}

function createTableWidget(
  headers: string[],
  rows: string[][],
  name = "جدول مشخصات",
  options: { bordered?: boolean; striped?: boolean; highlightCol?: number } = {}
): BuilderElement {
  return {
    id: generateElementId("tbl"),
    name,
    type: "widget",
    widgetType: "table",
    widgetProps: {
      headers,
      rows,
      bordered: options.bordered !== false,
      striped: options.striped !== false,
      highlightCol: options.highlightCol ?? null,
    },
    isLocked: false,
    isHidden: false,
    styles: { mobile: {} },
    children: [],
  };
}

function createFormInputWidget(
  label: string,
  name: string,
  placeholder = "",
  required = false,
  inputType = "text"
): BuilderElement {
  return {
    id: generateElementId("inp"),
    name: `فیلد: ${label}`,
    type: "widget",
    widgetType: "form_input",
    widgetProps: { label, name, placeholder, input_type: inputType, required },
    isLocked: false,
    isHidden: false,
    styles: { mobile: {} },
    children: [],
  };
}

/**
 * Built-in default values for the 28 standard block patterns.
 */
const PATTERN_DEFAULTS: Record<string, Record<string, string>> = {
  "hero-banner": {
    title: "کالکشن جدید رسید",
    subtitle: "جدیدترین محصولات فصل با تخفیف ویژه",
    image_url: "/placeholder-hero.svg",
    cta_text: "همین حالا بخرید",
    cta_url: "/products",
  },
  "feature-grid": {
    title: "چرا از ما بخرید؟",
    subtitle: "مزیت‌هایی که خرید را برای شما آسان می‌کنند",
    item1_title: "ارسال سریع",
    item1_text: "ارسال به سراسر کشور در کمترین زمان",
    item2_title: "ضمانت اصالت",
    item2_text: "تمام کالاها اصل و دارای گارانتی هستند",
    item3_title: "پرداخت امن",
    item3_text: "درگاه‌های بانکی معتبر و بازگشت وجه تضمین‌شده",
  },
  "product-showcase-cta": {
    title: "پیشنهاد ویژه این هفته",
    subtitle: "منتخبی از پرفروش‌ترین محصولات با قیمت استثنایی",
    image_url: "/placeholder-product.svg",
    cta_text: "مشاهده محصولات",
    cta_url: "/products",
  },
  testimonials: {
    title: "مشتریان ما چه می‌گویند",
    item1_text: "کیفیت محصولات عالی بود و ارسال سریع انجام شد.",
    item1_name: "سارا محمدی",
    item2_text: "پشتیبانی بسیار پاسخگو بود؛ حتماً دوباره خرید می‌کنم.",
    item2_name: "علی رضایی",
  },
  "faq-accordion": {
    title: "پرسش‌های متداول",
    q1: "چند روز به طول می‌انجامد تا سفارش ارسال شود؟",
    a1: "سفارش‌های تا ساعت ۱۴ روز کاری بعد ارسال می‌شوند.",
    q2: "آیا محصولات دارای ضمانت هستند؟",
    a2: "بله، تمامی محصولات با ضمانت اصالت و سلامت کالا ارسال می‌شوند.",
    q3: "چه روش‌های پرداختی پشتیبانی می‌شود؟",
    a3: "پرداخت آنلاین از طریق درگاه‌های بانکی و کارت به کارت.",
  },
  "image-text": {
    title: "داستان ما",
    body: "ما از سال ۱۳۹۰ با هدف ارائه کالاهای اصل و باکیفیت فعالیت می‌کنیم.",
    image_url: "/placeholder-about.svg",
    cta_text: "بیشتر بدانید",
    cta_url: "/about",
  },
  "countdown-offer": {
    title: "فروش ویژه پایان فصل",
    subtitle: "تا ۵۰٪ تخفیف روی هزاران کالا",
    ends_at: "شنبه ۲۳:۵۹",
    discount_code: "SEASON50",
    cta_text: "خرید با تخفیف",
    cta_url: "/products?discount=1",
  },
  "star-rating-display": {
    rating: "۴.۳",
    review_count: "۱۲۸",
  },
  "review-histogram": {
    average: "۴.۳",
    total: "۱۲۸",
    star5: "۶۱",
    star4: "۴۲",
    star3: "۱۵",
    star2: "۷",
    star1: "۳",
  },
  "product-card-grid": {
    title: "محصولات پرفروش",
    p1_name: "هدفون بلوتوثی",
    p1_price: "۱۸,۵۰۰,۰۰۰ تومان",
    p1_image: "/placeholder-product.svg",
    p1_url: "/products/product-1",
    p2_name: "ایرپاد پرو",
    p2_price: "۱۲,۹۰۰,۰۰۰ تومان",
    p2_image: "/placeholder-product.svg",
    p2_url: "/products/product-2",
    p3_name: "اسپیکر بلوتوثی",
    p3_price: "۸,۷۵۰,۰۰۰ تومان",
    p3_image: "/placeholder-product.svg",
    p3_url: "/products/product-3",
  },
  "text-marquee": {
    text1: "ارسال رایگان برای سفارش‌های بالای ۵۰۰ هزار تومان",
    text2: "ضمانت بازگشت ۷ روزه بدون قید و شرط",
    text3: "پرداخت امن با رمز دوم پویا",
    text4: "پشتیبانی ۲۴ ساعته",
  },
  "stats-counter": {
    stat1_value: "۱,۲۳۴",
    stat1_label: "محصول",
    stat2_value: "۵,۶۷۸",
    stat2_label: "سفارش",
    stat3_value: "۹۸٪",
    stat3_label: "رضایت مشتری",
    stat4_value: "۲۴",
    stat4_label: "ساعت پشتیبانی",
  },
  "image-gallery-showcase": {
    title: "گالری محصولات",
    img1: "/placeholder-product.svg",
    img2: "/placeholder-product.svg",
    img3: "/placeholder-product.svg",
    img4: "/placeholder-product.svg",
  },
  "discount-badge-banner": {
    percent: "۳۰",
    text: "تخفیف ویژه روی محصولات منتخب",
    cta_text: "مشاهده محصولات",
    cta_url: "/products",
  },
  "mega-menu-categories": {
    title: "دسته‌بندی محصولات",
    cat1_name: "لپ‌تاپ و کامپیوتر",
    cat1_url: "/category/laptop",
    cat2_name: "موبایل و تبلت",
    cat2_url: "/category/mobile",
    cat3_name: "هدفون و اسپیکر",
    cat3_url: "/category/audio",
    cat4_name: "لوازم جانبی",
    cat4_url: "/category/accessories",
  },
  "pricing-table": {
    title: "پلن‌های قیمت‌گذاری و تعرفه‌ها",
    subtitle: "پلن متناسب با کسب‌وکار خود را انتخاب کنید و رشد خود را شتاب دهید",
    plan1_name: "پایه",
    plan1_desc: "مناسب برای شروع و کسب‌وکارهای نوپا",
    plan1_price: "۲۹۰,۰۰۰ تومان",
    plan1_period: "/ ماهانه",
    plan1_f1: "دسترسی به امکانات پایه",
    plan1_f2: "پشتیبانی ایمیلی",
    plan1_f3: "۱ کاربر فعال",
    plan1_cta: "انتخاب پلن پایه",
    plan1_url: "/pricing?plan=basic",
    plan2_badge: "محبوب‌ترین",
    plan2_name: "حرفه‌ای",
    plan2_desc: "بهترین انتخاب برای تیم‌ها و شرکت‌های در حال توسعه",
    plan2_price: "۶۹۰,۰۰۰ تومان",
    plan2_period: "/ ماهانه",
    plan2_f1: "تمامی امکانات پلن پایه",
    plan2_f2: "پشتیبانی اولویت‌دار تیکت و تلفن",
    plan2_f3: "تا ۵ کاربر فعال همزمان",
    plan2_f4: "گزارش‌های پیشرفته و تحلیلی",
    plan2_cta: "شروع پلن حرفه‌ای",
    plan2_url: "/pricing?plan=pro",
    plan3_name: "ویژه",
    plan3_desc: "راهکار جامع برای سازمان‌ها و پروژه‌های با مقیاس بالا",
    plan3_price: "۱,۴۹۰,۰۰۰ تومان",
    plan3_period: "/ ماهانه",
    plan3_f1: "دسترسی نامحدود به تمامی قابلیت‌ها",
    plan3_f2: "پشتیبانی ۲۴ ساعته اختصاصی",
    plan3_f3: "کاربران نامحدود و مدیریت دسترسی",
    plan3_f4: "پشتیبان‌گیری ابری روزانه",
    plan3_cta: "ارتباط با کارشناسان",
    plan3_url: "/contact?plan=enterprise",
  },
  "price-list": {
    title: "لیست قیمت خدمات و محصولات",
    subtitle: "قیمت‌ها به تومان و شامل کلیه خدمات جانبی است",
    item1_title: "مشاوره تخصصی و تحلیل نیازسنجی",
    item1_desc: "جلسه آنلاین ۹۰ دقیقه‌ای به همراه ارائه سند راهبردی",
    item1_price: "۴۵۰,۰۰۰ تومان",
    item2_title: "نصب و پیکربندی اولیه نرم‌افزار",
    item2_desc: "راه‌اندازی کامل سیستم و آموزش کار با پنل مدیریت",
    item2_price: "۸۵۰,۰۰۰ تومان",
    item3_title: "پشتیبانی فنی و نگهداری ماهانه",
    item3_desc: "پایش مداوم، به‌روزرسانی امنیتی و پشتیبان‌گیری منظم",
    item3_price: "۱,۲۰۰,۰۰۰ تومان",
    item4_title: "توسعه و سفارشی‌سازی اختصاصی",
    item4_desc: "طراحی و پیاده‌سازی ویژگی‌های خاص متناسب با سفارش شما",
    item4_price: "۲,۵۰۰,۰۰۰ تومان",
    item5_title: "بسته آموزش و توانمندسازی پرسنل",
    item5_desc: "کارگاه آموزشی حضوری یا آنلاین با ارائه گواهی دوره",
    item5_price: "۱,۸۰۰,۰۰۰ تومان",
  },
  "icon-box-grid": {
    title: "چرا خدمات ما را انتخاب می‌کنند؟",
    subtitle: "ارائه برترین راهکارها با تمرکز بر کیفیت، سرعت و رضایت شما",
    box1_icon: "🚀",
    box1_title: "تحویل سریع و آنی",
    box1_desc: "کلیه سفارش‌ها در کوتاه‌ترین زمان پردازش و آماده ارسال یا تحویل می‌شوند.",
    box2_icon: "🛡️",
    box2_title: "تضمین اصالت و کیفیت",
    box2_desc: "تضمین صددرصدی اصالت تمامی کالاها همراه با گارانتی معتبر شرکتی.",
    box3_icon: "💳",
    box3_title: "پرداخت امن و مطمئن",
    box3_desc: "پشتیبانی از درگاه‌های بانکی عضو شاپرک و امنیت کامل تراکنش‌ها.",
    box4_icon: "🎧",
    box4_title: "پشتیبانی هفت‌روزه",
    box4_desc: "کارشناسان مجرب در تمام روزهای هفته آماده پاسخگویی به سوالات شما هستند.",
  },
  "author-bio": {
    name: "دکتر رضا کاظمی",
    role: "پژوهشگر ارشد و کارشناس تجربه کاربری",
    badge: "نویسنده برگزیده",
    avatar_url: "/placeholder-avatar.svg",
    bio: "بیش از یک دهه سابقه در تحلیل داده، طراحی تجربه کاربری و تولید محتوای تخصصی در کسب‌وکارهای مدرن فناوری.",
    contact_email: "reza.kazemi@example.com",
    cta_text: "ارسال پیام یا مشاوره",
    cta_url: "/contact?to=author",
  },
  "pull-quote": {
    quote_text: "سرمایه‌گذاری روی کیفیت و جلب رضایت مشتری، پایدارترین استراتژی برای تمایز و موفقیت در بازار رقابتی است.",
    author_name: "سهراب رحمانی",
    author_title: "مدیر ارشد محصول",
    source_note: "همایش سالانه نوآوری و تجارت دیجیتال",
  },
  "support-callout": {
    title: "نیاز به مشاوره قبل از خرید دارید؟",
    description: "کارشناسان فنی ما آماده پاسخگویی به تمامی سوالات شما و ارائه بهترین پیشنهاد متناسب با نیاز و بودجه‌تان هستند.",
    icon: "💬",
    badge_text: "پاسخگویی سریع",
    phone_label: "تماس مستقیم:",
    phone_number: "۰۲۱-۸۸۸۸۹۹۹۹",
    phone_url: "tel:02188889999",
    cta_text: "شروع گفتگوی آنلاین",
    cta_url: "/chat",
  },
  "comparison-table": {
    title: "مقایسه مشخصات و ویژگی‌های فنی",
    subtitle: "تفاوت مدل‌های مختلف را به دقت بررسی کرده و متناسب‌ترین گزینه را انتخاب کنید",
    col1_title: "ویژگی‌ها و قابلیت‌ها",
    col2_badge: "پیشنهاد ویژه",
    col2_name: "مدل پرو (Pro Edition)",
    col2_price: "۴,۸۵۰,۰۰۰ تومان",
    col2_cta: "خرید مدل پرو",
    col2_url: "/products",
    col3_name: "مدل استاندارد (Standard)",
    col3_price: "۲,۹۰۰,۰۰۰ تومان",
    col3_cta: "مشاهده و خرید",
    col3_url: "/products",
  },
  "process-steps": {
    title: "سفارش تا تحویل در ۴ مرحله آسان",
    subtitle: "تجربه خریدی لذت‌بخش، شفاف و بدون دغدغه از ثبت تا دریافت سفارش",
    s1_num: "۱",
    s1_title: "انتخاب هوشمند کالا",
    s1_desc: "بررسی نقد و مشخصات فنی کالاها و انتخاب بهترین گزینه",
    s2_num: "۲",
    s2_title: "پرداخت امن شتابی",
    s2_desc: "تسویه از طریق درگاه‌های امن شاپرک با کلیه کارت‌های بانکی",
    s3_num: "۳",
    s3_title: "بسته‌بندی ایمن و تست",
    s3_desc: "کنترل سلامت فیزیکی و آماده‌سازی در کارتن‌های ضربه‌گیر استاندارد",
    s4_num: "۴",
    s4_title: "تحویل اکسپرس درب منزل",
    s4_desc: "ارسال سریع با کد رهگیری پیامکی پستی تا زمان تحویل",
  },
  "lead-capture-form": {
    title: "درخواست مشاوره رایگان خرید",
    subtitle: "شماره همراه خود را وارد کنید تا کارشناسان فنی ما در کمتر از ۱۵ دقیقه با شما تماس بگیرند.",
    badge_text: "پاسخگویی در کمتر از ۱۵ دقیقه",
    button_text: "درخواست تماس رایگان کارشناس",
    privacy_note: "اطلاعات تماس شما نزد ما کاملاً محفوظ است و صرفاً جهت مشاوره استفاده می‌شود.",
  },
  "alert-banner": {
    icon: "📢",
    badge: "اطلاعیه مهم",
    title: "آغاز جشنواره شگفت‌انگیز پاییزه",
    description: "ارسال رایگان برای تمام سفارش‌های بالای ۵۰۰ هزار تومان و تخفیف ویژه تا ۴۰٪ روی اقلام منتخب تا پایان هفته فعال شد.",
    cta_text: "مشاهده تخفیف‌ها",
    cta_url: "/search?sale=true",
  },
  "floating-contact-bar": {
    heading: "راه‌های ارتباطی سریع با پشتیبانی",
    status_text: "پاسخگویی آنلاین کارشناسان",
    phone_label: "تلفن پشتیبانی",
    phone_num: "۰۲۱-۸۸۸۸۹۹۹۹",
    phone_url: "tel:02188889999",
    whatsapp_label: "واتساپ",
    whatsapp_url: "https://wa.me/989120000000",
    telegram_label: "تلگرام",
    telegram_url: "https://t.me/store_support",
    eitaa_label: "ایتا",
    eitaa_url: "https://eitaa.com/store_support",
  },
  "brand-logo-carousel": {
    title: "برندهای معتبر و شرکای تجاری رسمی",
    subtitle: "تضمین اصالت و سلامت کلیه محصولات با همکاری مستقیم برترین سازندگان",
    b1: "سامسونگ (Samsung)",
    b2: "اپل (Apple)",
    b3: "شیائومی (Xiaomi)",
    b4: "ایسوس (ASUS)",
    b5: "لنوو (Lenovo)",
    b6: "سونی (Sony)",
    trust_badge: "دارای نماد اعتماد الکترونیکی ۵ ستاره و عضو اتحادیه کشوری کسب‌وکارهای مجازی",
  },
  "product-highlights": {
    title: "چرا این محصول ارزش خرید بالایی دارد؟",
    subtitle: "۳ ویژگی متمایزکننده که این کالا را در بین گزینه‌های موجود بی‌رقیب می‌سازد",
    c1_icon: "🛡️",
    c1_title: "ضمانت اصالت ۱۰۰٪ فیزیکی",
    c1_desc: "تضمین کتبی اصالت کالا همراه با هولوگرام معتبر شرکتی و ثبت در سامانه جامع تجارت",
    c2_icon: "🔄",
    c2_title: "۷ روز مهلت تست و بازگشت",
    c2_desc: "امکان بازگشت کالا بدون قید و شرط و استرداد کامل وجه در صورت عدم رضایت",
    c3_icon: "⚡",
    c3_title: "پشتیبانی فنی و نصب رایگان",
    c3_desc: "راهنمایی تخصصی و تنظیمات اولیه توسط تیم کارشناسان فنی مجرب فروشگاه",
  },
};

/**
 * Transforms any of the 28 block patterns into clean, deeply nested AST nodes.
 * Fallback to DOM parser if slug is unrecognized.
 */
export function createPatternAST(
  pattern: { slug: string; title: string; category: string },
  renderedHtml: string,
  variablesOverride?: Record<string, string>
): BuilderElement {
  const slug = pattern.slug;
  const vars = {
    ...(PATTERN_DEFAULTS[slug] || {}),
    ...(variablesOverride || {}),
  };

  switch (slug) {
    case "hero-banner": {
      const title = vars.title || "کالکشن جدید رسید";
      const subtitle = vars.subtitle || "جدیدترین محصولات فصل با تخفیف ویژه";
      const imageUrl = vars.image_url || "/placeholder-hero.svg";
      const ctaText = vars.cta_text || "همین حالا بخرید";
      const ctaUrl = vars.cta_url || "/products";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "relative overflow-hidden rounded-2xl bg-primary text-primary-foreground p-6 md:p-12",
        children: [
          createContainerNode("سطر هیرو", {
            layout: {
              kind: "grid",
              direction: "row",
              justifyContent: "between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: { value: 32, unit: "px" },
              gridColumns: 2,
            },
            children: [
              createContainerNode("بخش متنی و دکمه", {
                layout: {
                  kind: "flex",
                  direction: "column",
                  justifyContent: "start",
                  alignItems: "stretch",
                  flexWrap: "nowrap",
                  gap: { value: 16, unit: "px" },
                  gridColumns: 1,
                },
                children: [
                  createHeadingWidget(title, "h1", "text-3xl font-bold md:text-5xl leading-tight"),
                  createTextWidget(`<p class="text-base opacity-90 md:text-lg leading-relaxed">${subtitle}</p>`),
                  createButtonWidget(ctaText, ctaUrl, "inline-flex items-center rounded-xl bg-primary-foreground px-6 py-3 font-semibold text-primary transition hover:opacity-90"),
                ],
              }),
              createImageWidget(imageUrl, title, "h-64 w-full rounded-xl object-cover md:h-80 shadow-md"),
            ],
          }),
        ],
      });
    }

    case "feature-grid": {
      const title = vars.title || "چرا از ما بخرید؟";
      const subtitle = vars.subtitle || "مزیت‌هایی که خرید را برای شما آسان می‌کنند";

      const items = [
        { title: vars.item1_title || "ارسال سریع", text: vars.item1_text || "ارسال در کمترین زمان" },
        { title: vars.item2_title || "ضمانت اصالت", text: vars.item2_text || "گارانتی معتبر شرکتی" },
        { title: vars.item3_title || "پرداخت امن", text: vars.item3_text || "درگاه‌های بانکی امن" },
      ];

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-12 w-full",
        children: [
          createContainerNode("سرتیتر بخش مزایا", {
            customCssClass: "text-center mb-8 space-y-2",
            children: [
              createHeadingWidget(title, "h2", "text-2xl font-bold md:text-3xl text-foreground"),
              createTextWidget(`<p class="text-muted-foreground leading-relaxed">${subtitle}</p>`),
            ],
          }),
          createContainerNode("شبکه کارت‌های مزیت", {
            layout: {
              kind: "grid",
              direction: "row",
              justifyContent: "between",
              alignItems: "stretch",
              flexWrap: "wrap",
              gap: { value: 24, unit: "px" },
              gridColumns: 3,
            },
            children: items.map((item, idx) =>
              createContainerNode(`کارت مزیت ${idx + 1}`, {
                customCssClass: "rounded-xl border bg-background p-6 shadow-sm flex flex-col space-y-2",
                children: [
                  createHeadingWidget(item.title, "h3", "text-lg font-bold text-foreground"),
                  createTextWidget(`<p class="text-sm text-muted-foreground leading-relaxed">${item.text}</p>`),
                ],
              })
            ),
          }),
        ],
      });
    }

    case "product-showcase-cta": {
      const title = vars.title || "پیشنهاد ویژه این هفته";
      const subtitle = vars.subtitle || "منتخبی از پرفروش‌ترین محصولات با قیمت استثنایی";
      const imageUrl = vars.image_url || "/placeholder-product.svg";
      const ctaText = vars.cta_text || "مشاهده محصولات";
      const ctaUrl = vars.cta_url || "/products";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "rounded-2xl border bg-background p-6 md:p-10 shadow-sm",
        children: [
          createContainerNode("شبکه معرفی محصول", {
            layout: {
              kind: "grid",
              direction: "row",
              justifyContent: "between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: { value: 32, unit: "px" },
              gridColumns: 2,
            },
            children: [
              createImageWidget(imageUrl, title, "h-72 w-full rounded-xl object-cover"),
              createContainerNode("محتوای فراخوان", {
                layout: {
                  kind: "flex",
                  direction: "column",
                  justifyContent: "start",
                  alignItems: "stretch",
                  flexWrap: "nowrap",
                  gap: { value: 16, unit: "px" },
                  gridColumns: 1,
                },
                children: [
                  createHeadingWidget(title, "h2", "text-2xl font-bold md:text-3xl text-foreground"),
                  createTextWidget(`<p class="text-muted-foreground leading-relaxed">${subtitle}</p>`),
                  createButtonWidget(ctaText, ctaUrl, "inline-flex items-center rounded-xl bg-primary px-6 py-3 font-semibold text-primary-foreground"),
                ],
              }),
            ],
          }),
        ],
      });
    }

    case "testimonials": {
      const title = vars.title || "مشتریان ما چه می‌گویند";
      const items = [
        { text: vars.item1_text || "کیفیت محصولات عالی بود و ارسال سریع انجام شد.", name: vars.item1_name || "سارا محمدی" },
        { text: vars.item2_text || "پشتیبانی بسیار پاسخگو بود؛ حتماً دوباره خرید می‌کنم.", name: vars.item2_name || "علی رضایی" },
      ];

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-12 w-full",
        children: [
          createHeadingWidget(title, "h2", "mb-8 text-center text-2xl font-bold md:text-3xl text-foreground"),
          createContainerNode("شبکه نظرات مشتریان", {
            layout: {
              kind: "grid",
              direction: "row",
              justifyContent: "between",
              alignItems: "stretch",
              flexWrap: "wrap",
              gap: { value: 24, unit: "px" },
              gridColumns: 2,
            },
            children: items.map((item, idx) =>
              createContainerNode(`نظر مشتری ${idx + 1}`, {
                customCssClass: "rounded-xl border bg-background p-6 shadow-sm flex flex-col justify-between space-y-4",
                children: [
                  createTextWidget(`<blockquote class="text-foreground leading-relaxed">«${item.text}»</blockquote>`),
                  createHeadingWidget(item.name, "h4", "text-sm font-semibold text-muted-foreground"),
                ],
              })
            ),
          }),
        ],
      });
    }

    case "faq-accordion": {
      const title = vars.title || "پرسش‌های متداول";
      const faqs = [
        { q: vars.q1 || "چند روز به طول می‌انجامد تا سفارش ارسال شود؟", a: vars.a1 || "سفارش‌های تا ساعت ۱۴ روز کاری بعد ارسال می‌شوند." },
        { q: vars.q2 || "آیا محصولات دارای ضمانت هستند؟", a: vars.a2 || "بله، تمامی محصولات با ضمانت اصالت و سلامت کالا ارسال می‌شوند." },
        { q: vars.q3 || "چه روش‌های پرداختی پشتیبانی می‌شود؟", a: vars.a3 || "پرداخت آنلاین از طریق درگاه‌های بانکی و کارت به کارت." },
      ];

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-12 w-full",
        children: [
          createHeadingWidget(title, "h2", "mb-6 text-center text-2xl font-bold md:text-3xl text-foreground"),
          createContainerNode("فهرست سوالات", {
            customCssClass: "mx-auto max-w-3xl space-y-3",
            children: faqs.map((f, idx) =>
              createContainerNode(`پرسش و پاسخ ${idx + 1}`, {
                customCssClass: "rounded-xl border bg-background p-4 shadow-sm space-y-2",
                children: [
                  createHeadingWidget(`؟ ${f.q}`, "h3", "font-semibold text-foreground text-base"),
                  createTextWidget(`<p class="text-sm text-muted-foreground leading-relaxed">${f.a}</p>`),
                ],
              })
            ),
          }),
        ],
      });
    }

    case "image-text": {
      const title = vars.title || "داستان ما";
      const body = vars.body || "ما با هدف ارائه کالاهای اصل و باکیفیت فعالیت می‌کنیم.";
      const imageUrl = vars.image_url || "/placeholder-about.svg";
      const ctaText = vars.cta_text || "بیشتر بدانید";
      const ctaUrl = vars.cta_url || "/about";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-12 w-full",
        children: [
          createContainerNode("سطر تصویر و متن", {
            layout: {
              kind: "grid",
              direction: "row",
              justifyContent: "between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: { value: 32, unit: "px" },
              gridColumns: 2,
            },
            children: [
              createImageWidget(imageUrl, title, "h-72 w-full rounded-xl object-cover shadow-sm"),
              createContainerNode("ستون توضیحات", {
                layout: {
                  kind: "flex",
                  direction: "column",
                  justifyContent: "start",
                  alignItems: "stretch",
                  flexWrap: "nowrap",
                  gap: { value: 16, unit: "px" },
                  gridColumns: 1,
                },
                children: [
                  createHeadingWidget(title, "h2", "text-2xl font-bold md:text-3xl text-foreground"),
                  createTextWidget(`<p class="text-muted-foreground leading-relaxed">${body}</p>`),
                  createButtonWidget(ctaText, ctaUrl),
                ],
              }),
            ],
          }),
        ],
      });
    }

    case "countdown-offer": {
      const title = vars.title || "فروش ویژه پایان فصل";
      const subtitle = vars.subtitle || "تا ۵۰٪ تخفیف روی هزاران کالا";
      const endsAt = vars.ends_at || "شنبه ۲۳:۵۹";
      const discountCode = vars.discount_code || "SEASON50";
      const ctaText = vars.cta_text || "خرید با تخفیف";
      const ctaUrl = vars.cta_url || "/products?discount=1";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "rounded-2xl border bg-gradient-to-r from-amber-500/10 via-background to-rose-500/10 p-8 text-center space-y-4",
        children: [
          createHeadingWidget(title, "h2", "text-2xl font-bold md:text-3xl text-foreground"),
          createTextWidget(`<p class="text-muted-foreground">${subtitle}</p>`),
          createHeadingWidget(`مهلت: ${endsAt} | کد تخفیف: ${discountCode}`, "h3", "font-mono font-bold text-primary text-lg"),
          createButtonWidget(ctaText, ctaUrl, "mx-auto bg-primary text-primary-foreground font-semibold rounded-xl px-8 py-3"),
        ],
      });
    }

    case "star-rating-display": {
      const rating = vars.rating || "۴.۳";
      const reviewCount = vars.review_count || "۱۲۸";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "inline-flex items-center gap-2 rounded-xl border border-border/60 bg-card px-4 py-2",
        layout: { kind: "flex", direction: "row", justifyContent: "start", alignItems: "center", flexWrap: "nowrap", gap: { value: 8, unit: "px" }, gridColumns: 1 },
        children: [
          createHeadingWidget(`★★★★☆ ${rating}`, "h4", "text-amber-400 font-bold text-sm"),
          createTextWidget(`(${reviewCount} نظر)`, "text-xs text-muted-foreground"),
        ],
      });
    }

    case "review-histogram": {
      const average = vars.average || "۴.۳";
      const total = vars.total || "۱۲۸";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "rounded-2xl border bg-background p-6 space-y-4",
        children: [
          createHeadingWidget(`میانگین امتیاز: ${average} از ۵ (${total} نظر ثبت شده)`, "h3", "text-lg font-bold text-foreground"),
          createContainerNode("سطرهای درصد امتیازها", {
            customCssClass: "space-y-2 text-sm text-muted-foreground",
            children: [
              createContainerNode("سطر ۵ ستاره", {
                layout: { kind: "flex", direction: "row", justifyContent: "between", alignItems: "center" },
                children: [
                  createTextWidget("۵ ستاره"),
                  createTextWidget(`${vars.star5 || "۶۱"}٪`, "font-bold text-foreground"),
                ],
              }),
              createContainerNode("سطر ۴ ستاره", {
                layout: { kind: "flex", direction: "row", justifyContent: "between", alignItems: "center" },
                children: [
                  createTextWidget("۴ ستاره"),
                  createTextWidget(`${vars.star4 || "۴۲"}٪`, "font-bold text-foreground"),
                ],
              }),
              createContainerNode("سطر ۳ ستاره", {
                layout: { kind: "flex", direction: "row", justifyContent: "between", alignItems: "center" },
                children: [
                  createTextWidget("۳ ستاره"),
                  createTextWidget(`${vars.star3 || "۱۵"}٪`, "font-bold text-foreground"),
                ],
              }),
              createContainerNode("سطر ۲ ستاره", {
                layout: { kind: "flex", direction: "row", justifyContent: "between", alignItems: "center" },
                children: [
                  createTextWidget("۲ ستاره"),
                  createTextWidget(`${vars.star2 || "۷"}٪`, "font-bold text-foreground"),
                ],
              }),
              createContainerNode("سطر ۱ ستاره", {
                layout: { kind: "flex", direction: "row", justifyContent: "between", alignItems: "center" },
                children: [
                  createTextWidget("۱ ستاره"),
                  createTextWidget(`${vars.star1 || "۳"}٪`, "font-bold text-foreground"),
                ],
              }),
            ],
          }),
        ],
      });
    }

    case "product-card-grid": {
      const title = vars.title || "محصولات پرفروش";
      const products = [
        { name: vars.p1_name || "هدفون بلوتوثی", price: vars.p1_price || "۱۸,۵۰۰,۰۰۰ تومان", img: vars.p1_image || "/placeholder-product.svg", url: vars.p1_url || "/products/1" },
        { name: vars.p2_name || "ایرپاد پرو", price: vars.p2_price || "۱۲,۹۰۰,۰۰۰ تومان", img: vars.p2_image || "/placeholder-product.svg", url: vars.p2_url || "/products/2" },
        { name: vars.p3_name || "اسپیکر بلوتوثی", price: vars.p3_price || "۸,۷۵۰,۰۰۰ تومان", img: vars.p3_image || "/placeholder-product.svg", url: vars.p3_url || "/products/3" },
      ];

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-12 w-full",
        children: [
          createHeadingWidget(title, "h2", "mb-8 text-center text-2xl font-bold md:text-3xl text-foreground"),
          createContainerNode("شبکه کارت محصولات", {
            layout: {
              kind: "grid",
              direction: "row",
              justifyContent: "between",
              alignItems: "stretch",
              flexWrap: "wrap",
              gap: { value: 24, unit: "px" },
              gridColumns: 3,
            },
            children: products.map((p, idx) =>
              createContainerNode(`کارت محصول ${idx + 1}`, {
                customCssClass: "rounded-xl border bg-background overflow-hidden p-4 flex flex-col space-y-3",
                children: [
                  createImageWidget(p.img, p.name, "h-48 w-full object-cover rounded-lg"),
                  createHeadingWidget(p.name, "h3", "font-bold text-base text-foreground"),
                  createTextWidget(p.price, "font-bold text-primary"),
                  createButtonWidget("مشاهده و خرید", p.url, "w-full text-center"),
                ],
              })
            ),
          }),
        ],
      });
    }

    case "text-marquee": {
      const texts = [vars.text1, vars.text2, vars.text3, vars.text4].filter(Boolean);
      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "bg-muted/80 border-y py-3 text-xs overflow-hidden",
        children: [
          createContainerNode("نوار اعلانات", {
            layout: { kind: "flex", direction: "row", justifyContent: "around", alignItems: "center", flexWrap: "wrap", gap: { value: 16, unit: "px" }, gridColumns: 1 },
            children: texts.map((t, idx) =>
              createTextWidget(`✦ ${t}`, "font-semibold text-foreground")
            ),
          }),
        ],
      });
    }

    case "stats-counter": {
      const stats = [
        { val: vars.stat1_value || "۱,۲۳۴", lbl: vars.stat1_label || "محصول" },
        { val: vars.stat2_value || "۵,۶۷۸", lbl: vars.stat2_label || "سفارش" },
        { val: vars.stat3_value || "۹۸٪", lbl: vars.stat3_label || "رضایت مشتری" },
        { val: vars.stat4_value || "۲۴", lbl: vars.stat4_label || "ساعت پشتیبانی" },
      ];

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-10 bg-muted/40 rounded-2xl border w-full",
        children: [
          createContainerNode("شبکه آمار", {
            layout: { kind: "grid", direction: "row", justifyContent: "between", alignItems: "center", flexWrap: "wrap", gap: { value: 16, unit: "px" }, gridColumns: 4 },
            children: stats.map((s, idx) =>
              createContainerNode(`شاخص آماری ${idx + 1}`, {
                customCssClass: "text-center flex flex-col space-y-1",
                children: [
                  createHeadingWidget(s.val, "h3", "text-3xl font-extrabold text-primary"),
                  createTextWidget(s.lbl, "text-xs text-muted-foreground font-semibold"),
                ],
              })
            ),
          }),
        ],
      });
    }

    case "image-gallery-showcase": {
      const title = vars.title || "گالری محصولات";
      const images = [vars.img1, vars.img2, vars.img3, vars.img4].filter(Boolean);

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-12 w-full",
        children: [
          createHeadingWidget(title, "h2", "mb-6 text-center text-2xl font-bold md:text-3xl text-foreground"),
          createContainerNode("شبکه تصاویر گالری", {
            layout: { kind: "grid", direction: "row", justifyContent: "between", alignItems: "stretch", flexWrap: "wrap", gap: { value: 16, unit: "px" }, gridColumns: 4 },
            children: images.map((img, idx) =>
              createImageWidget(img || "/placeholder.svg", `تصویر گالری ${idx + 1}`, "h-56 w-full rounded-xl object-cover shadow-sm")
            ),
          }),
        ],
      });
    }

    case "discount-badge-banner": {
      const percent = vars.percent || "۳۰";
      const text = vars.text || "تخفیف ویژه روی محصولات منتخب";
      const ctaText = vars.cta_text || "مشاهده محصولات";
      const ctaUrl = vars.cta_url || "/products";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "rounded-2xl bg-destructive text-destructive-foreground p-6 shadow-md",
        layout: { kind: "flex", direction: "row", justifyContent: "between", alignItems: "center", flexWrap: "wrap", gap: { value: 16, unit: "px" }, gridColumns: 1 },
        children: [
          createContainerNode("اطلاعات تخفیف", {
            layout: { kind: "flex", direction: "row", justifyContent: "start", alignItems: "center", flexWrap: "nowrap", gap: { value: 16, unit: "px" }, gridColumns: 1 },
            children: [
              createHeadingWidget(`${percent}٪ تخفیف`, "h3", "text-3xl font-black text-destructive-foreground"),
              createTextWidget(`<p class="text-sm opacity-90">${text}</p>`),
            ],
          }),
          createButtonWidget(ctaText, ctaUrl, "bg-background text-foreground font-bold rounded-xl px-6 py-2.5"),
        ],
      });
    }

    case "mega-menu-categories": {
      const title = vars.title || "دسته‌بندی محصولات";
      const cats = [
        { name: vars.cat1_name || "لپ‌تاپ و کامپیوتر", url: vars.cat1_url || "/category/laptop" },
        { name: vars.cat2_name || "موبایل و تبلت", url: vars.cat2_url || "/category/mobile" },
        { name: vars.cat3_name || "هدفون و اسپیکر", url: vars.cat3_url || "/category/audio" },
        { name: vars.cat4_name || "لوازم جانبی", url: vars.cat4_url || "/category/accessories" },
      ];

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-8 w-full",
        children: [
          createHeadingWidget(title, "h2", "mb-6 text-xl font-bold text-foreground"),
          createContainerNode("شبکه دسته‌بندی‌ها", {
            layout: { kind: "grid", direction: "row", justifyContent: "between", alignItems: "stretch", flexWrap: "wrap", gap: { value: 16, unit: "px" }, gridColumns: 4 },
            children: cats.map((c) =>
              createButtonWidget(c.name, c.url, "w-full rounded-xl border bg-background p-4 text-center font-bold text-foreground hover:bg-muted/40 transition")
            ),
          }),
        ],
      });
    }

    case "pricing-table": {
      const title = vars.title || "پلن‌های قیمت‌گذاری و تعرفه‌ها";
      const subtitle = vars.subtitle || "پلن متناسب با کسب‌وکار خود را انتخاب کنید";

      const plans = [
        {
          name: vars.plan1_name || "پایه",
          desc: vars.plan1_desc || "مناسب برای شروع",
          price: `${vars.plan1_price || "۲۹۰,۰۰۰ تومان"} ${vars.plan1_period || "/ ماهانه"}`,
          features: [vars.plan1_f1, vars.plan1_f2, vars.plan1_f3].filter(Boolean),
          cta: vars.plan1_cta || "انتخاب پلن",
          url: vars.plan1_url || "/pricing",
          isFeatured: false,
        },
        {
          badge: vars.plan2_badge || "محبوب‌ترین",
          name: vars.plan2_name || "حرفه‌ای",
          desc: vars.plan2_desc || "بهترین انتخاب برای تیم‌ها",
          price: `${vars.plan2_price || "۶۹۰,۰۰۰ تومان"} ${vars.plan2_period || "/ ماهانه"}`,
          features: [vars.plan2_f1, vars.plan2_f2, vars.plan2_f3, vars.plan2_f4].filter(Boolean),
          cta: vars.plan2_cta || "شروع پلن",
          url: vars.plan2_url || "/pricing",
          isFeatured: true,
        },
        {
          name: vars.plan3_name || "ویژه",
          desc: vars.plan3_desc || "راهکار جامع برای سازمان‌ها",
          price: `${vars.plan3_price || "۱,۴۹۰,۰۰۰ تومان"} ${vars.plan3_period || "/ ماهانه"}`,
          features: [vars.plan3_f1, vars.plan3_f2, vars.plan3_f3, vars.plan3_f4].filter(Boolean),
          cta: vars.plan3_cta || "ارتباط با ما",
          url: vars.plan3_url || "/contact",
          isFeatured: false,
        },
      ];

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-14 w-full",
        children: [
          createContainerNode("سرتیتر جدول تعرفه", {
            customCssClass: "text-center mb-10 space-y-2",
            children: [
              createHeadingWidget(title, "h2", "text-3xl font-extrabold text-foreground"),
              createTextWidget(`<p class="text-muted-foreground text-sm">${subtitle}</p>`),
            ],
          }),
          createContainerNode("شبکه پلن‌ها", {
            layout: { kind: "grid", direction: "row", justifyContent: "between", alignItems: "stretch", flexWrap: "wrap", gap: { value: 24, unit: "px" }, gridColumns: 3 },
            children: plans.map((p) =>
              createContainerNode(`پلن ${p.name}`, {
                customCssClass: `rounded-2xl border p-6 shadow-sm flex flex-col justify-between ${
                  p.isFeatured ? "border-2 border-primary bg-background shadow-md relative" : "bg-background"
                }`,
                children: [
                  p.badge
                    ? createTextWidget(p.badge, "inline-block text-[10px] font-bold bg-primary text-primary-foreground px-2 py-0.5 rounded-full mb-2")
                    : null,
                  createHeadingWidget(p.name, "h3", "text-xl font-bold"),
                  createTextWidget(p.desc, "text-xs text-muted-foreground"),
                  createHeadingWidget(p.price, "h4", "text-2xl font-black text-primary my-3"),
                  createTextWidget(p.features.map(f => `✓ ${f}`).join("\n"), "text-xs space-y-2 text-muted-foreground whitespace-pre-line"),
                  createButtonWidget(p.cta, p.url, `w-full mt-6 ${p.isFeatured ? "bg-primary text-primary-foreground font-bold" : ""}`),
                ].filter(Boolean) as BuilderElement[],
              })
            ),
          }),
        ],
      });
    }

    case "price-list": {
      const title = vars.title || "لیست قیمت خدمات و محصولات";
      const subtitle = vars.subtitle || "قیمت‌ها به تومان و شامل کلیه خدمات جانبی است";

      const items = [
        { t: vars.item1_title, d: vars.item1_desc, p: vars.item1_price },
        { t: vars.item2_title, d: vars.item2_desc, p: vars.item2_price },
        { t: vars.item3_title, d: vars.item3_desc, p: vars.item3_price },
        { t: vars.item4_title, d: vars.item4_desc, p: vars.item4_price },
        { t: vars.item5_title, d: vars.item5_desc, p: vars.item5_price },
      ].filter((i) => i.t);

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-10 max-w-3xl mx-auto w-full",
        children: [
          createHeadingWidget(title, "h2", "text-2xl font-bold text-center text-foreground"),
          createTextWidget(`<p class="text-xs text-muted-foreground text-center mb-8">${subtitle}</p>`),
          createContainerNode("فهرست آیتم‌ها", {
            layout: { kind: "flex", direction: "column", justifyContent: "start", alignItems: "stretch", flexWrap: "nowrap", gap: { value: 12, unit: "px" }, gridColumns: 1 },
            children: items.map((item, idx) =>
              createContainerNode(`ردیف قیمت ${idx + 1}`, {
                customCssClass: "flex items-center justify-between border-b pb-3",
                layout: { kind: "flex", direction: "row", justifyContent: "between", alignItems: "center", flexWrap: "nowrap", gap: { value: 16, unit: "px" }, gridColumns: 1 },
                children: [
                  createHeadingWidget(item.t!, "h4", "font-semibold text-sm text-foreground"),
                  createTextWidget(`<p class="text-xs text-muted-foreground">${item.d}</p>`),
                  createHeadingWidget(item.p || "", "h4", "text-sm font-bold text-primary shrink-0"),
                ],
              })
            ),
          }),
        ],
      });
    }

    case "icon-box-grid": {
      const title = vars.title || "چرا خدمات ما را انتخاب می‌کنند؟";
      const subtitle = vars.subtitle || "ارائه برترین راهکارها با تمرکز بر کیفیت، سرعت و رضایت شما";

      const boxes = [
        { icon: vars.box1_icon || "🚀", title: vars.box1_title || "تحویل سریع و آنی", desc: vars.box1_desc || "پردازش سریع سفارش‌ها" },
        { icon: vars.box2_icon || "🛡️", title: vars.box2_title || "تضمین اصالت و کیفیت", desc: vars.box2_desc || "تضمین صددرصدی اصالت کالاها" },
        { icon: vars.box3_icon || "💳", title: vars.box3_title || "پرداخت امن و مطمئن", desc: vars.box3_desc || "پشتیبانی از درگاه‌های بانکی عضو شاپرک" },
        { icon: vars.box4_icon || "🎧", title: vars.box4_title || "پشتیبانی هفت‌روزه", desc: vars.box4_desc || "پاسخگویی سریع در تمام روزهای هفته" },
      ];

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-12 w-full",
        children: [
          createContainerNode("سرتیتر بخش جعبه‌ها", {
            customCssClass: "text-center mb-8 space-y-2",
            children: [
              createHeadingWidget(title, "h2", "text-2xl font-bold text-foreground"),
              createTextWidget(`<p class="text-sm text-muted-foreground">${subtitle}</p>`),
            ],
          }),
          createContainerNode("شبکه جعبه‌های آیکون", {
            layout: { kind: "grid", direction: "row", justifyContent: "between", alignItems: "stretch", flexWrap: "wrap", gap: { value: 20, unit: "px" }, gridColumns: 4 },
            children: boxes.map((box, idx) =>
              createContainerNode(`باکس ${idx + 1}`, {
                customCssClass: "rounded-xl border bg-background p-5 text-center flex flex-col items-center space-y-2",
                children: [
                  createHeadingWidget(`${box.icon} ${box.title}`, "h3", "text-base font-bold text-foreground"),
                  createTextWidget(`<p class="text-xs text-muted-foreground leading-relaxed">${box.desc}</p>`),
                ],
              })
            ),
          }),
        ],
      });
    }

    case "author-bio": {
      const name = vars.name || "دکتر رضا کاظمی";
      const role = vars.role || "پژوهشگر ارشد";
      const badge = vars.badge || "نویسنده برگزیده";
      const avatarUrl = vars.avatar_url || "/placeholder-avatar.svg";
      const bio = vars.bio || "بیش از یک دهه سابقه در تجربه کاربری";
      const contactEmail = vars.contact_email || "reza@example.com";
      const ctaText = vars.cta_text || "ارسال پیام";
      const ctaUrl = vars.cta_url || "/contact";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "rounded-2xl border bg-background p-6 md:p-8 flex items-center gap-6 flex-wrap md:flex-nowrap",
        layout: { kind: "flex", direction: "row", justifyContent: "start", alignItems: "center", flexWrap: "wrap", gap: { value: 24, unit: "px" }, gridColumns: 1 },
        children: [
          createImageWidget(avatarUrl, name, "w-24 h-24 rounded-full object-cover shrink-0 border-2 border-primary"),
          createContainerNode("اطلاعات نویسنده", {
            layout: { kind: "flex", direction: "column", justifyContent: "start", alignItems: "stretch", flexWrap: "nowrap", gap: { value: 8, unit: "px" }, gridColumns: 1 },
            children: [
              createHeadingWidget(`${name} (${badge})`, "h3", "text-xl font-bold text-foreground"),
              createTextWidget(`<p class="text-xs text-muted-foreground">${role} | ${contactEmail}</p><p class="text-sm text-foreground/90 mt-2 leading-relaxed">${bio}</p>`),
              createButtonWidget(ctaText, ctaUrl),
            ],
          }),
        ],
      });
    }

    case "pull-quote": {
      const quoteText = vars.quote_text || "سرمایه‌گذاری روی کیفیت و جلب رضایت مشتری، پایدارترین استراتژی است.";
      const authorName = vars.author_name || "سهراب رحمانی";
      const authorTitle = vars.author_title || "مدیر ارشد محصول";
      const sourceNote = vars.source_note || "همایش سالانه نوآوری";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "my-8 border-s-4 border-primary bg-muted/30 p-6 rounded-e-xl space-y-3",
        children: [
          createHeadingWidget(`«${quoteText}»`, "h3", "text-lg md:text-xl font-semibold italic text-foreground leading-relaxed"),
          createTextWidget(`${authorName} - ${authorTitle} (${sourceNote})`, "text-xs text-muted-foreground font-semibold"),
        ],
      });
    }

    case "support-callout": {
      const title = vars.title || "نیاز به مشاوره قبل از خرید دارید؟";
      const description = vars.description || "کارشناسان فنی ما آماده پاسخگویی هستند.";
      const icon = vars.icon || "💬";
      const phoneLabel = vars.phone_label || "تماس مستقیم:";
      const phoneNumber = vars.phone_number || "۰۲۱-۸۸۸۸۹۹۹۹";
      const phoneUrl = vars.phone_url || "tel:02188889999";
      const ctaText = vars.cta_text || "شروع گفتگوی آنلاین";
      const ctaUrl = vars.cta_url || "/chat";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "rounded-2xl border-2 border-dashed border-primary/40 bg-primary/5 p-6 md:p-8 flex items-center justify-between flex-wrap gap-4",
        layout: { kind: "flex", direction: "row", justifyContent: "between", alignItems: "center", flexWrap: "wrap", gap: { value: 16, unit: "px" }, gridColumns: 1 },
        children: [
          createContainerNode("متن تماس", {
            layout: { kind: "flex", direction: "column", justifyContent: "start", alignItems: "stretch", flexWrap: "nowrap", gap: { value: 8, unit: "px" }, gridColumns: 1 },
            children: [
              createHeadingWidget(`${icon} ${title}`, "h3", "text-lg font-bold text-foreground"),
              createTextWidget(`<p class="text-xs text-muted-foreground leading-relaxed">${description}</p><p class="text-sm font-bold text-primary mt-1">${phoneLabel} ${phoneNumber}</p>`),
            ],
          }),
          createButtonWidget(ctaText, ctaUrl, "bg-primary text-primary-foreground font-semibold px-6 py-2.5 rounded-xl"),
        ],
      });
    }

    case "comparison-table": {
      const title = vars.title || "مقایسه مشخصات و ویژگی‌های فنی";
      const subtitle = vars.subtitle || "تفاوت مدل‌های مختلف را به دقت بررسی کنید";
      const col1Title = vars.col1_title || "ویژگی‌ها و قابلیت‌ها";
      const col2Name = vars.col2_name || "مدل پرو";
      const col2Price = vars.col2_price || "۴,۸۵۰,۰۰۰ تومان";
      const col3Name = vars.col3_name || "مدل استاندارد";
      const col3Price = vars.col3_price || "۲,۹۰۰,۰۰۰ تومان";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-10 w-full",
        children: [
          createHeadingWidget(title, "h2", "text-2xl font-bold text-center text-foreground"),
          createTextWidget(`<p class="text-xs text-muted-foreground text-center mb-8">${subtitle}</p>`),
          createTableWidget(
            [col1Title, `${col2Name} (${col2Price})`, `${col3Name} (${col3Price})`],
            [
              [vars.f1_name || "گارانتی رسمی", `✓ ${vars.f1_v2 || "۱۸ ماه تعویض"}`, vars.f1_v3 || "۱۲ ماه تعمیر"],
              [vars.f2_name || "پشتیبانی فنی", `✓ ${vars.f2_v2 || "۲۴ ساعته"}`, vars.f2_v3 || "روزهای کاری"],
              [vars.f3_name || "ارسال اکسپرس", `✓ ${vars.f3_v2 || "رایگان"}`, vars.f3_v3 || "عادی"],
              [vars.f4_name || "مهلت تست", `✓ ${vars.f4_v2 || "۱۴ روز"}`, vars.f4_v3 || "۷ روز"],
            ],
            "جدول مقایسه جامع",
            { bordered: true, striped: true, highlightCol: 1 }
          ),
        ],
      });
    }

    case "process-steps": {
      const title = vars.title || "سفارش تا تحویل در ۴ مرحله آسان";
      const subtitle = vars.subtitle || "تجربه خریدی لذت‌بخش و شفاف";
      const steps = [
        { num: vars.s1_num || "۱", title: vars.s1_title || "انتخاب کالا", desc: vars.s1_desc || "بررسی مشخصات" },
        { num: vars.s2_num || "۲", title: vars.s2_title || "پرداخت امن", desc: vars.s2_desc || "درگاه‌های شاپرک" },
        { num: vars.s3_num || "۳", title: vars.s3_title || "بسته‌بندی ایمن", desc: vars.s3_desc || "کنترل سلامت" },
        { num: vars.s4_num || "۴", title: vars.s4_title || "تحویل اکسپرس", desc: vars.s4_desc || "ارسال سریع پستی" },
      ];

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-12 w-full",
        children: [
          createContainerNode("سرتیتر مراحل", {
            customCssClass: "text-center mb-8 space-y-2",
            children: [
              createHeadingWidget(title, "h2", "text-2xl font-bold text-foreground"),
              createTextWidget(`<p class="text-xs text-muted-foreground">${subtitle}</p>`),
            ],
          }),
          createContainerNode("شبکه مراحل", {
            layout: { kind: "grid", direction: "row", justifyContent: "between", alignItems: "stretch", flexWrap: "wrap", gap: { value: 16, unit: "px" }, gridColumns: 4 },
            children: steps.map((s) =>
              createContainerNode(`مرحله ${s.num}: ${s.title}`, {
                customCssClass: "rounded-xl border bg-background p-5 text-center flex flex-col items-center space-y-2",
                children: [
                  createHeadingWidget(`${s.num}. ${s.title}`, "h3", "text-base font-bold text-foreground"),
                  createTextWidget(`<p class="text-xs text-muted-foreground leading-relaxed">${s.desc}</p>`),
                ],
              })
            ),
          }),
        ],
      });
    }

    case "lead-capture-form": {
      const title = vars.title || "درخواست مشاوره رایگان خرید";
      const subtitle = vars.subtitle || "شماره همراه خود را وارد کنید تا کارشناسان ما تماس بگیرند.";
      const buttonText = vars.button_text || "درخواست تماس رایگان کارشناس";
      const privacyNote = vars.privacy_note || "اطلاعات تماس شما نزد ما کاملاً محفوظ است.";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "rounded-2xl border bg-card p-6 md:p-8 max-w-lg mx-auto text-center space-y-4 my-8",
        children: [
          createHeadingWidget(title, "h3", "text-xl font-bold text-foreground"),
          createTextWidget(`<p class="text-xs text-muted-foreground">${subtitle}</p>`),
          createFormInputWidget(
            "نام و نام خانوادگی",
            "full_name",
            vars.name_placeholder || "نام و نام خانوادگی",
            true
          ),
          createFormInputWidget(
            "شماره همراه",
            "phone",
            vars.phone_placeholder || "شماره همراه (مثلاً ۰۹۱۲۳۴۵۶۷۸۹)",
            true,
            "tel"
          ),
          createButtonWidget(buttonText, "#submit", "w-full bg-primary text-primary-foreground font-semibold py-3 rounded-xl"),
          createTextWidget(`<p class="text-[11px] text-muted-foreground/70">${privacyNote}</p>`),
        ],
      });
    }

    case "alert-banner": {
      const icon = vars.icon || "📢";
      const badge = vars.badge || "اطلاعیه مهم";
      const title = vars.title || "آغاز جشنواره شگفت‌انگیز پاییزه";
      const description = vars.description || "ارسال رایگان برای تمام سفارش‌های بالای ۵۰۰ هزار تومان.";
      const ctaText = vars.cta_text || "مشاهده تخفیف‌ها";
      const ctaUrl = vars.cta_url || "/search?sale=true";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "rounded-xl border-s-4 border-amber-500 bg-amber-500/10 p-4 flex items-center justify-between flex-wrap gap-3",
        layout: { kind: "flex", direction: "row", justifyContent: "between", alignItems: "center", flexWrap: "wrap", gap: { value: 12, unit: "px" }, gridColumns: 1 },
        children: [
          createContainerNode("متن اعلان", {
            layout: { kind: "flex", direction: "column", justifyContent: "start", alignItems: "stretch", flexWrap: "nowrap", gap: { value: 4, unit: "px" }, gridColumns: 1 },
            children: [
              createHeadingWidget(`${icon} ${badge}: ${title}`, "h4", "font-bold text-sm text-foreground"),
              createTextWidget(description, "text-xs text-muted-foreground"),
            ],
          }),
          createButtonWidget(ctaText, ctaUrl, "text-xs font-semibold px-4 py-1.5 rounded-lg bg-amber-500 text-white"),
        ],
      });
    }

    case "floating-contact-bar": {
      const heading = vars.heading || "راه‌های ارتباطی سریع با پشتیبانی";
      const statusText = vars.status_text || "پاسخگویی آنلاین کارشناسان";

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "p-4 rounded-xl border bg-card/95 shadow-lg flex items-center justify-between flex-wrap gap-4",
        layout: { kind: "flex", direction: "row", justifyContent: "between", alignItems: "center", flexWrap: "wrap", gap: { value: 16, unit: "px" }, gridColumns: 1 },
        children: [
          createContainerNode("وضعیت پشتیبانی", {
            layout: { kind: "flex", direction: "column", justifyContent: "start", alignItems: "stretch", flexWrap: "nowrap", gap: { value: 4, unit: "px" }, gridColumns: 1 },
            children: [
              createHeadingWidget(heading, "h4", "text-sm font-bold text-foreground"),
              createTextWidget(`● ${statusText}`, "text-xs text-emerald-600 font-semibold"),
            ],
          }),
          createContainerNode("دکمه‌های ارتباطی", {
            layout: { kind: "flex", direction: "row", justifyContent: "end", alignItems: "center", flexWrap: "wrap", gap: { value: 8, unit: "px" }, gridColumns: 1 },
            children: [
              createButtonWidget(vars.phone_label || "تلفن پشتیبانی", vars.phone_url || "tel:02188889999", "text-xs px-3 py-1.5"),
              createButtonWidget(vars.whatsapp_label || "واتساپ", vars.whatsapp_url || "https://wa.me/", "text-xs px-3 py-1.5"),
              createButtonWidget(vars.telegram_label || "تلگرام", vars.telegram_url || "https://t.me/", "text-xs px-3 py-1.5"),
            ],
          }),
        ],
      });
    }

    case "brand-logo-carousel": {
      const title = vars.title || "برندهای معتبر و شرکای تجاری رسمی";
      const subtitle = vars.subtitle || "تضمین اصالت و سلامت کلیه محصولات";
      const logos = [vars.b1, vars.b2, vars.b3, vars.b4, vars.b5, vars.b6].filter(Boolean);

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-10 text-center space-y-6 w-full",
        children: [
          createContainerNode("سرتیتر برندها", {
            customCssClass: "space-y-1",
            children: [
              createHeadingWidget(title, "h2", "text-xl font-bold text-foreground"),
              createTextWidget(subtitle, "text-xs text-muted-foreground"),
            ],
          }),
          createContainerNode("شبکه لوگوها", {
            layout: { kind: "grid", direction: "row", justifyContent: "between", alignItems: "stretch", flexWrap: "wrap", gap: { value: 12, unit: "px" }, gridColumns: 6 },
            children: logos.map((b) =>
              createTextWidget(String(b || ""), "rounded-lg border bg-background p-3 text-xs font-bold text-muted-foreground text-center")
            ),
          }),
          createTextWidget(vars.trust_badge || "", "text-xs text-muted-foreground/80 font-medium"),
        ],
      });
    }

    case "product-highlights": {
      const title = vars.title || "چرا این محصول ارزش خرید بالایی دارد؟";
      const subtitle = vars.subtitle || "۳ ویژگی متمایزکننده که این کالا را در بین گزینه‌های موجود بی‌رقیب می‌سازد";
      const cards = [
        { icon: vars.c1_icon || "🛡️", title: vars.c1_title || "ضمانت اصالت ۱۰۰٪ فیزیکی", desc: vars.c1_desc || "تضمین کتبی اصالت کالا" },
        { icon: vars.c2_icon || "🔄", title: vars.c2_title || "۷ روز مهلت تست و بازگشت", desc: vars.c2_desc || "امکان بازگشت کالا بدون قید و شرط" },
        { icon: vars.c3_icon || "⚡", title: vars.c3_title || "پشتیبانی فنی و نصب رایگان", desc: vars.c3_desc || "راهنمایی تخصصی و تنظیمات اولیه" },
      ];

      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-12 w-full",
        children: [
          createContainerNode("سرتیتر برجستگی‌ها", {
            customCssClass: "text-center mb-8 space-y-2",
            children: [
              createHeadingWidget(title, "h2", "text-2xl font-bold text-foreground"),
              createTextWidget(`<p class="text-xs text-muted-foreground">${subtitle}</p>`),
            ],
          }),
          createContainerNode("شبکه ویژگی‌های متمایز", {
            layout: { kind: "grid", direction: "row", justifyContent: "between", alignItems: "stretch", flexWrap: "wrap", gap: { value: 20, unit: "px" }, gridColumns: 3 },
            children: cards.map((c, idx) =>
              createContainerNode(`ویژگی ${idx + 1}`, {
                customCssClass: "rounded-xl border bg-background p-6 shadow-sm space-y-2",
                children: [
                  createHeadingWidget(`${c.icon} ${c.title}`, "h3", "text-lg font-bold text-foreground"),
                  createTextWidget(`<p class="text-xs text-muted-foreground leading-relaxed">${c.desc}</p>`),
                ],
              })
            ),
          }),
        ],
      });
    }

    default: {
      // Fallback: generic wrapper with HTML custom widget
      return createContainerNode(`${pattern.category}: ${pattern.title}`, {
        customCssClass: "py-8 w-full",
        children: [
          createHtmlCustomWidget(renderedHtml, pattern.title),
        ],
      });
    }
  }
}
