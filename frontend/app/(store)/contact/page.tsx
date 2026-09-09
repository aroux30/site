"use client";

import { useState } from "react";
import { Phone, Mail, MapPin, Clock, Send, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

const contactInfo = [
  {
    icon: Phone,
    title: "تلفن تماس",
    lines: ["۰۲۱-۱۲۳۴۵۶۷۸", "۰۹۱۲-۱۲۳-۴۵۶۷"],
    color: "text-blue-500 bg-blue-50",
  },
  {
    icon: Mail,
    title: "ایمیل",
    lines: ["info@example.com", "support@example.com"],
    color: "text-emerald-500 bg-emerald-50",
  },
  {
    icon: MapPin,
    title: "آدرس",
    lines: ["تهران، خیابان ولیعصر، بالاتر از میدان ونک، پلاک ۱۲۳"],
    color: "text-red-500 bg-red-50",
  },
  {
    icon: Clock,
    title: "ساعات کاری",
    lines: ["شنبه تا چهارشنبه: ۹ صبح تا ۶ عصر", "پنج‌شنبه: ۹ صبح تا ۱ بعدازظهر"],
    color: "text-purple-500 bg-purple-50",
  },
];

interface FormErrors {
  name?: string;
  email?: string;
  subject?: string;
  message?: string;
}

export default function ContactPage() {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    subject: "",
    message: "",
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitted, setSubmitted] = useState(false);

  function validate(): boolean {
    const newErrors: FormErrors = {};

    if (!formData.name.trim() || formData.name.trim().length < 2) {
      newErrors.name = "نام باید حداقل ۲ حرف باشد";
    }

    if (
      !formData.email.trim() ||
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)
    ) {
      newErrors.email = "لطفاً ایمیل معتبر وارد کنید";
    }

    if (!formData.subject.trim() || formData.subject.trim().length < 3) {
      newErrors.subject = "موضوع باید حداقل ۳ حرف باشد";
    }

    if (!formData.message.trim() || formData.message.trim().length < 10) {
      newErrors.message = "پیام باید حداقل ۱۰ حرف باشد";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (validate()) {
      // In production, send to API
      console.log("Contact form data:", formData);
      setSubmitted(true);
    }
  }

  function handleChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    // Clear field error on change
    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  }

  return (
    <div className="container-page">
      {/* Page Header */}
      <div className="mb-10 text-center">
        <h1 className="mb-3 text-3xl font-bold text-foreground">تماس با ما</h1>
        <p className="mx-auto max-w-lg text-muted-foreground">
          سوال، پیشنهاد یا انتقادی دارید؟ از طریق فرم زیر یا اطلاعات تماس با
          ما در ارتباط باشید.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-5">
        {/* Contact Form */}
        <div className="lg:col-span-3">
          <Card className="p-6 sm:p-8">
            {submitted ? (
              <div className="flex flex-col items-center justify-center py-12">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-50 text-emerald-500">
                  <CheckCircle className="h-8 w-8" />
                </div>
                <h2 className="mb-2 text-xl font-bold text-foreground">
                  پیام شما ارسال شد
                </h2>
                <p className="mb-6 text-center text-muted-foreground">
                  از تماس شما متشکریم. کارشناسان ما در اسرع وقت با شما تماس
                  خواهند گرفت.
                </p>
                <Button
                  variant="outline"
                  onClick={() => {
                    setSubmitted(false);
                    setFormData({ name: "", email: "", subject: "", message: "" });
                  }}
                >
                  ارسال پیام جدید
                </Button>
              </div>
            ) : (
              <>
                <h2 className="mb-6 text-lg font-semibold text-foreground">
                  ارسال پیام
                </h2>
                <form onSubmit={handleSubmit} className="space-y-5">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="name">نام و نام خانوادگی</Label>
                      <Input
                        id="name"
                        name="name"
                        value={formData.name}
                        onChange={handleChange}
                        placeholder="نام خود را وارد کنید"
                      />
                      {errors.name && (
                        <p className="text-xs text-destructive">
                          {errors.name}
                        </p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">ایمیل</Label>
                      <Input
                        id="email"
                        name="email"
                        type="email"
                        value={formData.email}
                        onChange={handleChange}
                        placeholder="email@example.com"
                        dir="ltr"
                        className="text-left"
                      />
                      {errors.email && (
                        <p className="text-xs text-destructive">
                          {errors.email}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="subject">موضوع</Label>
                    <Input
                      id="subject"
                      name="subject"
                      value={formData.subject}
                      onChange={handleChange}
                      placeholder="موضوع پیام خود را وارد کنید"
                    />
                    {errors.subject && (
                      <p className="text-xs text-destructive">
                        {errors.subject}
                      </p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="message">پیام</Label>
                    <Textarea
                      id="message"
                      name="message"
                      value={formData.message}
                      onChange={handleChange}
                      placeholder="پیام خود را بنویسید..."
                      rows={5}
                    />
                    {errors.message && (
                      <p className="text-xs text-destructive">
                        {errors.message}
                      </p>
                    )}
                  </div>

                  <Button type="submit" size="lg" className="w-full sm:w-auto">
                    <Send className="ml-2 h-4 w-4" />
                    ارسال پیام
                  </Button>
                </form>
              </>
            )}
          </Card>
        </div>

        {/* Contact Info */}
        <div className="space-y-4 lg:col-span-2">
          {contactInfo.map((info) => (
            <Card key={info.title} className="p-5">
              <div className="flex gap-4">
                <div
                  className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-lg ${info.color}`}
                >
                  <info.icon className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="mb-1 font-semibold text-foreground">
                    {info.title}
                  </h3>
                  {info.lines.map((line, i) => (
                    <p key={i} className="text-sm text-muted-foreground">
                      {line}
                    </p>
                  ))}
                </div>
              </div>
            </Card>
          ))}

          {/* Map Placeholder */}
          <Card className="overflow-hidden">
            <div className="flex aspect-video items-center justify-center bg-muted">
              <div className="text-center">
                <MapPin className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  نقشه محل فروشگاه
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
