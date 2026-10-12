import { LitElement, css, html, nothing } from "lit";
import { property } from "lit/decorators.js";
import type { ReadbackMsg } from "../types/messages.generated";
import { base, rupees } from "../styles/tokens";
import { define } from "../define";
import { tr, type Lang } from "../i18n";

/**
 * Read-back panel (FR-018, T069): large item count, total and delivery window, the same numbers
 * the assistant reads aloud. `awaitingPayment` shows the hand-off to the app's payment step.
 */
export class TtbReadback extends LitElement {
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
      dl {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 6px 16px;
        margin: 0;
        font-size: var(--ttb-font-large);
      }
      dt {
        color: var(--ttb-muted);
      }
      dd {
        margin: 0;
        font-weight: 800;
      }
      .big {
        font-size: var(--ttb-font-xl);
      }
      .en {
        font-size: var(--ttb-font-small);
        color: var(--ttb-translation);
        font-weight: 400;
        display: block;
      }
      .say {
        margin: var(--ttb-space-small) 0 0;
        font-size: var(--ttb-font-card);
      }
      .pay {
        margin: var(--ttb-space) 0 0;
        padding: 10px 14px;
        border-radius: var(--ttb-radius-small);
        background: var(--ttb-warning-soft);
        font-size: var(--ttb-font-card);
        font-weight: 700;
      }
    `,
  ];

  @property({ attribute: false }) readback: ReadbackMsg | null = null;
  @property({ type: Boolean }) awaitingPayment = false;
  @property({ type: Boolean }) showTranslation = true;
  @property() language: Lang = "hi";

  render() {
    const r = this.readback;
    if (!r) return nothing;
    return html`
      <section role="region" aria-label=${tr(this.language, "ऑर्डर की जाँच", "Order summary")} aria-live="polite">
        <h3>${tr(this.language, "ऑर्डर की जाँच कीजिए", "Please check your order")}</h3>
        <dl>
          <dt>${tr(this.language, "सामान", "Items")}</dt>
          <dd class="big">${r.item_count}</dd>
          <dt>${tr(this.language, "कुल", "Total")}</dt>
          <dd class="big">${rupees(r.total)}</dd>
          <dt>${tr(this.language, "डिलीवरी", "Delivery")}</dt>
          <dd>
            <span lang=${this.language}>${tr(this.language, r.delivery.label_hi, r.delivery.label_en)}</span>
          </dd>
          ${r.address_text
            ? html`<dt>${tr(this.language, 'पता', 'Address')}</dt>
                <dd>${r.address_text}</dd>`
            : nothing}
        </dl>
        <p class="say" lang=${this.language}>${this.language === "en" ? r.text_en || r.text_hi : r.text_hi}</p>
        ${this.language !== "en" && this.showTranslation && r.text_en
          ? html`<p class="say en" lang="en" aria-label=${`English translation: ${r.text_en}`}>EN (translation): ${r.text_en}</p>`
          : nothing}
        ${this.awaitingPayment
          ? html`<p class="pay" role="status">
              ${tr(this.language, "भुगतान ऐप की अपनी भुगतान स्क्रीन पर फ़िंगरप्रिंट से होगा — बोलकर नहीं।", "Approve on the app's own payment screen with your fingerprint — never by voice.")}
            </p>`
          : nothing}
      </section>
    `;
  }
}

define("ttb-readback", TtbReadback);

declare global {
  interface HTMLElementTagNameMap {
    "ttb-readback": TtbReadback;
  }
}
