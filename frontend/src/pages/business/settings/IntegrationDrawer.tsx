import { useEffect } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { PostbackPanel } from './PostbackPanel';
import { SdkPanel } from './SdkPanel';
import type { IntegrationKind } from './types';
import { websiteHost } from './types';

export function IntegrationDrawer({
  kind,
  website,
  onClose,
}: {
  kind: IntegrationKind;
  website?: string;
  onClose: () => void;
}) {
  const domain = websiteHost(website) || 'example.com';
  const title = kind === 'postback' ? 'Postback / S2S' : 'JavaScript SDK';

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <aside
        className={cn(
          'relative ui-card w-full h-full shadow-soft flex flex-col border-l',
          kind === 'postback' ? 'max-w-xl' : 'max-w-lg',
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby="integration-drawer-title"
      >
        <div className="flex items-start justify-between gap-3 p-5 border-b border-border/70">
          <h2 id="integration-drawer-title" className="ui-section-title">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Закрыть"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5 space-y-5">
          {kind === 'postback' ? <PostbackPanel /> : <SdkPanel domain={domain} />}
        </div>
      </aside>
    </div>
  );
}
