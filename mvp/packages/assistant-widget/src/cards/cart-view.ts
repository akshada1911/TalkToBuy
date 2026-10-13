import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import type { CardsMsg, UiCart, UiProduct } from "../types/messages.generated";
import { base, rupees } from "../styles/tokens";
import { define } from "../define";
import { tr, type Lang } from "../i18n";
import "./product-card";

export type Pace = "guided" | "quick";

/** How long the newest card stays large and alone in guided pace (T097). */
export const SPOTLIGHT_MS = 3500;

/**
 * The cards on screen ARE the cart (FR-013): a running item count and ₹ total from `cart`
 * messages, one card per cart line. `cards` with mode "suggest" shows options that are not in the
 * cart yet. In guided pace the newest added card is shown large and alone first, then joins the
 * grid (T097).
 */
export class TtbCartView extends LitElement {
  static styles = [
    base,
    css`
      :host {
        display: block;
      }
      .summary {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        align-items: baseline;
        gap: 4px 16px;
        margin: 0 0 var(--ttb-space-small);
        font-size: var(--ttb-font-large);
        font-weight: 700;
      }
      .total {
        font-size: var(--ttb-font-xl);
      }
      h3 {
        font-size: var(--ttb-font-card);
        margin: var(--ttb-space) 0 var(--ttb-space-small);
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(var(--ttb-card-min, 170px), 1fr));
        gap: var(--ttb-space);
        list-style: none;
        margin: 0;
        padding: 0;
      }
      .spotlight {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--ttb-space-small);
        animation: pop 300ms ease-out;
      }
      .spotlight ttb-product-card {
        width: min(100%, 340px);
      }
      .spotlight .added {
        font-size: var(--ttb-font-large);
        font-weight: 700;
        color: var(--ttb-success);
        margin: 0;
      }
      .empty {
        color: var(--ttb-muted);
        font-size: var(--ttb-font-card);
        margin: 0;
      }
      /* compact: the assistant page's light cart panel (rows, not a card grid) */
      .compact {
        display: flex;
        flex-direction: column;
        gap: 6px;
        min-height: 0;
        padding: 12px 14px;
        background: var(--ttb-bg);
        color: var(--ttb-text);
        border-radius: 24px;
      }
      .compact .head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
      }
      .compact .head .title {
        font-family: var(--ttb-font-display);
        font-weight: 700;
        font-size: 16px;
      }
      .compact .head .title small {
        font-family: var(--ttb-font);
        font-weight: 500;
        font-size: 13px;
        color: var(--ttb-muted);
      }
      .compact .head .sum {
        font-family: var(--ttb-font-display);
        font-weight: 800;
        font-size: 22px;
      }
      .compact ul.rows {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 6px;
        min-height: 0;
        overflow-y: auto;
      }
      .compact li {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .compact li.suggest {
        opacity: 0.85;
      }
      .compact .thumb {
        width: 38px;
        height: 38px;
        flex: none;
        border-radius: 12px;
        background: #ffffff;
        object-fit: contain;
      }
      .compact .what {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
      }
      .compact .what b {
        font-weight: 600;
        font-size: 14px;
      }
      .compact .what small {
        font-size: 12px;
        color: var(--ttb-muted);
      }
      .compact .price {
        font-weight: 700;
        font-size: 14px;
      }
      .compact h4 {
        margin: 6px 0 0;
        font-size: 13px;
        color: var(--ttb-muted);
      }
      @keyframes pop {
        from {
          transform: scale(0.92);
          opacity: 0.4;
        }
        to {
          transform: scale(1);
          opacity: 1;
        }
      }
    `,
  ];

  @property({ attribute: false }) cart: UiCart | null = null;
  @property() pace: Pace = "guided";
  /** The assistant page's compact list (rows) instead of the card grid. */
  @property({ type: Boolean }) compact = false;
  @property() language: Lang = "hi";
  @state() private suggestions: UiProduct[] = [];
  @state() private spotlight: UiProduct | null = null;
  private spotlightTimer: ReturnType<typeof setTimeout> | null = null;
  private knownIds = new Set<string>();
  private lastSpotlightId: string | null = null;

  setCart(cart: UiCart): void {
    const ids = cart.lines.map((l) => l.product.id);
    const fresh = cart.lines.filter((l) => !this.knownIds.has(l.product.id));
    this.knownIds = new Set(ids);
    this.cart = cart;
    // Suggestions that are now in the cart are no longer suggestions.
    if (this.suggestions.length) this.suggestions = this.suggestions.filter((p) => !this.knownIds.has(p.id));
    if (fresh.length) this.spotlightProduct(fresh[fresh.length - 1].product);
  }

  showCards(msg: CardsMsg): void {
    if (msg.mode === "suggest") {
      this.suggestions = msg.products;
      return;
    }
    // "added": the cart message normally follows; spotlight right away so the card is on screen
    // before the assistant finishes mentioning it (SC-007).
    const last = msg.products[msg.products.length - 1];
    if (last) this.spotlightProduct(last);
    this.suggestions = this.suggestions.filter((p) => !msg.products.some((a) => a.id === p.id));
  }

  clearSuggestions(): void {
    this.suggestions = [];
  }

  /** Visible for tests. */
  get spotlightId(): string | null {
    return this.spotlight?.id ?? null;
  }

