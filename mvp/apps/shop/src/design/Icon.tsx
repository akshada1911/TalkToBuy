import { SPRITE } from "./sprite";

/** The icon sprite, rendered once at the top of the app. */
export function Sprite() {
  return (
    <svg
      width="0"
      height="0"
      style={{ position: "absolute" }}
      aria-hidden="true"
      focusable="false"
      dangerouslySetInnerHTML={{ __html: `<defs>${SPRITE}</defs>` }}
    />
  );
}

interface IconProps {
  /** Symbol id from the sprite, e.g. "i-mic" or "ic-milk". */
  name: string;
  size?: number;
  /** Product illustrations (ic-*) are drawn in a 48 px box and keep their own colours. */
  stroke?: number;
  className?: string;
}

/** UI icons are line icons drawn with the current text colour. */
export function Icon({ name, size = 22, stroke = 2, className }: IconProps) {
  const product = name.startsWith("ic-");
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox={product ? "0 0 48 48" : "0 0 24 24"}
      fill={product ? undefined : "none"}
      stroke={product ? undefined : "currentColor"}
      strokeWidth={product ? undefined : stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <use href={`#${name}`} />
    </svg>
  );
}
