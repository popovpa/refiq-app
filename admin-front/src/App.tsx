import { Navigate, Route, Routes } from 'react-router-dom';
import { ToastProvider } from '@/components/ui';
import { AuthProvider } from '@/lib/auth';
import { AdminLayout } from '@/layout/AdminLayout';
import { LoginPage } from '@/pages/LoginPage';
import { OverviewPage } from '@/pages/OverviewPage';
import { BusinessDetailPage, BusinessesPage, PartnerDetailPage, PartnersPage } from '@/pages/AccountPages';
import {
  OfferDetailPage,
  OffersPage,
  SiteDetailPage,
  SitesPage,
  TrackingLinkDetailPage,
  TrackingLinksPage,
} from '@/pages/PromotionPages';
import { ClickDetailPage, ClicksPage, ConversionDetailPage, ConversionsPage, PostbacksPage } from '@/pages/TrafficPages';
import {
  AuditPage,
  CommissionDetailPage,
  CommissionsPage,
  PayoutDetailPage,
  PayoutsPage,
} from '@/pages/FinancePages';
import { LegalEntitiesPage, LegalEntityDetailPage } from '@/pages/LegalEntitiesPages';
import { TracePage } from '@/pages/TracePage';
import { NotFoundPage } from '@/pages/NotFoundPage';

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<AdminLayout />}>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/businesses" element={<BusinessesPage />} />
            <Route path="/businesses/:id" element={<BusinessDetailPage />} />
            <Route path="/partners" element={<PartnersPage />} />
            <Route path="/partners/:id" element={<PartnerDetailPage />} />
            <Route path="/sites" element={<SitesPage />} />
            <Route path="/sites/:id" element={<SiteDetailPage />} />
            <Route path="/offers" element={<OffersPage />} />
            <Route path="/offers/:id" element={<OfferDetailPage />} />
            <Route path="/tracking-links" element={<TrackingLinksPage />} />
            <Route path="/tracking-links/:id" element={<TrackingLinkDetailPage />} />
            <Route path="/clicks" element={<ClicksPage />} />
            <Route path="/clicks/:rqcid" element={<ClickDetailPage />} />
            <Route path="/conversions" element={<ConversionsPage />} />
            <Route path="/conversions/:id" element={<ConversionDetailPage />} />
            <Route path="/postbacks" element={<PostbacksPage />} />
            <Route path="/commissions" element={<CommissionsPage />} />
            <Route path="/commissions/:id" element={<CommissionDetailPage />} />
            <Route path="/payouts" element={<PayoutsPage />} />
            <Route path="/payouts/:id" element={<PayoutDetailPage />} />
            <Route path="/legal-entities" element={<LegalEntitiesPage />} />
            <Route path="/legal-entities/:id" element={<LegalEntityDetailPage />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/trace/:rqcid" element={<TracePage />} />
            <Route path="/admin/trace/:rqcid" element={<TracePage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ToastProvider>
    </AuthProvider>
  );
}
