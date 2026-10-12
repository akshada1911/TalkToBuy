import { useEffect, useRef, useState } from "react";
import type { PaymentRequestedDetail, TalkToBuyAssistant } from "@talktobuy/assistant-widget";
import { PaymentStep } from "./payment/PaymentStep";
import { FamilyView } from "./family/FamilyView";
import { tr, type Lang } from "./lang";

export const SHOPPER_ID = "u-ghanshyam";

// Empty in local dev (Vite proxies /v1 with WebSockets); the session server's Cloud Run URL when deployed.
const SESSION_SERVER_URL: string = import.meta.env.VITE_PUBLIC_SESSION_SERVER_URL ?? "";
// Cost control: English captions only on the judges' screen (open the shop with ?en=1);
// the assistant is voice only: video (avatar) mode is not offered.
const PARAMS = new URLSearchParams(location.search);
const SHOW_ENGLISH = PARAMS.get("en") === "1";
const START_MEDIA_MODE = "audio_only";
// UI + conversation language: chosen with the picker below (or ?lang=en), remembered on this device.
function initialLang(): Lang {
  const fromUrl = PARAMS.get("lang");
  if (fromUrl === "en" || fromUrl === "hi") return fromUrl;
  try {
    return localStorage.getItem("ttb-lang") === "en" ? "en" : "hi";
  } catch {
    return "hi";
  }
}

function LanguagePicker({ lang, onChange }: { lang: Lang; onChange: (l: Lang) => void }) {
  return (
    <div className="lang-picker" role="radiogroup" aria-label="भाषा चुनें / Choose language">
      <span className="lang-label">भाषा / Language:</span>
      {(["hi", "en"] as const).map((l) => (
        <button
          key={l}
          type="button"
          role="radio"
          aria-checked={lang === l}
          className={lang === l ? "lang-btn selected" : "lang-btn"}
          onClick={() => onChange(l)}
        >
          {l === "hi" ? "हिंदी" : "English"}
        </button>
      ))}
    </div>
  );
}

const AISLES = [
  { icon: "🥛", hi: "दूध-दही", en: "Dairy" },
  { icon: "🌾", hi: "आटा-चावल", en: "Flour & rice" },
  { icon: "🍅", hi: "सब्ज़ी", en: "Vegetables" },
  { icon: "🌶️", hi: "मसाले", en: "Spices" },
  { icon: "🍪", hi: "बिस्कुट", en: "Biscuits" },
  { icon: "🍫", hi: "बेकिंग", en: "Baking" },
];

function Header({ cartCount, lang }: { cartCount: number | null; lang: Lang }) {
  return (
    <header className="site-header">
      <a className="brand" href="/">
        <span aria-hidden="true">🛒</span> TalkToBuy Demo Kirana
      </a>
      <nav aria-label={tr(lang, "मुख्य", "Main")}>
        {cartCount !== null && (
          <span className="cart-badge" aria-live="polite">
            {tr(lang, "कार्ट", "Cart")}: {cartCount}
          </span>
        )}
        <a className="nav-link" href="/family">
          {tr(lang, "परिवार", "Family view")}
        </a>
      </nav>
    </header>
  );
}

function Footer({ lang }: { lang: Lang }) {
  return (
    <footer className="site-footer">
      <p>Product data © Open Food Facts contributors, ODbL. Images CC BY-SA. openfoodfacts.org</p>
      <p>
        {lang === "en" ? (
          <>
            <strong>Prices are demo prices</strong> · Test mode: no real payment
          </>
        ) : (
          <>
            <strong>दाम सिर्फ़ डेमो के लिए हैं</strong> · टेस्ट मोड: कोई असली भुगतान नहीं
          </>
        )}
      </p>
    </footer>
  );
}

