// Wordmark typeface, bundled so it works offline.
import "@fontsource/figtree/latin-700.css";

/** RehearseAI mark: an orange speech bubble behind a blue one carrying a tick. The blue
 *  bubble has a ring in the page background colour so it reads as sitting in front. */
export function LogoMark({ size = 32, title }: { size?: number; title?: string }) {
  return (
    <svg
      viewBox="0 0 64 56"
      width={size}
      height={(size * 56) / 64}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      className="logo-mark"
    >
      {/* back bubble */}
      <rect x="2" y="2" width="33" height="25" rx="7" fill="#F2A23A" />
      <path d="M8 24 L5.5 35 L17 26 Z" fill="#F2A23A" />
      {/* front bubble, with a background-coloured ring */}
      <g className="logo-front">
        <rect x="17" y="15" width="38" height="29" rx="8" fill="#2B5BDB" stroke="var(--logo-ring)" strokeWidth="3" />
        <path d="M44 42 L52.5 53 L51 41 Z" fill="#2B5BDB" />
        <rect x="18.5" y="16.5" width="35" height="26" rx="6.5" fill="#2B5BDB" />
        <path d="M27 30 L33 36 L45 24" fill="none" stroke="#fff" strokeWidth="4.2" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  );
}

export default function Logo() {
  return (
    <span className="logo">
      <LogoMark size={50} />
      <span className="logo-word">
        Rehearse<span className="logo-ai">AI</span>
      </span>
    </span>
  );
}