  private spotlightProduct(p: UiProduct): void {
    if (this.pace !== "guided") return;
    if (this.spotlight?.id === p.id || (this.lastSpotlightId === p.id && !this.spotlight)) return;
    this.lastSpotlightId = p.id;
    this.spotlight = p;
    if (this.spotlightTimer) clearTimeout(this.spotlightTimer);
    this.spotlightTimer = setTimeout(() => {
      this.spotlight = null;
      this.spotlightTimer = null;
    }, SPOTLIGHT_MS);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this.spotlightTimer) clearTimeout(this.spotlightTimer);
  }

  protected willUpdate(changed: Map<string, unknown>): void {
    if (changed.has("pace") && this.pace === "quick" && this.spotlight) {
      this.spotlight = null;
      if (this.spotlightTimer) clearTimeout(this.spotlightTimer);
    }
  }

  private renderCompact() {
    const cart = this.cart;
    const L = this.language;
    const lines = cart?.lines ?? [];
    const count = lines.reduce((n, l) => n + l.qty, 0);
    const name = (p: UiProduct) => (L === "en" ? p.name : p.local_name || p.name);
    return html`
      <section class="compact" aria-label=${tr(L, "आपका कार्ट", "Your cart")}>
        <div class="head" aria-live="polite">
          <span class="title">${tr(L, "आपका कार्ट", "Your cart")} <small>${count === 1 ? tr(L, "1 सामान", "1 item") : tr(L, `${count} सामान`, `${count} items`)}</small></span>
          <span class="sum">${rupees(cart?.total ?? 0)}</span>
        </div>
        ${this.spotlight
          ? html`<div class="spotlight" role="status">
              <p class="added">✓ ${tr(L, "कार्ट में जोड़ा", "Added to cart")}</p>
              <ttb-product-card variant="spotlight" .product=${this.spotlight} .qty=${lines.find((l) => l.product.id === this.spotlight?.id)?.qty ?? 1} .language=${L}></ttb-product-card>
            </div>`
          : nothing}
        ${lines.length === 0 && !this.spotlight
          ? html`<p class="empty">${tr(L, "अभी कुछ नहीं। बोलकर बताइए, या नीचे सुझाव दबाइए।", "Nothing yet. Say what you need, or tap a suggestion below.")}</p>`
          : html`<ul class="rows" aria-label=${tr(L, "कार्ट का सामान", "Cart items")}>
              ${lines.map(
                (l) => html`<li>
                  ${l.product.image ? html`<img class="thumb" src=${l.product.image} alt="" loading="lazy" />` : html`<span class="thumb"></span>`}
                  <span class="what"><b>${name(l.product)}</b><small>${l.product.size} · ×${l.qty}</small></span>
                  <span class="price">${rupees(l.line_total)}</span>
                </li>`,
              )}
            </ul>`}
        ${this.suggestions.length
          ? html`<h4>${tr(L, "सुझाव (अभी कार्ट में नहीं)", "Suggestions (not in cart yet)")}</h4>
              <ul class="rows" aria-label=${tr(L, "सुझाव", "Suggestions")}>
                ${this.suggestions.map(
                  (p) => html`<li class="suggest">
                    ${p.image ? html`<img class="thumb" src=${p.image} alt="" loading="lazy" />` : html`<span class="thumb"></span>`}
                    <span class="what"><b>${name(p)}</b><small>${p.size}</small></span>
                    <span class="price">${rupees(p.price)}</span>
                  </li>`,
                )}
              </ul>`
          : nothing}
      </section>
    `;
  }

  render() {
    if (this.compact) return this.renderCompact();
    const cart = this.cart;
    const count = cart?.item_count ?? 0;
    const qtyOf = (id: string) => cart?.lines.find((l) => l.product.id === id)?.qty ?? 1;
    return html`
      <section aria-label=${tr(this.language, "आपका कार्ट", "Your cart")}>
        <p class="summary" aria-live="polite">
          <span>${this.language === "en" ? `${count} ${count === 1 ? "item" : "items"} in cart` : `कार्ट में ${count} सामान`}</span>
          <span class="total">${tr(this.language, "कुल", "Total")} ${rupees(cart?.total ?? 0)}</span>
        </p>
        ${this.spotlight
          ? html`<div class="spotlight" role="status">
              <p class="added">✓ ${tr(this.language, "कार्ट में जोड़ा", "Added to cart")}</p>
              <ttb-product-card
                variant="spotlight"
                .product=${this.spotlight}
                .qty=${qtyOf(this.spotlight.id)}
                .language=${this.language}
              ></ttb-product-card>
            </div>`
          : count === 0
            ? html`<p class="empty">${tr(this.language, "अभी कार्ट खाली है।", "Your cart is empty.")}</p>`
            : html`<ul class="grid" aria-label=${tr(this.language, "कार्ट का सामान", "Cart items")}>
                ${cart!.lines.map(
                  (l) => html`<li><ttb-product-card .product=${l.product} .qty=${l.qty} .language=${this.language}></ttb-product-card></li>`,
                )}
              </ul>`}
        ${this.suggestions.length
          ? html`<h3>${tr(this.language, "सुझाव (अभी कार्ट में नहीं)", "Suggestions (not in cart yet)")}</h3>
              <ul class="grid" aria-label=${tr(this.language, "सुझाव", "Suggestions")}>
                ${this.suggestions.map(
                  (p) => html`<li><ttb-product-card variant="suggest" .product=${p} .language=${this.language}></ttb-product-card></li>`,
                )}
              </ul>`
          : nothing}
      </section>
    `;
  }
}

define("ttb-cart-view", TtbCartView);

declare global {
  interface HTMLElementTagNameMap {
    "ttb-cart-view": TtbCartView;
  }
}
