import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import type { UiAddress } from "../types/messages.generated";
import { base } from "../styles/tokens";
import { define } from "../define";
import { tr, type Lang } from "../i18n";

export interface NewAddressFields {
  name: string;
  line1: string;
  area: string;
  city: string;
  pincode: string;
  phone: string;
}

const FIELDS: Array<{ key: keyof NewAddressFields; hi: string; en: string; mode?: string; max: number }> = [
  { key: "name", hi: "नाम", en: "Name", max: 80 },
  { key: "line1", hi: "मकान नंबर और गली", en: "House no. and street", max: 160 },
  { key: "area", hi: "इलाका", en: "Area", max: 80 },
  { key: "city", hi: "शहर", en: "City", max: 80 },
  { key: "pincode", hi: "पिनकोड (6 अंक)", en: "Pincode (6 digits)", mode: "numeric", max: 6 },
  { key: "phone", hi: "फ़ोन नंबर (10 अंक)", en: "Phone number (10 digits)", mode: "tel", max: 10 },
];

/**
 * Delivery address step (before the read-back and payment): the shopper's saved addresses as big
 * tap targets, plus a short form for a new one. Emits `ttb-address-select` {id, label} or
 * `ttb-address-new` {fields}; the main element turns either into a message to the assistant, which
 * is also how the same choice works by voice.
 */
export class TtbAddressPicker extends LitElement {
  static styles = [
    base,
    css`
      :host {
        display: block;
      }
      section {
        border: 3px solid var(--ttb-primary);
        border-radius: var(--ttb-radius);
        background: var(--ttb-surface);
        padding: var(--ttb-space);
      }
      h3 {
        margin: 0 0 var(--ttb-space-small);
        font-size: var(--ttb-font-large);
      }
      ul {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: var(--ttb-space-small);
      }
      li {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px 16px;
        padding: 10px 12px;
        border-radius: var(--ttb-radius-small);
        background: var(--ttb-surface-alt);
        font-size: var(--ttb-font-card);
      }
      .addr {
        flex: 1 1 220px;
        min-width: 0;
      }
      .label {
        font-weight: 800;
      }
      .text {
        color: var(--ttb-muted);
      }
      .tag {
        display: inline-block;
        margin-left: 6px;
        padding: 0 8px;
        border-radius: 8px;
        background: var(--ttb-warning-soft);
        color: var(--ttb-text);
        font-size: 11px;
        font-weight: 700;
        vertical-align: middle;
      }
      button {
        min-height: var(--ttb-tap);
      }
      .new {
        margin-top: var(--ttb-space-small);
      }
      form {
        display: grid;
        gap: var(--ttb-space-small);
        margin-top: var(--ttb-space-small);
      }
      label {
        display: grid;
        gap: 4px;
        font-size: var(--ttb-font-card);
        font-weight: 700;
      }
      input {
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
      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: var(--ttb-space-small);
      }
      [hidden] {
        display: none !important;
      }
      @media all {
        section {
          padding: 12px;
        }
        h3 {
          font-size: 22px;
        }
        li {
          flex-direction: column;
          align-items: stretch;
        }
        .addr {
          flex: none; /* in a column, the 220px row basis would become a height */
        }
        li button,
        .new,
        .actions button {
          width: 100%;
        }
        .actions {
          flex-direction: column;
        }
        input {
          font-size: 18px; /* at least 16 px, or phone browsers zoom the page on focus */
        }
      }
      .err {
        margin: 0;
        color: var(--ttb-danger);
        font-weight: 700;
      }
    `,
  ];

  @property({ attribute: false }) addresses: UiAddress[] = [];
  /** The shopper's default address: listed first and marked. */
  @property({ attribute: false }) preferredId: string | null = null;
  @property() language: Lang = "hi";
  @property({ type: Boolean }) disabled = false;
  @state() private adding = false;
  @state() private error = "";
  @state() private form: NewAddressFields = { name: "", line1: "", area: "", city: "", pincode: "", phone: "" };

  private select(a: UiAddress) {
    this.dispatchEvent(
      new CustomEvent("ttb-address-select", { detail: { id: a.id, label: a.label }, bubbles: true, composed: true }),
    );
  }

  private validate(): string {
    const L = this.language;
    const f = this.form;
    if (Object.values(f).some((v) => !v.trim())) return tr(L, "कृपया सभी जानकारी भरिए।", "Please fill in every field.");
    if (!/^[1-9][0-9]{5}$/.test(f.pincode.trim())) return tr(L, "पिनकोड 6 अंकों का होना चाहिए।", "Pincode must be 6 digits.");
    if (!/^[6-9][0-9]{9}$/.test(f.phone.replace(/[\s-]/g, ""))) {
      return tr(L, "फ़ोन नंबर 10 अंकों का होना चाहिए।", "Phone number must be 10 digits.");
    }
    return "";
  }

  private submit(e: Event) {
    e.preventDefault();
    this.error = this.validate();
    if (this.error) return;
    const fields = Object.fromEntries(Object.entries(this.form).map(([k, v]) => [k, v.trim()])) as unknown as NewAddressFields;
    this.dispatchEvent(new CustomEvent("ttb-address-new", { detail: { fields }, bubbles: true, composed: true }));
    this.adding = false;
  }

  private renderForm() {
    const L = this.language;
    return html`
      <form @submit=${this.submit} novalidate ?hidden=${!this.adding}>
        ${FIELDS.map(
          (f) => html`
            <label>
              ${tr(L, f.hi, f.en)}
              <input
                type="text"
                name=${f.key}
                inputmode=${f.mode ?? "text"}
                maxlength=${f.max}
                autocomplete="off"
                .value=${this.form[f.key]}
                @input=${(e: Event) => (this.form = { ...this.form, [f.key]: (e.target as HTMLInputElement).value })}
              />
            </label>
          `,
        )}
        ${this.error ? html`<p class="err" role="alert">${this.error}</p>` : nothing}
        <div class="actions">
          <button class="primary" type="submit" ?disabled=${this.disabled}>${tr(L, "इस पते पर भेजें", "Deliver to this address")}</button>
          <button type="button" @click=${() => (this.adding = false)}>${tr(L, "रद्द करें", "Cancel")}</button>
        </div>
      </form>
    `;
  }

  render() {
    const L = this.language;
    return html`
      <section role="region" aria-label=${tr(L, "डिलीवरी का पता", "Delivery address")} lang=${L}>
        <h3>${tr(L, "किस पते पर भेजें?", "Where should we deliver?")}</h3>
        <ul>
          ${[...this.addresses].sort((x, y) => Number(y.id === this.preferredId) - Number(x.id === this.preferredId)).map(
            (a) => html`
              <li>
                <div class="addr">
                  <div class="label">${a.label}${a.id === this.preferredId ? html` <span class="tag">${tr(L, "डिफ़ॉल्ट", "Default")}</span>` : nothing}</div>
                  <div class="text">${a.text}</div>
                </div>
                <button class="primary" type="button" ?disabled=${this.disabled} @click=${() => this.select(a)}>
                  ${tr(L, "यहाँ भेजें", "Deliver here")}
                </button>
              </li>
            `,
          )}
        </ul>
        <button class="new" type="button" ?hidden=${this.adding} ?disabled=${this.disabled} @click=${() => (this.adding = true)}>
          + ${tr(L, "नया पता", "New address")}
        </button>
        ${this.renderForm()}
      </section>
    `;
  }
}

define("ttb-address-picker", TtbAddressPicker);

declare global {
  interface HTMLElementTagNameMap {
    "ttb-address-picker": TtbAddressPicker;
  }
}
