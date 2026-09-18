# ADR: Financial architecture

Date: 2026-09-18

## Status

Accepted

## Invariants

1. One User may be Business and Partner at the same time. `User.accountType` is not a source of truth.
2. Business is a tenant. PartnerProfile is a separate participation context.
3. LegalEntity is first-class and separate from User. Business and PartnerProfile may point to the same or different LegalEntity.
4. RefIQ does not custody user funds. There is no wallet, stored balance, or pooled partner money.
5. Business is the payer of Partner. Money flow: Business → T-Bank → Partner.
6. Business → RefIQ (SaaS) and Business → Partner (settlement) are separate financial contours.
7. Currency is RUB only.
8. Partner payout is allowed only for NPD (self-employed), sole proprietor (IP), or legal entity. Ordinary individuals cannot receive payouts.
9. `FINANCIAL_TRANSACTIONS_ENABLED=false` is the default. Test mode runs the full domain without live T-Bank money movement.
10. `active_role` is session UX context only. Financial authorization uses membership/profile + resource ownership.
11. Self-deal is forbidden when Offer.business.legal_entity_id equals PartnerProfile.legal_entity_id. Same-user membership guard remains as defense-in-depth.
12. Business-owned promotion continues with `partner_id = NULL` and commission = 0.

## State machines

### Subscription

`TRIAL` (14 days) → `ACTIVE` ↔ `PAST_DUE` (30-day grace) → `SUSPENDED`  
`CANCELLED` keeps history. Suspended businesses can still log in, see debt, pay, and settle partner payouts.

### Conversion

`pending` → `approved` | `rejected` | `reversed`

### Commission

`pending` → `hold` (if holdPeriodDays > 0) → `available` → `payout_pending` → `paid`  
Also `cancelled` and `reversed`. Historical snapshots are immutable. Paid commissions reversed after payout become a manual-review event (`REVERSED_AFTER_PAYOUT`) without automatic clawback.

### Payout

`created` / `awaiting_confirmation` → `processing` → `paid`  
`overdue` after 3 days without Business confirmation.  
`failed` / `manual_review` / `reconciliation_required` for exception paths.  
Traffic suspension applies only to overdue Business-fault obligations, not T-Bank or Partner errors.

AUTO_PAYOUT is stored on `BusinessBillingProfile.auto_payout_enabled` and defaults to `false`. MVP always requires Business confirmation.

## Providers

- Test mode: `TestFinancialProvider`
- Live: `TBankPaymentProvider` (official Acquiring `v2/Init`, `v2/GetState`, `v2/Cancel`) and `TBankPayoutProvider` (official e2c `Init`, `Payment`, `GetState`)
- Switching to LIVE replaces the test provider. Domain logic does not change.
