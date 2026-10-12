import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import type { CardsMsg, UiCart, UiProduct } from "../types/messages.generated";
import { base, rupees } from "../styles/tokens";
import { define } from "../define";
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

  render() {
    const cart = this.cart;
    const count = cart?.item_count ?? 0;
    const qtyOf = (id: string) => cart?.lines.find((l) => l.product.id === id)?.qty ?? 1;
    return html`
      <section aria-label="आपका कार्ट / Your cart">
        <p class="summary" aria-live="polite">
          <span>कार्ट में ${count} सामान / ${count} ${count === 1 ? "item" : "items"}</span>
          <span class="total">कुल ${rupees(cart?.total ?? 0)}</span>
        </p>
        ${this.spotlight
          ? html`<div class="spotlight" role="status">
              <p class="added">✓ कार्ट में जोड़ा / Added</p>
              <ttb-product-card
                variant="spotlight"
                .product=${this.spotlight}
                .qty=${qtyOf(this.spotlight.id)}
              ></ttb-product-card>
            </div>`
          : count === 0
            ? html`<p class="empty">अभी कार्ट खाली है। / Your cart is empty.</p>`
            : html`<ul class="grid" aria-label="कार्ट का सामान / Cart items">
                ${cart!.lines.map(
                  (l) => html`<li><ttb-product-card .product=${l.product} .qty=${l.qty}></ttb-product-card></li>`,
                )}
              </ul>`}
        ${this.suggestions.length
          ? html`<h3>सुझाव (अभी कार्ट में नहीं) / Suggestions</h3>
              <ul class="grid" aria-label="सुझाव / Suggestions">
                ${this.suggestions.map(
                  (p) => html`<li><ttb-product-card variant="suggest" .product=${p}></ttb-product-card></li>`,
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
