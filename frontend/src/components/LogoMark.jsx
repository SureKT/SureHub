export default function LogoMark({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="2.5" y="2.5" width="11" height="11" rx="1"
        stroke="var(--accent)" strokeWidth="1.5"
        transform="rotate(45 8 8)" />
      <rect x="5.5" y="5.5" width="5" height="5" rx="0.5"
        fill="var(--accent)"
        transform="rotate(45 8 8)" />
    </svg>
  )
}
