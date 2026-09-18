import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthLayout } from '@/layouts/AuthLayout';
import { OnboardingLayout } from '@/layouts/OnboardingLayout';
import { AppLayout } from '@/layouts/AppLayout';
import { LoginPage } from '@/pages/auth/LoginPage';
import { RegisterPage } from '@/pages/auth/RegisterPage';
import { ForgotPasswordPage } from '@/pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from '@/pages/auth/ResetPasswordPage';
import { ConfirmAccountPage } from '@/pages/auth/ConfirmAccountPage';
import { OnboardingPage } from '@/pages/auth/OnboardingPage';
import { BusinessDashboard } from '@/pages/business/Dashboard';
import { BusinessOffers } from '@/pages/business/Offers';
import { BusinessOfferNew } from '@/pages/business/OfferNew';
import { BusinessOfferEdit } from '@/pages/business/OfferEdit';
import { BusinessOfferDetail } from '@/pages/business/OfferDetail';
import { BusinessPartners } from '@/pages/business/Partners';
import { BusinessConversions } from '@/pages/business/Conversions';
import { BusinessPayouts } from '@/pages/business/Payouts';
import { BusinessBilling } from '@/pages/business/Billing';
import { BusinessSettings } from '@/pages/business/Settings';
import { PartnerDashboard } from '@/pages/partner/Dashboard';
import { PartnerOffers } from '@/pages/partner/Offers';
import { PartnerOfferDetail } from '@/pages/partner/OfferDetail';
import { PartnerLinks } from '@/pages/partner/Links';
import { PartnerConversions } from '@/pages/partner/Conversions';
import { PartnerPayouts } from '@/pages/partner/Payouts';
import { PartnerSettings } from '@/pages/partner/Settings';
import { ProfilePage } from '@/pages/ProfilePage';
import { NotificationsPage } from '@/pages/NotificationsPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { ToastProvider } from '@/shared/components/Toast';

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/confirm-account" element={<ConfirmAccountPage />} />
        </Route>
        <Route element={<OnboardingLayout />}>
          <Route path="/onboarding" element={<OnboardingPage />} />
        </Route>
        <Route element={<AppLayout />}>
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/business" element={<BusinessDashboard />} />
          <Route path="/business/offers" element={<BusinessOffers />} />
          <Route path="/business/offers/new" element={<BusinessOfferNew />} />
          <Route path="/business/offers/:id/edit" element={<BusinessOfferEdit />} />
          <Route path="/business/offers/:id" element={<BusinessOfferDetail />} />
          <Route path="/business/partners" element={<BusinessPartners />} />
          <Route path="/business/conversions" element={<BusinessConversions />} />
          <Route path="/business/payouts" element={<BusinessPayouts />} />
          <Route path="/business/billing" element={<BusinessBilling />} />
          <Route path="/business/settings" element={<BusinessSettings />} />
          <Route path="/partner" element={<PartnerDashboard />} />
          <Route path="/partner/offers" element={<PartnerOffers />} />
          <Route path="/partner/offers/:id" element={<PartnerOfferDetail />} />
          <Route path="/partner/links" element={<PartnerLinks />} />
          <Route path="/partner/conversions" element={<PartnerConversions />} />
          <Route path="/partner/payouts" element={<PartnerPayouts />} />
          <Route path="/partner/settings" element={<PartnerSettings />} />
        </Route>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </ToastProvider>
  );
}
