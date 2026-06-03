import { GoogleLogin } from '@react-oauth/google';
import { useNavigate } from '@tanstack/react-router';
import { apiFetch } from '@/lib/api-client';
import { useAuthStore } from '@/stores/auth-store';
import { useState } from 'react';

interface AuthResponse {
  access_token: string;
  refresh_token: string;
}

interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string;
}

export function LoginPage() {
  const navigate = useNavigate();
  const { setAuth, setUser } = useAuthStore();
  const [error, setError] = useState<string | null>(null);

  const handleSuccess = async (response: { credential?: string }) => {
    if (!response.credential) {
      setError('No credential received from Google');
      return;
    }

    try {
      const authData = await apiFetch<AuthResponse>('/api/auth/google', {
        method: 'POST',
        body: JSON.stringify({ id_token: response.credential }),
      });

      setAuth(authData.access_token, authData.refresh_token);

      const user = await apiFetch<UserResponse>('/api/auth/me');
      setUser(user);

      navigate({ to: '/workspaces' });
    } catch (err: any) {
      setError(err.message || 'Login failed');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="bg-card border border-border rounded-md p-8 w-full max-w-sm">
        <h1 className="text-lg font-bold text-foreground mb-1">LLM Backtester</h1>
        <p className="text-xs text-muted-foreground mb-6">
          Audit, backtest, and compare LLM-generated portfolios.
        </p>

        {error && (
          <div className="bg-destructive/10 border border-destructive/30 text-destructive text-xs rounded-md p-2 mb-4">
            {error}
          </div>
        )}

        <div className="flex justify-center">
          <GoogleLogin
            onSuccess={handleSuccess}
            onError={() => setError('Google login failed')}
            theme="filled_black"
            size="large"
            width="300"
          />
        </div>

        <p className="text-[10px] text-muted-foreground mt-6 text-center">
          Research tool, not investment advice.
        </p>
      </div>
    </div>
  );
}
