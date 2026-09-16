export const OFFER_IMAGE_ASPECT = 1;
export const OFFER_IMAGE_OUTPUT_SIZE = 1024;

export type CropArea = {
  x: number;
  y: number;
  width: number;
  height: number;
};

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('image'));
    image.src = src;
  });
}

export async function cropImageToSquare(
  imageSrc: string,
  croppedAreaPixels: CropArea,
  outputSize = OFFER_IMAGE_OUTPUT_SIZE,
): Promise<string> {
  const image = await loadImage(imageSrc);
  const side = Math.min(croppedAreaPixels.width, croppedAreaPixels.height);
  const canvas = document.createElement('canvas');
  canvas.width = outputSize;
  canvas.height = outputSize;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('canvas');
  ctx.drawImage(
    image,
    croppedAreaPixels.x,
    croppedAreaPixels.y,
    side,
    side,
    0,
    0,
    outputSize,
    outputSize,
  );
  return canvas.toDataURL('image/jpeg', 0.85);
}
