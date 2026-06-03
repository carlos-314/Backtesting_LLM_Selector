import { useAuthStore } from '@/stores/auth-store';

export function TopBar() {
  const { user, logout } = useAuthStore();

  return (
    <header className="h-12 border-b border-border bg-card flex items-center justify-between px-4">
      <div className="text-xs text-muted-foreground">
        {/* Breadcrumbs will go here */}
      </div>

      <div className="flex items-center gap-3">
        {user && (
          <>
            <span className="text-xs text-muted-foreground">{user.email}</span>
            {user.avatar_url && (
              <img src={user.avatar_url} alt="" className="w-6 h-6 rounded-full" />
            )}
            <button
              onClick={logout}
              className="text-xs text-muted-foreground hover:text-destructive transition-colors"
            >
              Logout
            </button>
          </>
        )}
      </div>
    </header>
  );
}
