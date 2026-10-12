import { css } from "lit";

/**
 * Design tokens (Constitution IV, elder-first):
 * - card text ≥ 20 px, body ≥ 18 px, tap targets ≥ 48×48 px;
 * - warm, calm palette; every text/background pair below meets WCAG AA (most meet AAA);
 * - dark mode via prefers-color-scheme.
 *
 * Contrast notes (light): text #2B1D12 on #FFF8EE ≈ 15.9:1; muted #5C4636 on #FFF8EE ≈ 8.6:1;
 * white on primary #9A3412 ≈ 7.3:1; white on success #166534 ≈ 7.1:1; translation #3F4A5A on
 * #FFFFFF ≈ 9:1. Dark: #FBEFE3 on #1C1410 ≈ 16:1; #1C1410 on primary #FDBA74 ≈ 10:1.
 *
 * Hosts can override any `--ttb-*` property on the element.
 */
export const tokens = css`
  :host {
    --ttb-font: "Noto Sans Devanagari", "Noto Sans", "Mangal", "Nirmala UI", system-ui, sans-serif;
    --ttb-font-body: 18px;
    --ttb-font-card: 20px;
    --ttb-font-large: 24px;
    --ttb-font-xl: 30px;
    --ttb-font-small: 16px;
    --ttb-line: 1.5;

    --ttb-tap: 48px;
    --ttb-tap-large: 64px;
    --ttb-radius: 16px;
    --ttb-radius-small: 10px;
    --ttb-space: 16px;
    --ttb-space-small: 8px;

    --ttb-bg: #fff8ee;
    --ttb-surface: #ffffff;
    --ttb-surface-alt: #fdf0dc;
    --ttb-text: #2b1d12;
    --ttb-muted: #5c4636;
    --ttb-border: #d9c3ae;
    --ttb-primary: #9a3412;
    --ttb-on-primary: #ffffff;
    --ttb-primary-soft: #fde4cc;
    --ttb-success: #166534;
    --ttb-on-success: #ffffff;
    --ttb-success-soft: #dcf2e1;
    --ttb-warning-soft: #fff1c2;
    --ttb-danger: #9f1239;
    --ttb-on-danger: #ffffff;
    --ttb-translation: #3f4a5a;
    --ttb-translation-bg: #eef2f7;
    --ttb-focus: #1d4ed8;
    --ttb-shadow: 0 2px 10px rgba(60, 35, 15, 0.12);

    color-scheme: light dark;
  }

  @media (prefers-color-scheme: dark) {
    :host {
      --ttb-bg: #1c1410;
      --ttb-surface: #2a1f18;
      --ttb-surface-alt: #352820;
      --ttb-text: #fbefe3;
      --ttb-muted: #d9c3ae;
      --ttb-border: #6b5544;
      --ttb-primary: #fdba74;
      --ttb-on-primary: #1c1410;
      --ttb-primary-soft: #4a2c18;
      --ttb-success: #86efac;
      --ttb-on-success: #0f2a18;
      --ttb-success-soft: #173823;
      --ttb-warning-soft: #44380f;
      --ttb-danger: #fda4af;
      --ttb-on-danger: #2a0a12;
      --ttb-translation: #cfd8e3;
      --ttb-translation-bg: #26303b;
      --ttb-focus: #93c5fd;
      --ttb-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
    }
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
    padding: 8px 20px;
    border-radius: var(--ttb-radius-small);
    border: 2px solid var(--ttb-primary);
    background: var(--ttb-surface);
    color: var(--ttb-primary);
    font-weight: 600;
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
    outline: 4px solid var(--ttb-focus);
    outline-offset: 3px;
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
