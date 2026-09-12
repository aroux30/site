"use client";

import React, { useState, useEffect } from "react";
import {
  Users,
  Search,
  Filter,
  Shield,
  UserCheck,
  UserX,
  Mail,
  Phone,
  Calendar,
  MoreVertical,
  CheckCircle2,
  XCircle,
  RefreshCw,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toPersianDigits } from "@/lib/utils";
import apiClient from "@/lib/api/client";

interface UserItem {
  id: string;
  phone: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  role: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}



export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadUsers() {
      try {
        setLoading(true);
        // The admin list lives on the users router: /api/v1/users/admin/users
        const res = await apiClient.get("/users/admin/users?page=1&page_size=50");
        if (res.data && Array.isArray(res.data.items)) {
          setUsers(res.data.items);
        }
      } catch (err) {
        // Honest failure: show an error state, never fabricated users
        setLoadError(true);
      } finally {
        setLoading(false);
      }
    }
    loadUsers();
  }, []);

  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      u.phone.includes(search) ||
      (u.email && u.email.toLowerCase().includes(search.toLowerCase())) ||
      (u.first_name && u.first_name.includes(search)) ||
      (u.last_name && u.last_name.includes(search));

    const matchesRole = roleFilter === "all" || u.role === roleFilter;

    return matchesSearch && matchesRole;
  });

  const toggleUserStatus = (id: string) => {
    setUsers((prev) =>
      prev.map((u) => (u.id === id ? { ...u, is_active: !u.is_active } : u))
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">مدیریت کاربران</h1>
          <p className="text-sm text-muted-foreground">
            مشاهده، جستجو و مدیریت نقش و وضعیت حساب‌های کاربری
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="px-3 py-1 text-sm font-medium">
            مجموع کاربران: {toPersianDigits(users.length)}
          </Badge>
        </div>
      </div>

      {/* Filters Bar */}
      <Card className="p-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جستجو با شماره موبایل، نام یا ایمیل..."
              className="pr-9"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="all">همه نقش‌ها</option>
              <option value="customer">مشتریان</option>
              <option value="super_admin">مدیران سیستم</option>
              <option value="vendor">فروشندگان</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Users Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3">کاربر</th>
                <th className="px-4 py-3">شماره تماس</th>
                <th className="px-4 py-3">نقش</th>
                <th className="px-4 py-3">تاریخ ثبت‌نام</th>
                <th className="px-4 py-3">وضعیت حساب</th>
                <th className="px-4 py-3 text-center">عملیات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loadError ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-destructive">
                    خطا در دریافت کاربران. لطفاً صفحه را دوباره بارگذاری کنید.
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted-foreground">
                    کاربری با این مشخصات یافت نشد.
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => (
                  <tr key={u.id} className="transition-colors hover:bg-muted/30">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 font-bold text-primary">
                          {u.first_name ? u.first_name[0] : "ک"}
                        </div>
                        <div>
                          <div className="font-medium text-foreground">
                            {u.first_name && u.last_name
                              ? `${u.first_name} ${u.last_name}`
                              : "کاربر بدون نام"}
                          </div>
                          {u.email && (
                            <div className="text-xs text-muted-foreground">{u.email}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-sm">
                      {toPersianDigits(u.phone)}
                    </td>
                    <td className="px-4 py-3">
                      {u.role === "super_admin" ? (
                        <Badge variant="destructive" className="gap-1">
                          <Shield className="h-3 w-3" /> مدیر کل
                        </Badge>
                      ) : u.role === "vendor" ? (
                        <Badge variant="secondary">فروشنده</Badge>
                      ) : (
                        <Badge variant="outline">مشتری عادی</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {toPersianDigits(u.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      {u.is_active ? (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
                          <CheckCircle2 className="h-3.5 w-3.5" /> فعال
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-destructive">
                          <XCircle className="h-3.5 w-3.5" /> مسدود
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleUserStatus(u.id)}
                        className="text-xs"
                      >
                        {u.is_active ? "مسدودسازی" : "فعال‌سازی"}
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
