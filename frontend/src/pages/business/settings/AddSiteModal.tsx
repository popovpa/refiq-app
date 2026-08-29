import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { siteHostname } from '@/shared/links/destinationUrl';

export function AddSiteModal({
  pending,
  error,
  onClose,
  onSubmit,
}: {
  pending?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (payload: { url: string; name?: string }) => void;
}) {
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [nameTouched, setNameTouched] = useState(false);
  const suggested = siteHostname(url);

  useEffect(() => {
    if (!nameTouched) setName(suggested);
  }, [suggested, nameTouched]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmedUrl = url.trim();
    if (!trimmedUrl) return;
    const trimmedName = name.trim();
    onSubmit({
      url: trimmedUrl,
      name: trimmedName && trimmedName !== suggested ? trimmedName : undefined,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <form className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft" onSubmit={submit}>
        <div className="flex items-start justify-between gap-3">
          <h2 className="ui-section-title">Добавить сайт</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>

        <label className="block">
          <span className="ui-label">Адрес сайта *</span>
          <input
            className="ui-input"
            autoFocus
            placeholder="https://shop.example.ru"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
        </label>
        <label className="block">
          <span className="ui-label">Название</span>
          <input
            className="ui-input"
            placeholder="Интернет-магазин"
            value={name}
            onChange={(event) => {
              setNameTouched(true);
              setName(event.target.value);
            }}
          />
        </label>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button type="submit" disabled={!url.trim() || pending}>
            {pending ? 'Добавление...' : 'Добавить'}
          </Button>
        </div>
      </form>
    </div>
  );
}
