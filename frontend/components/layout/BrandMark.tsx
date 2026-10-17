import { useId } from "react";

/** The Sana mark: a rounded cross with a lightning bolt, as in the prototype header. */
export function BrandMark({ className = "brand-mark" }: { className?: string }) {
  const gradientId = `sana-mark-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#23805c" />
          <stop offset=".55" stopColor="#3f9a72" />
          <stop offset="1" stopColor="#8bb79a" />
        </linearGradient>
      </defs>
      <rect x="7.2" y="1" width="9.6" height="22" rx="3.2" fill={`url(#${gradientId})`} />
      <rect x="1" y="7.2" width="22" height="9.6" rx="3.2" fill={`url(#${gradientId})`} />
      <path d="M13.4 6.2 12.6 10.6 16.6 11.4 10.6 17.8 11.4 13.4 7.4 12.6z" fill="#fff" />
    </svg>
  );
}
