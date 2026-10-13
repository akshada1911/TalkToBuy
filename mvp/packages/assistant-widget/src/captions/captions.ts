import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import type { CaptionMsg } from "../types/messages.generated";
import { base } from "../styles/tokens";
import { define } from "../define";
import { tr, type Lang } from "../i18n";

const DIGIT = "[0-9०-९]"; // ASCII and Devanagari digits
/** A contiguous run of 4–8 digits that is not part of a longer run. */
const RUN = new RegExp(`(?<!${DIGIT})${DIGIT}{4,8}(?!${DIGIT})`, "gu");
/** 4–8 single digits spoken one by one ("1 2 3 4", "1-2-3-4"). */
const SPACED = new RegExp(`(?<![0-9०-९])${DIGIT}(?:[ \\-]${DIGIT}){3,7}(?![ \\-]?${DIGIT})`, "gu");

/**
 * Mask OTP/PIN-like digit runs in shopper captions (T102, Constitution III): 4–8 digits in a row,
 * or 4–8 single digits separated by spaces or hyphens. Each digit becomes "•".
 */
export function maskDigits(text: string): string {
  return text
    .replace(SPACED, (m) => m.replace(/[0-9०-९]/gu, "•"))
    .replace(RUN, (m) => "•".repeat([...m].length));
}

interface Turn {
  key: string;
  who: CaptionMsg["who"];
  turn_id: string;
  text_hi: string;
  text_en?: string | null;
  final: boolean;
  interrupted?: boolean;
}

const MAX_TURNS = 40;

/**
 * Always-on captions for both sides (FR-003, FR-009). Captions are keyed by `who` + `turn_id`;
 * each message carries the turn's full text so far and replaces the previous text for that key.
 */
export class TtbCaptions extends LitElement {
  static styles = [
    base,
    css`
      :host {
        display: block;
      }
      .log {
        display: flex;
        flex-direction: column;
        gap: var(--ttb-space-small);
        max-height: var(--ttb-captions-max-height, 280px);
        overflow-y: auto;
        padding: var(--ttb-space-small);
        background: var(--ttb-surface);
        border: 2px solid var(--ttb-border);
        border-radius: var(--ttb-radius);
      }
      .turn {
        padding: 8px 12px;
        border-radius: var(--ttb-radius-small);
        max-width: 92%;
      }
      .assistant {
        align-self: flex-start;
        background: var(--ttb-surface-alt);
      }
      .shopper {
        align-self: flex-end;
        background: var(--ttb-primary-soft);
      }
      .who {
        font-size: var(--ttb-font-small);
        font-weight: 700;
        color: var(--ttb-muted);
      }
      .hi {
        font-size: var(--ttb-font-card);
        margin: 0;
      }
      .partial .hi {
        color: var(--ttb-muted);
      }
      .en {
        margin: 4px 0 0;
        padding: 2px 8px;
        font-size: var(--ttb-font-small);
        font-style: italic;
        color: var(--ttb-translation);
        background: var(--ttb-translation-bg);
        border-left: 4px solid var(--ttb-translation);
        border-radius: 4px;
      }
      .en-tag {
        font-style: normal;
        font-weight: 700;
        font-size: 14px;
        letter-spacing: 0.02em;
        margin-right: 6px;
      }
      .empty {
        color: var(--ttb-muted);
        margin: 0;
      }
      /* "talk" variant: the latest lines of the conversation, centred on the green page. Earlier
         turns stay in the DOM (for screen readers) but are not drawn. */
      .talk {
        display: flex;
        flex-direction: column;
        gap: 8px;
        min-height: var(--ttb-talk-min, 108px);
        text-align: center;
        color: #ffffff;
      }
      .talk .t {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      /* no bubble: the log variant's .assistant/.shopper backgrounds must not leak in */
      .talk .t {
        background: none;
        max-width: none;
        padding: 0;
        align-self: stretch;
      }
      .talk .t.old {
        position: absolute;
        width: 1px;
        height: 1px;
        overflow: hidden;
        clip: rect(0 0 0 0);
      }
      .talk p {
        margin: 0;
      }
      .talk .you {
        font-size: 15px;
        line-height: 1.35;
        font-style: italic;
        color: var(--ttb-on-forest);
      }
      .talk .bot {
        font-family: var(--ttb-font-display);
        font-weight: 600;
        font-size: var(--ttb-talk-size, 21px);
        line-height: 1.22;
        letter-spacing: -0.01em;
        text-wrap: balance;
      }
      .talk .t.partial .bot {
        opacity: 0.88;
      }
      .talk .tr {
        font-size: 13px;
        font-style: italic;
        color: var(--ttb-on-forest);
      }
    `,
  ];