function ShopPage({ lang, onLang }: { lang: Lang; onLang: (l: Lang) => void }) {
  const widget = useRef<TalkToBuyAssistant>(null);
  const [payment, setPayment] = useState<PaymentRequestedDetail | null>(null);
  const [cartCount, setCartCount] = useState<number | null>(null);

  useEffect(() => {
    const el = widget.current;
    if (!el) return;
    const onPay = (e: CustomEvent<PaymentRequestedDetail>) => setPayment(e.detail);
    const onCart = (e: CustomEvent<{ cart: { item_count: number } }>) => setCartCount(e.detail.cart.item_count);
    const onEnd = () => setPayment(null);
    el.addEventListener("ttb:payment-cancelled", onEnd);
    el.addEventListener("ttb:payment-requested", onPay);
    el.addEventListener("ttb:cart-changed", onCart);
    el.addEventListener("ttb:session-ended", onEnd);
    return () => {
      el.removeEventListener("ttb:payment-requested", onPay);
      el.removeEventListener("ttb:cart-changed", onCart);
      el.removeEventListener("ttb:session-ended", onEnd);
      el.removeEventListener("ttb:payment-cancelled", onEnd);
    };
    // The widget is re-created when the language changes (key={lang}), so re-attach the listeners.
  }, [lang]);

  return (
    <>
      <Header cartCount={cartCount} lang={lang} />
      <main className="page">
        <section className="hero" aria-labelledby="hero-title">
          <h1 id="hero-title">{tr(lang, "नमस्ते! आज क्या मँगवाना है?", "Hello! What would you like to order today?")}</h1>
          <p className="hero-en" lang={lang}>
            {tr(
              lang,
              "दुकानदार को बताइए आपको क्या चाहिए, बोलकर या लिखकर।",
              "Tell the shopkeeper what you need, by voice or by typing.",
            )}
          </p>
        </section>

        <section className="assistant-slot" aria-label={tr(lang, "दुकानदार सहायक", "Shopkeeper assistant")}>
          <LanguagePicker lang={lang} onChange={onLang} />
          {/* Firebase Hosting can't proxy WebSockets, so deployed builds point straight at the
              session server (VITE_PUBLIC_SESSION_SERVER_URL, a public URL, never a secret). */}
          {/* key={lang}: switching language starts a fresh assistant in that language. */}
          <talktobuy-assistant
            key={lang}
            ref={widget}
            ticket-url={`${SESSION_SERVER_URL}/v1/demo-ticket`}
            server-url={SESSION_SERVER_URL}
            language={lang}
            show-translation={SHOW_ENGLISH && lang === "hi" ? "true" : "false"}
            media-mode={START_MEDIA_MODE}
            avatar-audio="muxed"
          />
        </section>

        <section aria-labelledby="aisles-title">
          <h2 id="aisles-title">{tr(lang, "दुकान के सामान", "Aisles")}</h2>
          <ul className="aisles">
            {AISLES.map((a) => (
              <li key={a.en} className="aisle">
                <span className="aisle-icon" aria-hidden="true">
                  {a.icon}
                </span>
                <span className="aisle-hi" lang={lang}>
                  {tr(lang, a.hi, a.en)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </main>
      <Footer lang={lang} />
      {payment && (
        <PaymentStep
          request={payment}
          shopperId={SHOPPER_ID}
          lang={lang}
          onResolve={(result) => {
            widget.current?.resolvePayment(result);
            setPayment(null);
          }}
        />
      )}
    </>
  );
}

export function App() {
  const [lang, setLang] = useState<Lang>(initialLang);
  const chooseLang = (l: Lang) => {
    setLang(l);
    try {
      localStorage.setItem("ttb-lang", l);
    } catch {
      /* private mode: the choice just isn't remembered */
    }
  };

  const path = window.location.pathname.replace(/\/+$/, "");
  if (path === "/family") {
    return (
      <>
        <Header cartCount={null} lang={lang} />
        <main className="page">
          <LanguagePicker lang={lang} onChange={chooseLang} />
          <FamilyView shopperId={SHOPPER_ID} lang={lang} />
        </main>
        <Footer lang={lang} />
      </>
    );
  }
  return <ShopPage lang={lang} onLang={chooseLang} />;
}
