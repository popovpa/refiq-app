import { describe, expect, it } from 'vitest';
import { businessFilterTriggerLabel } from './businessFilter';

describe('businessFilterTriggerLabel', () => {
  it('shows the all-businesses label when nothing is selected', () => {
    expect(businessFilterTriggerLabel()).toBe('Все бизнесы');
    expect(businessFilterTriggerLabel('')).toBe('Все бизнесы');
    expect(businessFilterTriggerLabel('   ')).toBe('Все бизнесы');
  });

  it('shows a placeholder while the selected business name is loading', () => {
    expect(businessFilterTriggerLabel(undefined, '123')).toBe('…');
  });

  it('shows the selected business name', () => {
    expect(businessFilterTriggerLabel('Acme', '123')).toBe('Acme');
  });
});
