import { LitElement, css, html, nothing } from "lit";
import { property } from "lit/decorators.js";
import type { GoalListMsg, UiGoalItem } from "../types/messages.generated";
import { base, rupees } from "../styles/tokens";
import { define } from "../define";

export const STRUCK_REASON_HI: Record<NonNullable<UiGoalItem["struck_reason"]>, string> = {
  on_hand: "आपके पास है",
  in_cart: "कार्ट में है",
};
const STRUCK_REASON_EN: Record<NonNullable<UiGoalItem["struck_reason"]>, string> = {
  on_hand: "you have it",
  in_cart: "already in cart",
};

/**
 * Goal list (FR-026, T078): large rows with picture, name, pack and qty. Struck items show a
 * strike-through and their reason. Each new `goal_list` message replaces the list (live updates).
 */
export class TtbGoalList extends LitElement {
  static styles = [
    base,
    css`
      :host {
        display: block;
      }
      section {
        background: var(--ttb-surface);
        border: 2px solid var(--ttb-border);
        border-radius: var(--ttb-radius);
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
        align-items: center;
        gap: 12px;
        min-height: 64px;
        padding: 6px 8px;
        border-radius: var(--ttb-radius-small);
        background: var(--ttb-surface-alt);
        font-size: var(--ttb-font-card);
      }
      img {
        width: 56px;
        height: 56px;
        object-fit: contain;
        background: #ffffff;
        border-radius: 8px;
        flex: none;
      }
      .text {
        flex: 1;
        min-width: 0;
      }
      .need {
        font-weight: 700;
      }
      .meta {
        color: var(--ttb-muted);
      }
      .qty {
        font-weight: 800;
        white-space: nowrap;
      }
      li.struck .need,
      li.struck .meta {
        text-decoration: line-through;
        text-decoration-thickness: 3px;
        color: var(--ttb-muted);
      }
      .reason {
        display: inline-block;
        margin-top: 2px;
        font-weight: 700;
        color: var(--ttb-success);
        text-decoration: none;
      }
    `,
  ];

  @property({ attribute: false }) goal: GoalListMsg | null = null;

  render() {
    const g = this.goal;
    if (!g) return nothing;
    return html`
      <section aria-label="सामान की सूची / Shopping list">
        <h3 lang="hi">${g.goal_text}</h3>
        <ul>
          ${g.items.map((it) => this.row(it))}
        </ul>
      </section>
    `;
  }

  private row(it: UiGoalItem) {
    const p = it.product;
    const reason = it.struck && it.struck_reason ? it.struck_reason : null;
    return html`
      <li class=${it.struck ? "struck" : ""} data-struck=${it.struck ? "true" : "false"}>
        ${p?.image ? html`<img src=${p.image} alt="" loading="lazy" />` : nothing}
        <div class="text">
          <div class="need" lang="hi">
            ${it.struck ? html`<span class="sr-only">हटाया गया: </span>` : nothing}${p?.local_name || it.need}
          </div>
          ${p ? html`<div class="meta">${p.name} · ${p.size} · ${rupees(p.price)}</div>` : nothing}
          ${reason
            ? html`<span class="reason" lang="hi">${STRUCK_REASON_HI[reason]}<span class="sr-only"> (${STRUCK_REASON_EN[reason]})</span></span>`
            : nothing}
        </div>
        ${!it.struck && it.qty ? html`<span class="qty">× ${it.qty}</span>` : nothing}
      </li>
    `;
  }
}

define("ttb-goal-list", TtbGoalList);

declare global {
  interface HTMLElementTagNameMap {
    "ttb-goal-list": TtbGoalList;
  }
}
