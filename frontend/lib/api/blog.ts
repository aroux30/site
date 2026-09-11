import apiClient from "./client";

export interface BlogPostCategory {
  id: string;
  name: string;
  slug: string;
  created_at?: string;
  updated_at?: string;
  post_count?: number;
}

export interface BlogPost {
  id: string;
  author_id: string;
  author_name?: string;
  title: string;
  slug: string;
  excerpt?: string;
  content?: string;
  cover_image_url?: string;
  status: "draft" | "published" | "archived";
  published_at?: string;
  category_id?: string;
  category?: BlogPostCategory;
  reading_time?: number;
  view_count: number;
  related_posts?: BlogPost[];
  seo?: {
    title?: string;
    description?: string;
    canonical_url?: string;
    og_title?: string;
    og_description?: string;
    og_image?: string;
    schema_markup?: Record<string, unknown>;
  };
  created_at: string;
  updated_at: string;
}

export interface BlogListResponse {
  items: BlogPost[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface BlogQueryParams {
  category?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

/* -------------------------------------------------------------------------- */
/*                               Fallback Data                                */
/* -------------------------------------------------------------------------- */

export const fallbackCategories: BlogPostCategory[] = [
  { id: "cat-1", name: "راهنمای خرید", slug: "buying-guides", post_count: 8 },
  { id: "cat-2", name: "بررسی و جعبه‌گشایی", slug: "reviews", post_count: 5 },
  { id: "cat-3", name: "اخبار و تازه‌های فناوری", slug: "tech-news", post_count: 12 },
  { id: "cat-4", name: "آموزش و ترفندها", slug: "tutorials", post_count: 7 },
  { id: "cat-5", name: "مقایسه محصولات", slug: "comparisons", post_count: 4 },
];

export const fallbackPosts: BlogPost[] = [
  {
    id: "post-1",
    author_id: "u-1",
    author_name: "علیرضا احمدی",
    title: "راهنمای جامع خرید گوشی‌های پرچمدار سال؛ کدام پرچمدار ارزش خرید بیشتری دارد؟",
    slug: "flagship-phones-buying-guide-2026",
    excerpt:
      "با تنوع بالای گوشی‌های پرچمدار در بازار، انتخاب گزینه ایده‌آل دشوار شده است. در این مقاله به مقایسه دوربین، پردازنده، نمایشگر و ارزش خرید جدیدترین پرچمداران می‌پردازیم.",
    content: `## مقدمه
بازار تلفن‌های هوشمند پرچمدار در سال‌های اخیر دستخوش تحولات شگرفی در زمینه‌های هوش مصنوعی روی دستگاه، پیشرفت حسگرهای عکاسی پریسکوپی و شارژ سریع شده است. اگر در پی ارتقای گوشی خود هستید، در این مقاله تمام جوانب خرید یک پرچمدار مناسب را بررسی خواهیم کرد.

### مهم‌ترین معیارهای انتخاب پرچمدار
پیش از خرید، باید نیازهای خود را اولویت‌بندی کنید:
1. **قدرت پردازش و هوش مصنوعی**: چیپست‌های نوین با پردازش عصبی پیشرفته.
2. **سیستم دوربین و فیلم‌برداری**: تفکیک نور، زوم اپتیکال و دیافراگم متغیر.
3. **کیفیت نمایشگر و روشنایی**: پنل‌های LTPO AMOLED با روشنایی بالا در زیر نور مستقیم خورشید.
4. **ظرفیت باتری و سرعت شارژ**: عمر باتری حداقل یک روز کامل در کاربری سنگین.

## عملکرد پردازشی و دوام حرارتی
پردازنده‌های پرچمدار امروزی قدرتی فراتر از نیاز روزمره کاربران دارند. نکته کلیدی، مدیریت حرارتی پایدار در جلسات طولانی گیمینگ یا ویرایش ویدیوهای 4K و 8K است. پرچمداران مجهز به خنک‌کننده‌های محفظه بخار بزرگتر، پایداری به مراتب بیشتری نشان می‌دهند.

### عکاسی و فیلم‌برداری؛ رقابت حسگرهای ۱ اینچی
امروزه دوربین اصلی اکثر پرچمداران به سنسورهای بزرگ نزدیک به یک اینچ مجهز شده‌اند که در تاریکی شب، جزئیات حیرت‌انگیزی بدون نویز تولید می‌کنند. حضور لنزهای تله‌فوتو با قابلیت زوم بدون افت کیفیت، ابزاری بی‌نظیر برای ثبت پرتره‌های حرفه‌ای فراهم آورده است.

## نتیجه‌گیری و پیشنهاد نهایی
اگر اولویت شما اکوسیستم هماهنگ و ضبط ویدیوی بی‌رقیب است، گزینه‌های مجهز به پردازنده‌های بهینه شده بیشترین کارایی را خواهند داشت. اما اگر شارژ فوق سریع، سفارشی‌سازی نامحدود و زوم اپتیکال عمیق را می‌پسندید، پرچمداران اندرویدی انتخابی ایده‌آل خواهند بود.`,
    cover_image_url:
      "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=1200&auto=format&fit=crop&q=80",
    status: "published",
    published_at: "2026-09-08T10:00:00Z",
    category_id: "cat-1",
    category: fallbackCategories[0],
    reading_time: 6,
    view_count: 1420,
    created_at: "2026-09-08T09:00:00Z",
    updated_at: "2026-09-08T10:00:00Z",
  },
  {
    id: "post-2",
    author_id: "u-2",
    author_name: "مریم رضایی",
    title: "مقایسه لپ‌تاپ‌های اولترابوک جدید: مک‌بوک در برابر رقبای ویندوزی",
    slug: "ultrabook-macbook-vs-windows-comparison",
    excerpt:
      "بررسی دقیق عملکرد، شارژدهی باتری، کیفیت ساخت و نمایشگر در مقایسه مستقیم جدیدترین اولترابوک‌های بازار برای برنامه‌نویسان و طراحان.",
    content: `## چرا مقایسه اولترابوک‌ها اهمیت دارد؟
لپ‌تاپ‌های باریک و سبک برای کارمندان دورکار، مدیران، برنامه‌نویسان و تولیدکنندگان محتوا ابزار حیاتی کار محسوب می‌شوند. توازن میان وزن کم، قدرت پردازش بالا و شارژدهی طولانی باتری بزرگترین چالش سازندگان است.

### طراحی و کیفیت ساخت
استفاده از آلومینیوم بازیافتی با برش دقیق CNC و لولاهای روان که با یک انگشت باز می‌شوند، به استاندارد طلایی این رده تبدیل شده است. صفحه کلیدهای ارگونومیک با حرکت کلید مناسب و تاچ‌پدهای لمسی مجهز به بازخورد لرزشی تجربه‌ای لذت‌بخش به ارمغان می‌آورند.

### طول عمر باتری در استفاده روزمره
بزرگترین جهش چند سال اخیر، امکان کار مداوم ۱۰ تا ۱۵ ساعته بدون نیاز به شارژر در طول روز کاری است. معماری‌های کارآمد پردازنده باعث شده‌اند تا دیگر نگران یافتن پریز برق در جلسات یا کافه‌ها نباشید.

## جمع‌بندی
برای افرادی که نرم‌افزارهای تخصصی سیستم‌عامل مک را ترجیح می‌دهند، شارژدهی و روانی عملکرد بی‌نظیر است. اما برای کاربرانی که نیاز به ارتقای قطعات، تنوع درگاه‌ها یا اجرای بازی‌های رایانه‌ای دارند، اولترابوک‌های ویندوزی پیشرفته آزادی عمل بیشتری ارائه می‌دهند.`,
    cover_image_url:
      "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=1200&auto=format&fit=crop&q=80",
    status: "published",
    published_at: "2026-09-06T14:30:00Z",
    category_id: "cat-5",
    category: fallbackCategories[4],
    reading_time: 8,
    view_count: 980,
    created_at: "2026-09-06T14:00:00Z",
    updated_at: "2026-09-06T14:30:00Z",
  },
  {
    id: "post-3",
    author_id: "u-3",
    author_name: "سهراب مرادی",
    title: "بهترین هدفون‌های بی‌سیم با قابلیت حذف نویز فعال (ANC) در سال ۲۰۲۶",
    slug: "best-wireless-headphones-anc-2026",
    excerpt:
      "اگر به دنبال سکوت مطلق در محیط کار یا لذت بردن از موسیقی با کیفیت استودیویی هستید، این ۵ هدفون برتر بازار با قوی‌ترین سیستم نویز کنسلینگ را بررسی کنید.",
    content: `## سکوت؛ باارزش‌ترین دارایی در دنیای شلوغ
فناوری حذف نویز فعال (Active Noise Cancellation) با تولید فرکانس‌های معکوس امواج صوتی مزاحم اطراف، فضایی ساکت و آرام برای تمرکز روی کار یا گوش دادن به موسیقی فراهم می‌کند.

### فاکتورهای کلیدی در انتخاب هدفون ANC
- **کارایی در حذف صدای مکالمات انسانی**: نویزهای با فرکانس متغیر چالش اصلی الگوریتم‌های هوش مصنوعی هستند.
- **کیفیت میکروفون برای تماس‌های کاری**: وضوح صدای کاربر حتی در خیابان‌های شلوغ یا باد شدید.
- **راحتی ایرکاپ‌ها و وزن کلی**: برای استفاده‌های طولانی‌مدت بیش از ۴ ساعت.
- **کدک‌های صوتی بلوتوث با کیفیت بالا**: نظیر LDAC و aptX Lossless.

### برترین گزینه‌ها از نگاه کارشناسان
در بررسی‌های آزمایشگاهی ما، مدل‌های برتر سونی، اپل، سنهایزر و بوز توانستند بیش از ۹۵ درصد صداهای ممتد بم و بیش از ۸۰ درصد صداهای زیر محیطی را دفع کنند. راحتی پدهای گوشی و امکان اتصال همزمان به دو دستگاه (Multipoint) از مهم‌ترین ویژگی‌های مدل‌های پرچمدار است.`,
    cover_image_url:
      "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=1200&auto=format&fit=crop&q=80",
    status: "published",
    published_at: "2026-09-04T09:15:00Z",
    category_id: "cat-2",
    category: fallbackCategories[1],
    reading_time: 5,
    view_count: 1840,
    created_at: "2026-09-04T08:00:00Z",
    updated_at: "2026-09-04T09:15:00Z",
  },
  {
    id: "post-4",
    author_id: "u-1",
    author_name: "علیرضا احمدی",
    title: "۱۰ ترفند طلایی برای افزایش چشمگیر طول عمر باتری گوشی هوشمند",
    slug: "10-tips-to-extend-smartphone-battery-life",
    excerpt:
      "با رعایت این چند نکته ساده و علمی، سلامت باتری گوشی خود را برای سال‌ها بالای ۸۵ درصد نگه دارید و از هزینه‌های تعویض باتری خلاص شوید.",
    content: `## علم نگهداری از باتری‌های لیتیوم-یون
بسیاری از باورهای عامیانه درباره شارژ باتری تلفن همراه مربوط به نسل‌های قدیمی باتری‌های نیکل-کادمیوم است. باتری‌های مدرن لیتیومی نیازمند مراقبت‌های متفاوتی هستند تا واکنش‌های شیمیایی داخلی آنها دچار فرسودگی زودهنگام نشود.

### قانون طلایی ۲۰ تا ۸۰ درصد
تخلیه کامل باتری تا صفر درصد و شارژ مداوم آن تا صد درصد بیشترین فشار فیزیکی را به ساختار الکترودها وارد می‌کند. سعی کنید شارژ گوشی خود را بین ۲۰٪ تا ۸۰٪ یا نهایتاً ۸۵٪ نگه دارید. اکثر سیستم‌های عامل نوین قابلیت محدودسازی سقف شارژ را در تنظیمات دارند.

### گرما؛ بزرگترین دشمن سلامت باتری
داغ شدن گوشی حین بازی سنگین همزمان با اتصال به شارژر، سرعت تخریب سلول‌های لیتیوم را چند برابر می‌کند. همیشه گوشی را در محیط خنک شارژ کنید و هنگام شارژ سریع از بازی‌های گرافیکی سنگین بپرهیزید.`,
    cover_image_url:
      "https://images.unsplash.com/photo-1585338107529-13afc5f02586?w=1200&auto=format&fit=crop&q=80",
    status: "published",
    published_at: "2026-09-02T11:00:00Z",
    category_id: "cat-4",
    category: fallbackCategories[3],
    reading_time: 4,
    view_count: 3120,
    created_at: "2026-09-02T10:00:00Z",
    updated_at: "2026-09-02T11:00:00Z",
  },
  {
    id: "post-5",
    author_id: "u-2",
    author_name: "مریم رضایی",
    title: "ساعت هوشمند در سال ۲۰۲۶؛ نجات‌دهنده سلامت یا ابزار تجملاتی؟",
    slug: "smartwatch-health-savior-or-luxury",
    excerpt:
      "سنسورهای نوار قلب (ECG)، سنجش اکسیژن خون، پایش استرس و کیفیت خواب چقدر دقیق هستند و ساعت‌های هوشمند چگونه می‌توانند سبک زندگی ما را دگرگون کنند؟",
    content: `## تبدیل مچ دست به آزمایشگاه سیار سلامت
ساعت‌های هوشمند امروزی دیگر صرفاً نمایش‌دهنده پیام‌ها و اعلان‌های گوشی نیستند؛ آنها گجت‌های پیشرفته پایش سلامت به شمار می‌روند که جان انسان‌های بسیاری را با تشخیص زودهنگام ناهماهنگی ضربان قلب نجات داده‌اند.

### قابلیت‌های پیشرفته پایش تندرستی
- نوار قلب پیوسته با هشدارهای فیبریلاسیون دهلیزی
- سنجش اکسیژن اشباع خون (SpO2) در طول خواب شبانه
- ثبت مراحل خواب عمیق، سبک و REM
- تشخیص سقوط ناگهانی و تصادف رانندگی با ارسال پیام اضطراری خودکار

اگر فعالیت ورزشی مرتب دارید یا مایلید عادات سلامتی روزانه خود را بهبود دهید، استفاده از یک ساعت یا مچ‌بند هوشمند معتبر سرمایه‌گذاری ارزشمندی روی سلامت شما خواهد بود.`,
    cover_image_url:
      "https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?w=1200&auto=format&fit=crop&q=80",
    status: "published",
    published_at: "2026-08-29T16:00:00Z",
    category_id: "cat-2",
    category: fallbackCategories[1],
    reading_time: 5,
    view_count: 1150,
    created_at: "2026-08-29T15:00:00Z",
    updated_at: "2026-08-29T16:00:00Z",
  },
  {
    id: "post-6",
    author_id: "u-3",
    author_name: "سهراب مرادی",
    title: "مقایسه تلویزیون‌های OLED در برابر Mini-LED؛ کدام تکنولوژی تصویر برتر است؟",
    slug: "oled-vs-miniled-tv-comparison",
    excerpt:
      "کنتراست بی‌نهایت و مشکی خالص پنل‌های OLED یا روشنایی خیره‌کننده و دوام طولانی پنل‌های Mini-LED؟ راهنمای انتخاب برای اتاق‌های تاریک و روشن.",
    content: `## میدان نبرد غول‌های تصویر
انتخاب بین تلویزیون‌های اولد و مینی‌ال‌ای‌دی یکی از متداول‌ترین پرسش‌های خریداران حرفه‌ای تلویزیون برای تماشای فیلم و اتصال به کنسول‌های بازی است.

### پنل‌های OLED؛ پادشاه کنتراست و رنگ مشکی
در پنل‌های OLED هر پیکسل به صورت مجزا نور ساطع می‌کند و خاموش می‌شود. نتیجه آن مشکی ۱۰۰٪ خالص و کنتراست بی‌نهایت است که در اتاق‌های تاریک و تماشای فیلم‌های سینمایی تجربه‌ای شبیه به سینما پدید می‌آورد.

### فناوری Mini-LED؛ درخشش خیره‌کننده در نور روز
تلویزیون‌های مینی‌ال‌ای‌دی با هزاران دیود نوری ریز در پس‌زمینه، قادرند به روشنایی بیش از ۲۰۰۰ نیت دست یابند. این میزان روشنایی، آنها را برای اتاق‌های پرنور با پنجره‌های بزرگ و بدون نگرانی از سوختگی پیکسل ایده‌آل می‌سازد.`,
    cover_image_url:
      "https://images.unsplash.com/photo-1593359677879-a4bb92f829d1?w=1200&auto=format&fit=crop&q=80",
    status: "published",
    published_at: "2026-08-25T13:40:00Z",
    category_id: "cat-5",
    category: fallbackCategories[4],
    reading_time: 7,
    view_count: 2430,
    created_at: "2026-08-25T13:00:00Z",
    updated_at: "2026-08-25T13:40:00Z",
  },
];

/* -------------------------------------------------------------------------- */
/*                               API Client                                   */
/* -------------------------------------------------------------------------- */

export async function fetchBlogPosts(
  params?: BlogQueryParams,
): Promise<BlogListResponse> {
  try {
    const { data } = await apiClient.get<BlogListResponse>("/blog/posts", {
      params,
    });
    if (data && data.items && data.items.length > 0) {
      return data;
    }
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.warn("Could not fetch blog posts from API, using fallback data", error);
    }
  }

  // Fallback filtering
  let filtered = [...fallbackPosts];
  if (params?.category) {
    filtered = filtered.filter(
      (p) => p.category?.slug === params.category || p.category_id === params.category,
    );
  }
  if (params?.search) {
    const q = params.search.toLowerCase().trim();
    filtered = filtered.filter(
      (p) =>
        p.title.toLowerCase().includes(q) ||
        (p.excerpt && p.excerpt.toLowerCase().includes(q)) ||
        (p.content && p.content.toLowerCase().includes(q)),
    );
  }

  const page = params?.page || 1;
  const pageSize = params?.page_size || 9;
  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const startIndex = (page - 1) * pageSize;
  const items = filtered.slice(startIndex, startIndex + pageSize);

  return {
    items,
    total,
    page,
    page_size: pageSize,
    total_pages: totalPages,
    has_next: page < totalPages,
    has_prev: page > 1,
  };
}

export async function fetchBlogPostBySlug(slug: string): Promise<BlogPost> {
  try {
    const { data } = await apiClient.get<BlogPost>(`/blog/posts/${slug}`);
    if (data && data.id) {
      return data;
    }
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.warn("Could not fetch post from API, using fallback data", { slug, error });
    }
  }

  const post = fallbackPosts.find((p) => p.slug === slug);
  if (post) {
    // Add related posts from other items
    const related = fallbackPosts
      .filter((p) => p.id !== post.id)
      .slice(0, 3);
    return { ...post, related_posts: related };
  }

  // If slug not directly matched, return first post with custom slug for dev preview
  const first = fallbackPosts[0]!;
  return { ...first, slug, related_posts: fallbackPosts.slice(1, 4) };
}

export async function fetchBlogCategories(): Promise<BlogPostCategory[]> {
  try {
    const { data } = await apiClient.get<BlogPostCategory[]>("/blog/categories");
    if (Array.isArray(data) && data.length > 0) {
      return data;
    }
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.warn("Could not fetch blog categories from API, using fallback data", error);
    }
  }

  return fallbackCategories;
}

export async function fetchRecentBlogPosts(limit = 4): Promise<BlogPost[]> {
  try {
    const { data } = await apiClient.get<BlogPost[]>("/blog/recent", {
      params: { limit },
    });
    if (Array.isArray(data) && data.length > 0) {
      return data;
    }
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.warn("Could not fetch recent posts from API, using fallback data", error);
    }
  }

  return fallbackPosts.slice(0, limit);
}
