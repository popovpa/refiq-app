import { Download } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';

export function TrackingLinkQrBlock({
  imageSrc,
  downloadEndpoint,
  shortCode,
}: {
  imageSrc: string;
  downloadEndpoint: string;
  shortCode: string;
}) {
  const { addToast } = useToast();

  const download = async () => {
    try {
      await api.download(downloadEndpoint, `${shortCode}.png`);
    } catch {
      addToast('Не удалось скачать QR-код', 'error');
    }
  };

  return (
    <div className="space-y-2">
      <img
        src={imageSrc}
        alt="QR-код ссылки"
        className="h-28 w-28 rounded-md border border-border/70 bg-white p-1 object-contain"
      />
      <Button type="button" size="sm" variant="secondary" onClick={download}>
        <Download size={14} /> Скачать QR-код
      </Button>
    </div>
  );
}
