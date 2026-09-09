import type { Metadata } from "next";
import {
  Users,
  Target,
  Eye,
  ShoppingBag,
  Award,
  HeartHandshake,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export const metadata: Metadata = {
  title: "درباره ما",
};

const stats = [
  { label: "سال تجربه", value: "۵+", icon: Award },
  { label: "مشتری", value: "۵۰,۰۰۰+", icon: Users },
  { label: "محصول", value: "۱۰,۰۰۰+", icon: ShoppingBag },
  { label: "رضایت مشتری", value: "۹۸٪", icon: HeartHandshake },
];

const team = [
  { name: "سارا احمدی", role: "مدیرعامل و بنیان‌گذار" },
  { name: "محمد رضایی", role: "مدیر فنی" },
  { name: "زهرا کریمی", role: "مدیر بازاریابی" },
  { name: "امیر حسینی", role: "مدیر پشتیبانی" },
];

export default function AboutPage() {
  return (
    <div className="container-page">
      {/* Hero */}
      <section className="mb-16 rounded-2xl bg-gradient-to-l from-primary-600 to-secondary-600 p-8 text-white sm:p-14">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="mb-4 text-3xl font-bold sm:text-4xl">درباره ما</h1>
          <p className="text-lg leading-relaxed text-white/90">
            ما با هدف ارائه بهترین تجربه خرید آنلاین، از سال ۱۳۹۸ فعالیت خود
            را آغاز کردیم و امروز افتخار خدمت‌رسانی به هزاران مشتری در سراسر
            ایران را داریم.
          </p>
        </div>
      </section>

      {/* Company Story */}
      <section className="mb-16">
        <div className="mx-auto max-w-3xl">
          <h2 className="mb-6 text-2xl font-bold text-foreground">
            داستان ما
          </h2>
          <div className="space-y-4 leading-relaxed text-muted-foreground">
            <p>
              فروشگاه آنلاین ما با ایده‌ای ساده شروع شد: دسترسی آسان به
              محصولات با کیفیت و قیمت مناسب برای همه مردم ایران. ما معتقدیم که
              هر فردی حق دارد بهترین محصولات را با بهترین قیمت و در کوتاه‌ترین
              زمان دریافت کند.
            </p>
            <p>
              در طول سال‌های فعالیت، تیم ما با تلاش مستمر و گوش دادن به
              نیازهای مشتریان، توانسته است خدماتی متمایز ارائه دهد. از ارسال
              سریع و رایگان گرفته تا پشتیبانی ۲۴ ساعته، تمامی تلاش ما بر
              ارائه بهترین تجربه خرید متمرکز است.
            </p>
            <p>
              امروز با بیش از ۱۰,۰۰۰ محصول در دسته‌بندی‌های مختلف از جمله
              الکترونیک، پوشاک، لوازم خانه و بسیاری دیگر، آماده خدمت‌رسانی
              به شما هستیم.
            </p>
          </div>
        </div>
      </section>

      <Separator className="mb-16" />

      {/* Mission & Vision */}
      <section className="mb-16">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <Card className="p-8">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Target className="h-6 w-6" />
            </div>
            <h3 className="mb-3 text-xl font-bold text-foreground">
              مأموریت ما
            </h3>
            <p className="leading-relaxed text-muted-foreground">
              ارائه بهترین محصولات با کیفیت تضمین‌شده، قیمت رقابتی و تجربه
              خریدی آسان و لذت‌بخش. ما تلاش می‌کنیم تا با استفاده از
              فناوری‌های روز، خرید آنلاین را به ساده‌ترین و مطمئن‌ترین شکل
              ممکن برای مشتریان خود فراهم کنیم.
            </p>
          </Card>

          <Card className="p-8">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-secondary/10 text-secondary-600">
              <Eye className="h-6 w-6" />
            </div>
            <h3 className="mb-3 text-xl font-bold text-foreground">
              چشم‌انداز ما
            </h3>
            <p className="leading-relaxed text-muted-foreground">
              تبدیل شدن به معتبرترین و محبوب‌ترین فروشگاه آنلاین ایران.
              می‌خواهیم به جایی برسیم که هر ایرانی اولین انتخابش برای خرید
              آنلاین، فروشگاه ما باشد و بتوانیم با ایجاد اشتغال و حمایت از
              تولید داخلی، نقشی مؤثر در اقتصاد کشور داشته باشیم.
            </p>
          </Card>
        </div>
      </section>

      {/* Stats */}
      <section className="mb-16">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {stats.map((stat) => (
            <Card
              key={stat.label}
              className="p-6 text-center"
            >
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                <stat.icon className="h-6 w-6" />
              </div>
              <p className="text-2xl font-bold text-foreground sm:text-3xl">
                {stat.value}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {stat.label}
              </p>
            </Card>
          ))}
        </div>
      </section>

      <Separator className="mb-16" />

      {/* Team */}
      <section className="mb-16">
        <h2 className="mb-8 text-center text-2xl font-bold text-foreground">
          تیم ما
        </h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {team.map((member) => (
            <Card
              key={member.name}
              className="p-6 text-center"
            >
              <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-muted">
                <Users className="h-8 w-8 text-muted-foreground" />
              </div>
              <h3 className="font-semibold text-foreground">{member.name}</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {member.role}
              </p>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
