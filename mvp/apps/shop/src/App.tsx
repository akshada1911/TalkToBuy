import { useEffect, useRef, useState } from "react";
import type { PaymentRequestedDetail, TalkToBuyAssistant } from "@talktobuy/assistant-widget";
import { PaymentStep } from "./payment/PaymentStep";
import { FamilyView } from "./family/FamilyView";

export const SHOPPER_ID = "u-ghanshyam";

// Empty in local dev (Vite proxies /v1 with WebSockets); the session server's Cloud Run URL when deployed.
const SESSION_SERVER_URL: string = import.meta.env.VITE_PUBLIC_SESSION_SERVER_URL ?? "";

const AISLES = [
  { icon: "🥛", hi: "दूध-दही", en: "Dairy" },
  { icon: "🌾", hi: "आटा-चावल", en: "Flour & rice" },
  { icon: "🍅", hi: "सब्ज़ी", en: "Vegetables" },
  { icon: "🌶️", hi: "मसाले", en: "Spices" },
  { icon: "🍪", hi: "बिस्कुट", en: "Biscuits" },
  { icon: "🍫", hi: "बेकिंग", en: "Baking" },
];

function Header({ cartCount }: { cartCount: number | null }) {
  return (
    <header className="site-header">
      <a className="brand" href="/">
        <span aria-hidden="true">🛒</span> TalkToBuy Demo Kirana
      </a>
      <nav aria-label="मुख्य / Main">
        {cartCount !== null && (
          <span className="cart-badge" aria-live="polite">
            कार्ट: {cartCount} / Cart: {cartCount}
          </span>
        )}
        <a className="nav-link" href="/family">
          परिवार / Family view
        </a>
      </nav>
    </header>
  );
}

function Footer() {
  return (
    <footer className="site-footer">
      <p>Product data © Open Food Facts contributors, ODbL. Images CC BY-SA. openfoodfacts.org</p>
      <p>
        <strong>Prices are demo prices</strong> · दाम सिर्फ़ डेमो के लिए हैं · Test mode: no real payment
      </p>
    </footer>
  );
}

function ShopPage() {
  const widget = useRef<TalkToBuyAssistant>(null);
  const [payment, setPayment] = useState<PaymentRequestedDetail | null>(null);
  const [cartCount, setCartCount] = useState<number | null>(null);

  useEffect(() => {
    const el = widget.current;
    if (!el) return;
    const onPay = (e: CustomEvent<PaymentRequestedDetail>) => setPayment(e.detail);
    const onCart = (e: CustomEvent<{ cart: { item_count: number } }>) => setCartCount(e.detail.cart.item_count);
    const onEnd = () => setPayment(null);
    el.addEventListener("ttb:payment-requested", onPay);
    el.addEventListener("ttb:cart-changed", onCart);
    el.addEventListener("ttb:session-ended", onEnd);
    return () => {
      el.removeEventListener("ttb:payment-requested", onPay);
      el.removeEventListener("ttb:cart-changed", onCart);
      el.removeEventListener("ttb:session-ended", onEnd);
    };
  }, []);

  return (
    <>
      <Header cartCount={cartCount} />
      <main className="page">
        <section className="hero" aria-labelledby="hero-title">
          <h1 id="hero-title">नमस्ते! आज क्या मँगवाना है?</h1>
          <p className="hero-en" lang="en">
            Hello! Tell the shopkeeper what you need, by voice or by typing.
          </p>
        </section>

        <section className="assistant-slot" aria-label="दुकानदार सहायक / Shopkeeper assistant">
          {/* Firebase Hosting can't proxy WebSockets, so deployed builds point straight at the
              session server (VITE_PUBLIC_SESSION_SERVER_URL, a public URL, never a secret). */}
          <talktobuy-assistant
            ref={widget}
            ticket-url={`${SESSION_SERVER_URL}/v1/demo-ticket`}
            server-url={SESSION_SERVER_URL}
            language="hi"
            show-translation="true"
            avatar-audio="muxed"
          />
        </section>

        <section aria-labelledby="aisles-title">
          <h2 id="aisles-title">दुकान के सामान / Aisles</h2>
          <ul className="aisles">
            {AISLES.map((a) => (
              <li key={a.en} className="aisle">
                <span className="aisle-icon" aria-hidden="true">
                  {a.icon}
                </span>
                <span className="aisle-hi">{a.hi}</span>
                <span className="aisle-en" lang="en">
                  {a.en}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </main>
      <Footer />
      {payment && (
        <PaymentStep
          request={payment}
          shopperId={SHOPPER_ID}
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
  const path = window.location.pathname.replace(/\/+$/, "");
  if (path === "/family") {
    return (
      <>
        <Header cartCount={null} />
        <main className="page">
          <FamilyView shopperId={SHOPPER_ID} />
        </main>
        <Footer />
      </>
    );
  }
  return <ShopPage />;
}
