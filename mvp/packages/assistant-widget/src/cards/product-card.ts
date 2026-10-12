import { LitElement, css, html, nothing } from "lit";
import { property } from "lit/decorators.js";
import type { UiProduct } from "../types/messages.generated";
import { base, rupees } from "../styles/tokens";
import { define } from "../define";

export type CardVariant = "grid" | "spotlight" | "suggest";

/**
 * One product card (FR-013): picture, name, Hindi local name, size, ₹ price with a "demo price"
 * tag. All card text is ≥ 20 px (24 px when spotlighted) with AA contrast.
 */
export class TtbProductCard extends LitElement {
  static styles = [
    base,
    css`
      :host {
        display: block;
      }
      article {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: var(--ttb-surface);
        border: 2px solid var(--ttb-border);
        border-radius: var(--ttb-radius);
        box-shadow: var(--ttb-shadow);
        overflow: hidden;
        font-size: var(--ttb-font-card);
      }
      :host([variant="spotlight"]) article {
        border: 4px solid var(--ttb-success);
        font-size: var(--ttb-font-large);
      }
      :host([variant="suggest"]) article {
        border-style: dashed;
      }
      .pic {
        aspect-ratio: 1 / 1;
        background: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
      }
      .body {
        padding: 10px 12px 12px;
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .local {
        font-weight: 700;
        font-size: 1.1em;
        margin: 0;
      }
      .name,
      .size {
        margin: 0;
        color: var(--ttb-muted);
      }
      .price-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px 10px;
        margin-top: 4px;
      }
      .price {
        font-weight: 800;
        font-size: 1.15em;
      }
      .tag {
        font-size: var(--ttb-font-card);
        font-weight: 500;
        padding: 0 8px;
        border-radius: 999px;
        background: var(--ttb-warning-soft);
        color: var(--ttb-text);
        border: 1px solid var(--ttb-border);
      }
      .qty {
        font-weight: 800;
        color: var(--ttb-on-success);
        background: var(--ttb-success);
        padding: 0 10px;
        border-radius: 999px;
      }
      .oos {
        color: var(--ttb-danger);
        font-weight: 700;
        margin: 0;
      }
    `,
  ];

  @property({ attribute: false }) product?: UiProduct;
  @property({ type: Number }) qty = 0;
  @property({ reflect: true }) variant: CardVariant = "grid";

  render() {
    const p = this.product;
    if (!p) return nothing;
    const label = `${p.local_name}, ${p.name}, ${p.size}, ${rupees(p.price)} (demo price)${this.qty ? `, quantity ${this.qty}` : ""}`;
    return html`
      <article aria-label=${label}>
        <div class="pic">
          ${p.image
            ? html`<img src=${p.image} alt=${p.name} title=${p.image_credit || ""} loading="lazy" decoding="async" />`
            : nothing}
        </div>
        <div class="body">
          <p class="local" lang="hi">${p.local_name}</p>
          <p class="name" lang="en">${p.name}</p>
          <p class="size">${p.size}</p>
          <div class="price-row">
            <span class="price">${rupees(p.price)}</span>
            <span class="tag">डेमो दाम / demo price</span>
            ${this.qty > 0 ? html`<span class="qty" aria-label=${`मात्रा ${this.qty}`}>× ${this.qty}</span>` : nothing}
          </div>
          ${p.in_stock ? nothing : html`<p class="oos">अभी उपलब्ध नहीं / Out of stock</p>`}
        </div>
      </article>
    `;
  }
}

define("ttb-product-card", TtbProductCard);

declare global {
  interface HTMLElementTagNameMap {
    "ttb-product-card": TtbProductCard;
  }
}
