import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { clearTokens, reviewLogin, setTokens } from "@/lib/api";

export type UserRole = "reviewer" | "admin";

export interface User {
  email: string;
  role: UserRole;
  name: string;
}

interface AuthContextType {
  user: User | null;
  login: (
    email: string,
    password: string,
    options?: { newPassword?: string; challengeSession?: string },
  ) => Promise<User | "NEW_PASSWORD_REQUIRED">;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const USER_STORAGE = "ibrary_review_user";
const PW_CHALLENGE_STORAGE = "ibrary_review_pw_challenge";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const raw = sessionStorage.getItem(USER_STORAGE);
    return raw ? (JSON.parse(raw) as User) : null;
  });

  const persistUser = (next: User) => {
    setUser(next);
    sessionStorage.setItem(USER_STORAGE, JSON.stringify(next));
  };

  const login = async (
    email: string,
    password: string,
    options?: { newPassword?: string; challengeSession?: string },
  ): Promise<User | "NEW_PASSWORD_REQUIRED"> => {
    const resp = await reviewLogin({
      email,
      password,
      new_password: options?.newPassword,
      challenge_session: options?.challengeSession,
    });

    if (resp.challenge === "NEW_PASSWORD_REQUIRED" && resp.challenge_session) {
      sessionStorage.setItem(
        PW_CHALLENGE_STORAGE,
        JSON.stringify({
          session: resp.challenge_session,
          email: email.trim().toLowerCase(),
        }),
      );
      return "NEW_PASSWORD_REQUIRED";
    }

    if (!resp.user || !resp.tokens) {
      throw new Error("Login response missing user or tokens");
    }

    setTokens(resp.tokens);
    const next: User = {
      email: resp.user.email,
      role: resp.user.role,
      name: resp.user.name,
    };
    sessionStorage.removeItem(PW_CHALLENGE_STORAGE);
    persistUser(next);
    return next;
  };

  const logout = () => {
    setUser(null);
    sessionStorage.removeItem(USER_STORAGE);
    sessionStorage.removeItem(PW_CHALLENGE_STORAGE);
    clearTokens();
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
