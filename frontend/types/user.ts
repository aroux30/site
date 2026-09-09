export interface User {
  id: string;
  firstName: string;
  lastName: string;
  fullName: string;
  email: string;
  phone: string;
  avatar?: string;
  role: UserRole;
  isActive: boolean;
  isEmailVerified: boolean;
  isPhoneVerified: boolean;

  // Profile
  nationalId?: string;
  birthDate?: string;
  gender?: "male" | "female" | "other";

  // Addresses
  addresses: UserAddress[];
  defaultAddressId?: string;

  // Wallet
  walletBalance: number;

  // Timestamps
  createdAt: string;
  updatedAt: string;
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

export interface LoginRequest {
  phone: string;
  password: string;
}

export interface RegisterRequest {
  firstName: string;
  lastName: string;
  phone: string;
  email?: string;
  password: string;
  passwordConfirmation: string;
}

export interface OtpRequest {
  phone: string;
}

export interface OtpVerifyRequest {
  phone: string;
  code: string;
}

export interface UpdateProfileRequest {
  firstName?: string;
  lastName?: string;
  email?: string;
  nationalId?: string;
  birthDate?: string;
  gender?: "male" | "female" | "other";
}

export interface ChangePasswordRequest {
  currentPassword: string;
  newPassword: string;
  newPasswordConfirmation: string;
}