  @property({ type: Boolean, attribute: "show-translation" }) showTranslation = true;
  @property() language: Lang = "hi";
  /** "log": every turn as a bubble. "talk": only the latest lines, centred (the assistant page). */
  @property() variant: "log" | "talk" = "log";
  @state() private turns: Turn[] = [];

  /** Add or update a caption. */
  upsert(msg: CaptionMsg): void {
    const key = `${msg.who}:${msg.turn_id}`;
    const masked = msg.who === "shopper";
    const next: Turn = {
      key,
      who: msg.who,
      turn_id: msg.turn_id,
      text_hi: masked ? maskDigits(msg.text_hi) : msg.text_hi,
      text_en: msg.text_en ? (masked ? maskDigits(msg.text_en) : msg.text_en) : msg.text_en,
      final: msg.final,
    };
    const idx = this.turns.findIndex((t) => t.key === key);
    if (idx >= 0) {
      const prev = this.turns[idx];
      // Keep an earlier translation if a later partial omits it.
      if (!next.text_en && prev.text_en) next.text_en = prev.text_en;
      const copy = this.turns.slice();
      copy[idx] = { ...prev, ...next };
      this.turns = copy;
    } else {
      this.turns = [...this.turns, next].slice(-MAX_TURNS);
    }
  }

  /** Mark the assistant's turn as cut off (barge-in). */
  markInterrupted(turnId?: string | null): void {
    this.turns = this.turns.map((t) =>
      t.who === "assistant" && (!turnId || t.turn_id === turnId) && !t.final ? { ...t, final: true, interrupted: true } : t,
    );
  }

  clear(): void {
    this.turns = [];
  }

  protected updated(): void {
    const log = this.renderRoot.querySelector(".log");
    if (log) log.scrollTop = log.scrollHeight;
  }

  private renderTalk() {
    const lastOf = (who: string) => {
      for (let i = this.turns.length - 1; i >= 0; i--) if (this.turns[i].who === who) return i;
      return -1;
    };
    const shown = new Set([lastOf("assistant"), lastOf("shopper")]);
    return html`
      <div class="talk" role="log" aria-live="polite" aria-relevant="additions text" aria-label=${tr(this.language, "बातचीत के कैप्शन", "Conversation captions")}>
        ${this.turns.length === 0
          ? html`<p class="bot" lang=${this.language}>${tr(this.language, "नमस्ते! आज क्या मँगवाना है?", "Namaste! What would you like to order today?")}</p>`
          : this.turns.map(
              (t, i) => html`
                <div class="t ${shown.has(i) ? "" : "old"} ${t.final ? "" : "partial"}" data-who=${t.who} data-turn=${t.turn_id}>
                  <p class=${t.who === "shopper" ? "you" : "bot"} lang=${this.language}>
                    <span class="sr-only">${t.who === "assistant" ? tr(this.language, "दुकानदार (AI): ", "Shopkeeper (AI): ") : tr(this.language, "आप: ", "You: ")}</span>${t.text_hi}${t.interrupted ? " …" : ""}
                  </p>
                  ${this.showTranslation && t.text_en
                    ? html`<p class="tr" lang="en" aria-label=${`English translation: ${t.text_en}`}><span aria-hidden="true">EN: ${t.text_en}</span></p>`
                    : nothing}
                </div>
              `,
            )}
      </div>
    `;
  }

  render() {
    if (this.variant === "talk") return this.renderTalk();
    return html`
      <div class="log" role="log" aria-live="polite" aria-relevant="additions text" aria-label=${tr(this.language, "बातचीत के कैप्शन", "Conversation captions")}>
        ${this.turns.length === 0
          ? html`<p class="empty">${tr(this.language, "यहाँ बातचीत लिखी दिखेगी।", "Captions appear here.")}</p>`
          : this.turns.map(
              (t) => html`
                <div class="turn ${t.who} ${t.final ? "" : "partial"}" data-turn=${t.turn_id}>
                  <div class="who">${t.who === "assistant" ? tr(this.language, "दुकानदार (AI)", "Shopkeeper (AI)") : tr(this.language, "आप", "You")}</div>
                  <p class="hi" lang=${this.language}>${t.text_hi}${t.interrupted ? " …" : ""}</p>
                  ${this.showTranslation && t.text_en
                    ? html`<p class="en" lang="en" aria-label=${`English translation: ${t.text_en}`}>
                        <span class="en-tag" aria-hidden="true">EN (translation)</span><span aria-hidden="true">${t.text_en}</span>
                      </p>`
                    : nothing}
                </div>
              `,
            )}
      </div>
    `;
  }
}

define("ttb-captions", TtbCaptions);

declare global {
  interface HTMLElementTagNameMap {
    "ttb-captions": TtbCaptions;
  }
}
