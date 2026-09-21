import { Outlet, Navigate } from 'react-router-dom';
import { useFreshSession } from '@/shared/hooks/useAuth';
import { postAuthPath } from '@/shared/layout/roleContext';
import logoMark from '@/assets/brand/logo.png';
import logoLabel from '@/assets/brand/label.png';

export function OnboardingLayout() {
  const { isAuthenticated, isLoading, session } = useFreshSession();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const next = postAuthPath(session);
  if (next !== '/onboarding') {
    return <Navigate to={next} replace />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,hsla(174,72%,40%,0.10),transparent_42%),radial-gradient(circle_at_bottom_left,hsla(248,78%,62%,0.10),transparent_42%)]" />
        <div className="relative w-full max-w-3xl">
        <div className="text-center mb-7">
          <div className="inline-flex items-center justify-center gap-2.5 mb-3">
            <img
              src={logoMark}
              alt=""
              className="h-9 w-auto max-w-[40px] object-contain object-center select-none"
              draggable={false}
            />
            <img
              src={logoLabel}
              alt="RefIQ"
              className="h-5 w-auto max-w-[140px] object-contain object-left select-none"
              draggable={false}
            />
          </div>
        </div>
        <div className="ui-card p-6 sm:p-8 shadow-soft">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
