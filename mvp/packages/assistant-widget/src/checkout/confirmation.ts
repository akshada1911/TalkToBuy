import { LitElement, css, html, nothing } from "lit";
import { property } from "lit/decorators.js";
import type { OrderMsg } from "../types/messages.generated";
import { base } from "../styles/tokens";
import { define } from "../define";
import { tr, type Lang } from "../i18n";

/** Order confirmation (FR-021, T069): order ID and delivery time; family notice (FR-033). */
export class TtbConfirmation extends LitElement {
  static styles = [
    base,
    css`
      :host {
        display: block;
      }
      section {
        border: 3px solid var(--ttb-success);
        border-radius: var(--ttb-radius);
        background: var(--ttb-success-soft);
        padding: var(--ttb-space);
        font-size: var(--ttb-font-card);
      }
      h3 {
        margin: 0 0 var(--ttb-space-small);
        font-size: var(--ttb-font-xl);
        color: var(--ttb-text);
      }
      p {
        margin: 4px 0;
      }
      .en {
        font-size: var(--ttb-font-small);
        color: var(--ttb-translation);
      }
      .id {
        font-family: ui-monospace, monospace;
        font-weight: 700;
      }
      .when {
        font-size: var(--ttb-font-large);
        font-weight: 800;
      }
    `,
  ];

  @property({ attribute: false }) order: OrderMsg | null = null;
  @property() familyName: string | null = null;
  @property() language: Lang = "hi";

  render() {
    const o = this.order;
    if (!o && !this.familyName) return nothing;
    return html`
      <section role="status" aria-live="polite">
        ${o
          ? html`<h3>✓ ${tr(this.language, "ऑर्डर हो गया", "Order placed")}</h3>
              <p>${tr(this.language, "ऑर्डर नंबर", "Order ID")}: <span class="id">${o.order_id}</span></p>
              <p class="when" lang=${this.language}>${tr(this.language, "डिलीवरी", "Delivery")}: ${tr(this.language, o.delivery.label_hi, o.delivery.label_en)}</p>
              <p class="en" lang=${this.language}>${tr(this.language, "टेस्ट मोड, असली भुगतान नहीं", "Test mode, no real payment")}</p>`
          : nothing}
        ${this.familyName
          ? html`<p lang=${this.language}>${this.language === "en" ? `${this.familyName} has been notified in the app.` : `${this.familyName} को बता दिया गया है।`}</p>`
          : nothing}
      </section>
    `;
  }
}

define("ttb-confirmation", TtbConfirmation);

declare global {
  interface HTMLElementTagNameMap {
    "ttb-confirmation": TtbConfirmation;
  }
}
