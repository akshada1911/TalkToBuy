import { LitElement, css, html } from "lit";
import { property, state } from "lit/decorators.js";
import { base } from "../styles/tokens";
import { define } from "../define";
import { tr, type Lang } from "../i18n";

/**
 * Typed alternative to speech (FR-003). Emits `ttb-text` with `{text}`; the main element sends
 * `{type:"text"}`. Max 500 characters (schema limit).
 */
export class TtbTextInput extends LitElement {
  static styles = [
    base,
    css`
      form {
        display: flex;
        gap: var(--ttb-space-small);
        align-items: stretch;
      }
      label {
        flex: 1;
        display: flex;
      }
      input {
        flex: 1;
        min-height: var(--ttb-tap);
        font: inherit;
        font-size: var(--ttb-font-card);
        padding: 8px 14px;
        border: 2px solid var(--ttb-border);
        border-radius: var(--ttb-radius-small);
        background: var(--ttb-surface);
        color: var(--ttb-text);
        min-width: 0;
      }
      @media all {
        form {
          gap: 6px;
        }
        input {
          font-size: 18px; /* at least 16 px, or phone browsers zoom the page on focus */
          padding: 8px 12px;
        }
        button {
          flex: none;
          white-space: nowrap;
          padding: 8px 16px;
        }
      }
      input::placeholder {
        color: var(--ttb-muted);
      }
      /* tone="dark": a pill field on the forest-green assistant page. */
      :host([tone="dark"]) input {
        min-height: 46px;
        padding: 0 16px;
        border: 1px solid rgba(255, 255, 255, 0.28);
        border-radius: 23px;
        background: rgba(255, 255, 255, 0.08);
        color: #ffffff;
      }
      :host([tone="dark"]) input::placeholder {
        color: rgba(255, 255, 255, 0.65);
      }
      :host([tone="dark"]) button.primary {
        min-height: 46px;
        min-width: 64px;
        border: 0;
        border-radius: 23px;
        background: #ffffff;
        color: var(--ttb-forest);
      }
      :host([tone="dark"]) button.primary:disabled {
        opacity: 0.55;
      }
    `,
  ];

  @property({ type: Boolean }) disabled = false;
  @property() language: Lang = "hi";
  @property({ reflect: true }) tone: "light" | "dark" = "light";
  @state() private value = "";

  private submit(e: Event) {
    e.preventDefault();
    const text = this.value.trim().slice(0, 500);
    if (!text || this.disabled) return;
    this.dispatchEvent(new CustomEvent("ttb-text", { detail: { text }, bubbles: true, composed: true }));
    this.value = "";
  }

  render() {
    return html`
      <form @submit=${this.submit}>
        <label>
          <span class="sr-only">${tr(this.language, "लिखकर बताइए", "Type your message")}</span>
          <input
            type="text"
            lang=${this.language}
            maxlength="500"
            autocomplete="off"
            placeholder=${tr(this.language, "लिखकर बताइए…", "Type here…")}
            .value=${this.value}
            ?disabled=${this.disabled}
            @input=${(e: Event) => (this.value = (e.target as HTMLInputElement).value)}
          />
        </label>
        <button class="primary" type="submit" ?disabled=${this.disabled || !this.value.trim()}>${tr(this.language, "भेजें", "Send")}</button>
      </form>
    `;
  }
}

define("ttb-text-input", TtbTextInput);

declare global {
  interface HTMLElementTagNameMap {
    "ttb-text-input": TtbTextInput;
  }
}
