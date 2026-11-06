import { cn } from "@/lib/utils";

/**
 * The rubber-stamp mark shown on a filed checklist step. Drawn in SVG with a
 * turbulence filter so the ink reads as pressed, not printed.
 */
export function Stamp({ date, className, animate = true }: { date?: number; className?: string; animate?: boolean }) {
  const label = date
    ? new Date(date).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "2-digit" })
    : "";
  return (
    <svg
      viewBox="0 0 120 120"
      aria-hidden
      className={cn("pointer-events-none select-none text-stamp", animate && "animate-stamp", className)}
      style={{ transform: "rotate(-9deg)" }}
    >
      <defs>
        <filter id="ink" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" />
          <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.3 1.55" />
          <feComposite in="SourceGraphic" operator="in" />
        </filter>
        <path id="arcTop" d="M 22 60 A 38 38 0 0 1 98 60" />
        <path id="arcBottom" d="M 26 66 A 34 34 0 0 0 94 66" />
      </defs>
      <g filter="url(#ink)" fill="none" stroke="currentColor">
        <circle cx="60" cy="60" r="52" strokeWidth="5" />
        <circle cx="60" cy="60" r="45" strokeWidth="2" />
        <text fill="currentColor" stroke="none" fontFamily="Public Sans Variable, sans-serif" fontSize="12.5" fontWeight="800" letterSpacing="3">
          <textPath href="#arcTop" startOffset="50%" textAnchor="middle">INCCORPAI</textPath>
        </text>
        <text x="60" y="66" fill="currentColor" stroke="none" textAnchor="middle" fontFamily="Public Sans Variable, sans-serif" fontSize="27" fontWeight="900" letterSpacing="1.5">
          FILED
        </text>
        <text fill="currentColor" stroke="none" fontFamily="Public Sans Variable, sans-serif" fontSize="10" fontWeight="700" letterSpacing="1.5">
          <textPath href="#arcBottom" startOffset="50%" textAnchor="middle">{label}</textPath>
        </text>
      </g>
    </svg>
  );
}
