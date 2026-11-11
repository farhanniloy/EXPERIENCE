"use client";

import Image, { ImageProps } from "next/image";
import { useState } from "react";

type Props = Omit<ImageProps, "src" | "onError"> & {
  src: string;
  fallback: string;
};

export function FallbackImage({ src, fallback, alt, ...props }: Props) {
  const [failedSource, setFailedSource] = useState<string | null>(null);

  return (
    <Image
      {...props}
      alt={alt}
      src={failedSource === src ? fallback : src}
      unoptimized
      onError={() => {
        if (src !== fallback) setFailedSource(src);
      }}
    />
  );
}
