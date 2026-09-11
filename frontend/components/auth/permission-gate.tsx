"use client";

import React from "react";
import { useAuth } from "@/hooks/use-auth";

interface PermissionGateProps {
  /**
   * Required permission slug, e.g. "products:delete", "users:manage", "orders:write"
   */
  permission?: string;
  /**
   * Multiple permissions (all or any based on requireAll)
   */
  permissions?: string[];
  /**
   * If true, user must have all specified permissions. Default: false (any).
   */
  requireAll?: boolean;
  /**
   * Minimum role required ("admin" | "vendor" | "support" | "customer")
   */
  role?: string;
  /**
   * Content to display when authorized
   */
  children: React.ReactNode;
  /**
   * Fallback to display when unauthorized (default: null)
   */
  fallback?: React.ReactNode;
}

/**
 * Granular RBAC Permission Gate.
 * Conditionally renders UI elements based on user roles and permissions.
 */
export function PermissionGate({
  permission,
  permissions = [],
  requireAll = false,
  role,
  children,
  fallback = null,
}: PermissionGateProps) {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading || !isAuthenticated || !user) {
    return <>{fallback}</>;
  }

  // Super Admins bypass all granular permission checks
  const isSuperAdmin = Boolean(
    user.is_superuser ||
      user.role === "admin" ||
      user.roles?.includes("super_admin") ||
      user.permissions?.includes("*"),
  );

  if (isSuperAdmin) {
    return <>{children}</>;
  }

  // Check role requirement
  if (role && user.role !== role && !user.roles?.includes(role)) {
    return <>{fallback}</>;
  }

  // Check permissions requirement
  const requiredList = permission ? [permission, ...permissions] : permissions;
  if (requiredList.length === 0) {
    return <>{children}</>;
  }

  const userPerms = new Set(user.permissions || []);

  if (requireAll) {
    const hasAll = requiredList.every((p) => userPerms.has(p));
    return hasAll ? <>{children}</> : <>{fallback}</>;
  }

  const hasAny = requiredList.some((p) => userPerms.has(p));
  return hasAny ? <>{children}</> : <>{fallback}</>;
}

export default PermissionGate;
