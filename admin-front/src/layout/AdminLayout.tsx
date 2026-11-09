import { useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

export function AdminLayout() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return (
    <div className="h-screen flex bg-background overflow-hidden">
      <div className="hidden lg:flex">
        <Sidebar />
      </div>
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-nav-shade/40" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 z-50">
            <Sidebar onClose={() => setMobileOpen(false)} />
          </div>
        </div>
      )}
      <div className="flex-1 flex flex-col min-w-0">
        <Header onOpenMenu={() => setMobileOpen(true)} />
        <main className="flex-1 overflow-auto px-4 py-5 sm:px-6 lg:px-8 lg:py-6">
          <div className="max-w-content mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
