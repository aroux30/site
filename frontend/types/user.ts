export interface User {
  id: string;
  phone: string;
  email?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  national_code?: string | null;
  birth_date?: string | null;
  avatar_url?: string | null;
  gender?: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;

  // Convenience & legacy compatibility fields
  name?: string | null;
  firstName?: string | null;
  lastName?: string | null;
  fullName?: string | null;
  avatar?: string;
  role?: UserRole;
  isActive?: boolean;
  isEmailVerified?: boolean;
  isPhoneVerified?: boolean;

  // Profile extensions
  nationalId?: string;
  birthDate?: string;

  // Addresses
  addresses?: UserAddress[];
  defaultAddressId?: string;

  // Wallet & Gamification
  walletBalance?: number;
  loyalty_points?: number;
  loyaltyPoints?: number;
  loyalty_tier?: "bronze" | "silver" | "gold" | "platinum" | string;
  loyaltyTier?: "bronze" | "silver" | "gold" | "platinum" | string;

  // Timestamps
  createdAt?: string;
  updatedAt?: string;
  lastLoginAt?: string;
}

export type UserRole = "customer" | "admin" | "vendor" | "support";

export interface UserAddress {
  id: string;
  title: string;
  firstName: string;
  lastName: string;
  phone: string;
  province: string;
  city: string;
  address: string;
  postalCode: string;
  isDefault: boolean;
  latitude?: number;
  longitude?: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserProfileResponse {
  id: string;
  phone: string;
  email?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  national_code?: string | null;
  birth_date?: string | null;
  avatar_url?: string | null;
  gender?: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface LoginRequest {
  phone: string;
  password: string;
}

export interface RegisterRequest {
  phone: string;
  password: string;
  first_name: string;
  last_name: string;
  // Optional aliases for compatibility
  firstName?: string;
  lastName?: string;
  email?: string;
  passwordConfirmation?: string;
}

export interface OtpRequest {
  phone: string;
}

export interface OtpResponse {
  status?: string;
  message?: string;
  expires_in?: number;
  code?: string;
  [key: string]: unknown;
}

export interface OtpVerifyRequest {
  phone: string;
  code: string;
}

export interface UpdateProfileRequest {
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  national_code?: string | null;
  birth_date?: string | null;
  avatar_url?: string | null;
  gender?: string | null;
  // Legacy aliases
  firstName?: string;
  lastName?: string;
  nationalId?: string;
  birthDate?: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
  // Legacy aliases
  currentPassword?: string;
  newPasswordConfirmation?: string;
}

export interface MessageResponse {
  message: string;
}
