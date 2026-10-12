import { LitElement, css, html } from "lit";
import { property, state } from "lit/decorators.js";
import { base } from "../styles/tokens";
import { define } from "../define";

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
      input::placeholder {
        color: var(--ttb-muted);
      }
    `,
  ];

  @property({ type: Boolean }) disabled = false;
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
          <span class="sr-only">लिखकर बताइए / Type your message</span>
          <input
            type="text"
            lang="hi"
            maxlength="500"
            autocomplete="off"
            placeholder="लिखकर बताइए… / Type here…"
            .value=${this.value}
            ?disabled=${this.disabled}
            @input=${(e: Event) => (this.value = (e.target as HTMLInputElement).value)}
          />
        </label>
        <button class="primary" type="submit" ?disabled=${this.disabled || !this.value.trim()}>भेजें / Send</button>
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
