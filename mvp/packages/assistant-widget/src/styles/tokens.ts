import { css } from "lit";

/**
 * Design tokens, from the phone-app design reference: deep forest green and amber on a warm
 * off-white, Bricolage Grotesque for headings and Instrument Sans (+ Noto Sans Devanagari) for text.
 * Light only: the assistant sits on the forest-green page, with light cards for the cart, address,
 * read-back and goal list.
 *
 * Contrast: ink #14201A on #FFFFFF ≈ 17:1; muted #4E5D55 on #FFFFFF ≈ 7.2:1; white on forest
 * #0F3D2E ≈ 12.6:1; ink on amber #F4B63B ≈ 9.9:1; #B7CBC1 on forest ≈ 6.4:1.
 *
 * Hosts can override any `--ttb-*` property on the element.
 */
export const tokens = css`
  :host {
    --ttb-font: "Instrument Sans", "Noto Sans Devanagari", "Noto Sans", system-ui, sans-serif;
    --ttb-font-display: "Bricolage Grotesque", "Noto Sans Devanagari", system-ui, sans-serif;
    --ttb-font-body: 15px;
    --ttb-font-card: 15px;
    --ttb-font-large: 18px;
    --ttb-font-xl: 24px;
    --ttb-font-small: 13px;
    --ttb-line: 1.4;

    --ttb-tap: 44px;
    --ttb-tap-large: 56px;
    --ttb-radius: 18px;
    --ttb-radius-small: 12px;
    --ttb-space: 14px;
    --ttb-space-small: 8px;

    --ttb-forest: #0f3d2e;
    --ttb-forest-2: #174a38;
    --ttb-amber: #f4b63b;
    --ttb-on-forest: #b7cbc1;

    --ttb-bg: #f3f2ec;
    --ttb-surface: #ffffff;
    --ttb-surface-alt: #eeede5;
    --ttb-text: #14201a;
    --ttb-muted: #4e5d55;
    --ttb-border: #e4e2d8;
    --ttb-primary: #0f3d2e;
    --ttb-on-primary: #ffffff;
    --ttb-primary-soft: #ddefe5;
    --ttb-success: #0b6b45;
    --ttb-on-success: #ffffff;
    --ttb-success-soft: #ddefe5;
    --ttb-warning-soft: #fbefd0;
    --ttb-danger: #b42318;
    --ttb-on-danger: #ffffff;
    --ttb-translation: #3f4a5a;
    --ttb-translation-bg: #eef2f7;
    --ttb-focus: #f4b63b;
    --ttb-shadow: 0 2px 10px rgba(20, 32, 26, 0.12);

    color-scheme: light;
  }
`;

/** Shared base styles for every widget sub-component. */
export const base = css`
  :host {
    font-family: var(--ttb-font);
    font-size: var(--ttb-font-body);
    line-height: var(--ttb-line);
    color: var(--ttb-text);
  }
  * {
    box-sizing: border-box;
  }
  button {
    font: inherit;
    min-width: var(--ttb-tap);
    min-height: var(--ttb-tap);
    padding: 8px 18px;
    border-radius: var(--ttb-radius-small);
    border: 1.5px solid var(--ttb-primary);
    background: var(--ttb-surface);
    color: var(--ttb-primary);
    font-weight: 700;
    cursor: pointer;
  }
  button.primary {
    background: var(--ttb-primary);
    color: var(--ttb-on-primary);
  }
  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  button:focus-visible,
  input:focus-visible,
  textarea:focus-visible,
  [tabindex]:focus-visible {
    outline: 3px solid var(--ttb-focus);
    outline-offset: 2px;
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }
  @media (prefers-reduced-motion: reduce) {
    * {
      animation: none !important;
      transition: none !important;
    }
  }
`;

/** Rupee formatting with Indian digit grouping (₹1,016). */
export function rupees(n: number): string {
  return `₹${Math.round(n).toLocaleString("en-IN")}`;
}
