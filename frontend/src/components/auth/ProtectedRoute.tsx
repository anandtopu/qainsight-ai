import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import LoadingSpinner from '../ui/LoadingSpinner';

export default function ProtectedRoute() {
  const hasHydrated = useAuthStore((s) => s._hasHydrated);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const token = useAuthStore((s) => s.token);
  const fetchUser = useAuthStore((s) => s.fetchUser);
  const location = useLocation();
  const [validating, setValidating] = useState(false);

  useEffect(() => {
    // Once the persist store has hydrated, if a token exists but the session
    // flag was not persisted (page refresh), re-validate the token silently.
    if (hasHydrated && token && !isAuthenticated) {
      setValidating(true);
      fetchUser().finally(() => setValidating(false));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasHydrated]);

  // Still loading localStorage — show nothing so there's no redirect flash.
  if (!hasHydrated || validating) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-950">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
