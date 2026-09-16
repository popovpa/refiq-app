import { useState } from 'react';
import { Outlet, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/shared/hooks/useAuth';
import { hasRoleContext, postAuthPath } from '@/shared/layout/roleContext';
import { cn } from '@/shared/utils/cn';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

export function AppLayout() {
  const { isAuthenticated, isLoading, session } = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const isProfile = location.pathname === '/profile';
  const isPartnerOfferDetail = /^\/partner\/offers\/[^/]+$/.test(location.pathname);
  const isBusinessOverview = location.pathname === '/business';
  const isOfferWizard = /\/business\/offers\/(new|[^/]+\/edit)$/.test(location.pathname);
  const isFixedHeightPage = isProfile || isPartnerOfferDetail || isBusinessOverview;

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  const home = postAuthPath(session);
  if (home === '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }
  if (location.pathname.startsWith('/business') && !hasRoleContext(session?.user.roles, 'business')) {
    return <Navigate to={home} replace />;
  }
  if (location.pathname.startsWith('/partner') && !hasRoleContext(session?.user.roles, 'partner')) {
    return <Navigate to={home} replace />;
  }

  return (
    <div className="h-screen flex bg-background overflow-hidden">
      <Sidebar mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        <Header onOpenMobileMenu={() => setMobileOpen(true)} />
        <main
          className={cn(
            'flex-1 min-h-0 p-4 lg:p-6',
            isFixedHeightPage ? 'overflow-hidden max-lg:overflow-auto flex flex-col' : 'overflow-auto',
          )}
        >
          <div
            className={cn(
              'mx-auto w-full',
              !isOfferWizard && 'max-w-content',
              isFixedHeightPage && 'flex-1 min-h-0 flex flex-col overflow-hidden',
            )}
          >
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
