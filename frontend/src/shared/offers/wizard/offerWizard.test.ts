import { describe, expect, it } from 'vitest';
import { CATEGORIES, categoryLabel, resolveCategoryCode } from '@/shared/catalog/categories';
import { parseGeoCodes } from '@/shared/catalog/countries';
import { normalizeTrafficSource, TRAFFIC_SOURCES } from '@/shared/catalog/trafficSources';
import { DESCRIPTION_MAX, offerFormErrors, stepErrors } from '@/shared/offers/offerFormMeta';
import { blankOfferForm, formToPayload, offerToForm } from '@/shared/offers/types';
import { OFFER_IMAGE_ASPECT, OFFER_IMAGE_OUTPUT_SIZE } from '@/shared/offers/wizard/cropImage';
import { WIZARD_STEPS } from '@/shared/offers/wizard/meta';
import {
  OFFER_WIZARD_ASIDE_MID_PX,
  OFFER_WIZARD_ASIDE_PX,
  OFFER_WIZARD_ASIDE_WIDE_PX,
  OFFER_WIZARD_GRID_CLASS,
} from '@/shared/offers/wizard/OfferWizardLayout';
import { canPublishOffer, stepComplete } from '@/shared/offers/wizard/readiness';

describe('Offer wizard model', () => {
  it('has exactly four steps and no extra step', () => {
    expect(WIZARD_STEPS.map((item) => item.id)).toEqual(['basics', 'traffic', 'conversions', 'review']);
    expect(WIZARD_STEPS.map((item) => item.label)).toEqual(['Основное', 'Трафик', 'Конверсии', 'Проверка']);
  });

  it('keeps access policy on step 1 and geo on step 2', () => {
    const form = blankOfferForm();
    form.name = 'Курс';
    form.category = 'ONLINE_COURSES';
    form.description = 'Описание';
    form.access_policy = 'approval';
    expect(stepComplete(form, 'basics')).toBe(true);
    expect(stepErrors(form, 'basics').geo_countries).toBeUndefined();
    expect(stepComplete(form, 'traffic')).toBe(false);
    form.geo_countries = ['RU'];
    form.allowed_traffic = ['EMAIL'];
    expect(stepComplete(form, 'traffic')).toBe(true);
  });

  it('validates commission and hold', () => {
    const form = blankOfferForm();
    form.name = 'Курс';
    form.category = 'ONLINE_COURSES';
    form.description = 'Описание';
    form.geo_countries = ['RU'];
    form.allowed_traffic = ['EMAIL'];
    form.conversion_type = 'sale';
    form.commission_value = '0';
    expect(offerFormErrors(form, true).commission_value).toBe('Укажите размер комиссии');
    form.commission_value = '10';
    form.hold_period_days = '5';
    expect(offerFormErrors(form, true).hold_period_days).toBe('Выберите холд-период');
    form.hold_period_days = '0';
    expect(canPublishOffer(form)).toBe(true);
  });

  it('serializes a strict allowlist', () => {
    const form = blankOfferForm();
    form.name = 'Курс';
    form.category = 'ONLINE_COURSES';
    form.description = 'Описание';
    form.geo_countries = ['RU', 'KZ'];
    form.allowed_traffic = ['EMAIL'];
    form.commission_value = '10';
    const payload = formToPayload(form, 'draft');
    expect(payload.allowed_traffic).toEqual(['EMAIL']);
    expect(payload).not.toHaveProperty('forbidden_traffic');
    expect(payload.geo).toEqual(['RU', 'KZ']);
    expect(payload.hold_period_days).toBe(0);
  });

  it('maps category to one vertical and supports search labels', () => {
    expect(resolveCategoryCode('Education')).toBe('ONLINE_COURSES');
    expect(categoryLabel('ONLINE_COURSES')).toBe('Образование → Онлайн-курсы');
    const verticals = new Map(CATEGORIES.map((item) => [item.code, item.verticalCode]));
    expect(verticals.get('ANTIVIRUS')).toBe('CYBERSECURITY');
    expect(verticals.get('CRM')).toBe('SAAS');
    expect(new Set(CATEGORIES.map((item) => item.code)).size).toBe(CATEGORIES.length);
  });

  it('treats missing traffic source as prohibited', () => {
    expect(normalizeTrafficSource('email')).toBe('EMAIL');
    expect(TRAFFIC_SOURCES.some((item) => item.code === 'EMAIL')).toBe(true);
    const allowed = new Set(['EMAIL']);
    expect(allowed.has('SEO')).toBe(false);
    expect(allowed.has('SEARCH_ADS')).toBe(false);
  });

  it('parses ISO countries and drops WW', () => {
    expect(parseGeoCodes('RU, KZ, WW')).toEqual(['RU', 'KZ']);
  });

  it('keeps a shared wizard layout and square crop output', () => {
    expect(OFFER_WIZARD_ASIDE_MID_PX).toBe(320);
    expect(OFFER_WIZARD_ASIDE_PX).toBe(352);
    expect(OFFER_WIZARD_ASIDE_WIDE_PX).toBe(360);
    expect(OFFER_WIZARD_GRID_CLASS).toContain('minmax(0,1fr)_352px');
    expect(OFFER_WIZARD_GRID_CLASS).toContain('minmax(0,1fr)_360px');
    expect(OFFER_IMAGE_ASPECT).toBe(1);
    expect(OFFER_IMAGE_OUTPUT_SIZE).toBe(1024);
  });

  it('requires a trimmed offer description and keeps partner notes optional', () => {
    const form = blankOfferForm();
    form.name = 'Курс';
    form.category = 'ONLINE_COURSES';
    form.access_policy = 'approval';
    form.description = '   ';
    expect(stepErrors(form, 'basics').description).toBe('Укажите описание оффера');
    form.description = 'Онлайн-курс Python для начинающих.';
    expect(stepErrors(form, 'basics').description).toBeUndefined();
    expect(stepErrors(form, 'basics').partner_notes).toBeUndefined();
    form.description = `${'а'.repeat(DESCRIPTION_MAX)}е`;
    expect(offerFormErrors(form, true).description).toBe('Максимальная длина — 3000 символов');
  });

  it('serializes partner notes as null when empty and loads a null value into the form', () => {
    const form = blankOfferForm();
    form.name = 'Курс';
    form.category = 'ONLINE_COURSES';
    form.description = 'Онлайн-курс Python.\nПрактические задания.';
    form.partner_notes = '   ';
    form.geo_countries = ['RU'];
    form.allowed_traffic = ['EMAIL'];
    form.commission_value = '10';
    const payload = formToPayload(form, 'draft');
    expect(payload.description).toBe('Онлайн-курс Python.\nПрактические задания.');
    expect(payload.partner_notes).toBeNull();

    form.partner_notes = 'Лучше всего конвертируется аудитория 20–35 лет.';
    expect(formToPayload(form, 'draft').partner_notes).toBe('Лучше всего конвертируется аудитория 20–35 лет.');

    const loaded = offerToForm({
      name: 'Курс',
      description: 'Описание',
      partner_notes: null,
      category_code: 'ONLINE_COURSES',
      geo: 'RU',
      allowed_traffic: ['EMAIL'],
      commission_rules: [{ type: 'percent', value: 10, currency: 'RUB' }],
    });
    expect(loaded.partner_notes).toBe('');
    expect(loaded.description).toBe('Описание');
  });
});
