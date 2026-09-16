import { useState } from 'react';
import Cropper, { type Area } from 'react-easy-crop';
import { Button } from '@/shared/components/Button';
import { cropImageToSquare, OFFER_IMAGE_ASPECT } from '@/shared/offers/wizard/cropImage';

export function OfferImageCropModal({
  imageSrc,
  onCancel,
  onApply,
}: {
  imageSrc: string;
  onCancel: () => void;
  onApply: (dataUrl: string) => void | Promise<void>;
}) {
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [area, setArea] = useState<Area | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apply = async () => {
    if (!area || pending) return;
    setPending(true);
    setError(null);
    try {
      await onApply(await cropImageToSquare(imageSrc, area));
    } catch {
      setError('Не удалось обрезать изображение');
      setPending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={pending ? undefined : onCancel} />
      <div className="relative ui-card w-full max-w-lg space-y-4 p-5 shadow-soft">
        <h2 className="ui-section-title">Выберите область изображения</h2>
        <div className="relative h-80 overflow-hidden rounded-lg bg-muted">
          <Cropper
            image={imageSrc}
            crop={crop}
            zoom={zoom}
            aspect={OFFER_IMAGE_ASPECT}
            onCropChange={setCrop}
            onZoomChange={setZoom}
            onCropComplete={(_, pixels) => setArea(pixels)}
          />
        </div>
        <input
          type="range"
          min={1}
          max={3}
          step={0.05}
          value={zoom}
          aria-label="Масштаб"
          className="w-full accent-primary"
          onChange={(event) => setZoom(Number(event.target.value))}
        />
        {error && <p className="text-xs text-destructive">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" disabled={pending} onClick={onCancel}>
            Отмена
          </Button>
          <Button type="button" disabled={!area || pending} onClick={apply}>
            {pending ? 'Обработка...' : 'Применить'}
          </Button>
        </div>
      </div>
    </div>
  );
}
