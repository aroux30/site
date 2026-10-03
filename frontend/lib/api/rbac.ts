import apiClient from "./client";

// ── Types ───────────────────────────────────────────────────────────────────

export interface Permission {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  resource: string;
  action: string;
  created_at: string;
}

export interface Role {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_system: boolean;
  created_at: string;
  /**
   * Hydrated view-model fields. The list endpoint returns neither; the roles
   * page merges each row's detail response in before rendering, and default
   * initialisers guarantee both are present from that point on. Callers that
   * use a bare list response must default them (``?? []`` / ``?? 0``).
   */
  permissions: Permission[];
  user_count: number;
}

export interface RoleDetail extends Role {
  permissions: Permission[];
}

export interface UserRoles {
  user_id: string;
  roles: Role[];
}

/** افزودن/کاستن یک مجوز برای یک کاربر خاص، مستقل از نقش‌ها (WordPress add_cap) */
export type OverrideEffect = "grant" | "deny";

export interface PermissionOverride {
  id: string;
  user_id: string;
  permission: string;
  effect: OverrideEffect;
  created_by: string | null;
  created_at: string;
}

export interface PermissionOverrides {
  user_id: string;
  items: PermissionOverride[];
  total: number;
}

// ── API (admin) ─────────────────────────────────────────────────────────────

export const rbacApi = {
  /** فهرست همه مجوزها (آرایه خام — قرارداد صفحه مدیریت نقش‌ها) */
  listPermissions: async (params?: { resource?: string }): Promise<Permission[]> => {
    const res = await apiClient.get<
      Permission[] | { items: Permission[]; total: number }
    >("/rbac/admin/permissions", { params });
    const data = res.data;
    return Array.isArray(data) ? data : data.items;
  },

  /** فهرست نقش‌ها (آرایه خام — قرارداد صفحه مدیریت نقش‌ها) */
  listRoles: async (): Promise<Role[]> => {
    const res = await apiClient.get<Role[] | { items: Role[]; total: number }>(
      "/rbac/admin/roles",
    );
    // The endpoint has returned both shapes over its life; normalise so a
    // caller never has to care which one is live.
    const data = res.data;
    const roles = Array.isArray(data) ? data : data.items;
    return roles.map((role) => ({ ...role, permissions: role.permissions ?? [], user_count: role.user_count ?? 0 }));
  },

  /** جزئیات نقش همراه با مجوزهایش */
  getRole: async (roleId: string): Promise<RoleDetail> => {
    const res = await apiClient.get<RoleDetail>(`/rbac/admin/roles/${roleId}`);
    return res.data;
  },

  /** ایجاد نقش */
  createRole: async (payload: {
    name: string;
    slug: string;
    description?: string | null;
  }): Promise<Role> => {
    const res = await apiClient.post<Role>("/rbac/admin/roles", payload);
    return res.data;
  },

  /** ویرایش نقش */
  updateRole: async (
    roleId: string,
    payload: { name?: string; description?: string | null },
  ): Promise<Role> => {
    const res = await apiClient.patch<Role>(`/rbac/admin/roles/${roleId}`, payload);
    return res.data;
  },

  /** حذف نقش */
  deleteRole: async (roleId: string): Promise<void> => {
    await apiClient.delete(`/rbac/admin/roles/${roleId}`);
  },

  /** افزودن مجوزها به نقش */
  assignPermissions: async (roleId: string, permissionIds: string[]): Promise<void> => {
    await apiClient.post(`/rbac/admin/roles/${roleId}/permissions`, {
      permission_ids: permissionIds,
    });
  },

  /** حذف مجوزها از نقش */
  removePermissions: async (roleId: string, permissionIds: string[]): Promise<void> => {
    await apiClient.delete(`/rbac/admin/roles/${roleId}/permissions`, {
      data: { permission_ids: permissionIds },
    });
  },

  /** نقش‌های یک کاربر */
  getUserRoles: async (userId: string | number): Promise<UserRoles> => {
    const res = await apiClient.get<UserRoles>(`/rbac/admin/users/${userId}/roles`);
    return res.data;
  },

  /** حذف یک مجوز از فهرست مجوزها */
  deletePermission: async (permissionId: string): Promise<void> => {
    await apiClient.delete(`/rbac/admin/permissions/${permissionId}`);
  },

  /** استثناهای مجوز یک کاربر (بالاتر از نقش‌ها) */
  listPermissionOverrides: async (userId: string): Promise<PermissionOverrides> => {
    const res = await apiClient.get<PermissionOverrides>(
      `/rbac/admin/users/${userId}/permission-overrides`,
    );
    return res.data;
  },

  /**
   * اعطا یا منع یک مجوز به کاربر. upsert است: اعطای دوباره همان مجوز اثر
   * قبلی را برمی‌گرداند (add_cap در وردپرس هم دقیقاً همین رفتار را دارد).
   */
  setPermissionOverride: async (
    userId: string,
    permission: string,
    effect: OverrideEffect,
  ): Promise<PermissionOverride> => {
    const res = await apiClient.post<PermissionOverride>(
      `/rbac/admin/users/${userId}/permission-overrides`,
      { permission, effect },
    );
    return res.data;
  },

  /** برداشتن استثنای یک مجوز از کاربر */
  revokePermissionOverride: async (
    userId: string,
    permission: string,
  ): Promise<void> => {
    // The codename is a path segment ("blog:write" carries a colon and a
    // slash would silently address a different route), so it is encoded
    // rather than interpolated raw.
    await apiClient.delete(
      `/rbac/admin/users/${userId}/permission-overrides/${encodeURIComponent(permission)}`,
    );
  },

  /** تخصیص نقش به کاربر */
  assignUserRoles: async (userId: string | number, roleIds: string[]): Promise<UserRoles> => {
    const res = await apiClient.post<UserRoles>(`/rbac/admin/users/${userId}/roles`, {
      role_ids: roleIds,
    });
    return res.data;
  },

  /** حذف نقش از کاربر */
  removeUserRoles: async (userId: string | number, roleIds: string[]): Promise<UserRoles> => {
    const res = await apiClient.delete<UserRoles>(`/rbac/admin/users/${userId}/roles`, {
      data: { role_ids: roleIds },
    });
    return res.data;
  },
};
