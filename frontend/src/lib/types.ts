/**
 * Tipos compartidos entre vistas y dominios (espejo de los DTOs del backend).
 */

export type Role = "viewer" | "analyst" | "admin";

export interface SessionUser {
  id: string;
  email: string;
  role: Role;
  full_name: string | null;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: SessionUser;
}
