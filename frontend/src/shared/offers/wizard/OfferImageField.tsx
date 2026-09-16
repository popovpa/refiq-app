import { useRef, useState } from 'react';
import { Button } from '@/shared/components/Button';
import { OfferImageCropModal } from '@/shared/offers/wizard/OfferImageCropModal';
import { OfferSquareMedia } from '@/shared/offers/wizard/OfferSquareMedia';

const MAX_FILE_BYTES = 2 * 1024 * 1024;

export function OfferImageField({
  src,
  onChange,
  onError,
}: {
  src?: string | null;
  onChange: (value: string | null) => void;
  onError: (message: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [cropSrc, setCropSrc] = useState<string | null>(null);

  const openPicker = () => inputRef.current?.click();

  const onFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      onError('Файл больше 2 МБ');
      return;
    }
    setCropSrc(URL.createObjectURL(file));
  };

  const closeCrop = () => {
    if (cropSrc) URL.revokeObjectURL(cropSrc);
    setCropSrc(null);
  };

  return (
    <div className="space-y-2">
      <div className="overflow-hidden rounded-lg border border-border bg-muted/20">
        {src ? (
          <OfferSquareMedia src={src} className="rounded-none border-0" />
        ) : (
          <div className="flex aspect-square w-full flex-col items-center justify-center gap-3 px-4 text-center">
            <p className="text-sm font-medium text-muted-foreground">Нет изображения</p>
            <Button type="button" size="sm" variant="secondary" onClick={openPicker}>
              Загрузить
            </Button>
          </div>
        )}
      </div>
      {src ? (
        <div className="flex gap-2">
          <Button type="button" size="sm" variant="secondary" onClick={openPicker}>
            Заменить
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => onChange(null)}>
            Удалить
          </Button>
        </div>
      ) : null}
      <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={onFile} />
      {cropSrc ? (
        <OfferImageCropModal
          imageSrc={cropSrc}
          onCancel={closeCrop}
          onApply={async (dataUrl) => {
            onChange(dataUrl);
            closeCrop();
          }}
        />
      ) : null}
    </div>
  );
}
