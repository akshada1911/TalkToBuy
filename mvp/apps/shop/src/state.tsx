import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type {
  OrderPlacedDetail,
  PaymentRequestedDetail,
  PaymentResult,
  TalkToBuyAssistant,
  UiCart,
  UiCartLine,
  WidgetPhase,
} from "@talktobuy/assistant-widget";
import { completeCart, linesOf, listAddresses, putCart, type CatalogProduct, type SavedAddress, type StoreCart } from "./api";
import { useShopCart } from "./shopCart";
import { LangContext, translate, type StringKey } from "./i18n";
import { URL_LANG } from "./config";
import type { Lang } from "./lang";

export type Screen = "home" | "list" | "pdp" | "cart" | "checkout" | "pay" | "track" | "settings" | "family" | "address" | "talk";

/** A payment to approve with the fingerprint. `manual`: the shop's own checkout (no assistant involved). */
export type PaymentRequest = PaymentRequestedDetail & { manual?: boolean };

export interface Route {
  screen: Screen;
  pdpId?: string;
  listCat?: string;
  query?: string;
}

export interface PlacedOrder {
  id: string;
  slot: { label_hi: string; label_en: string };
  lines: UiCartLine[];
  total: number;
  addressText: string;
  placedAt: number;
}

export type PayMethod = "upi" | "card" | "wallet" | "cod";

export interface Member {
  id: string;
  name: string;
  canOrder: boolean;
  locked: boolean;
}

interface DemoState {
  coupon: string | null;
  tip: number;
  pay: PayMethod;
  share: boolean;
  members: Member[];
}

const LANG_KEY = "ttb-lang";
const ADDR_KEY = "ttb-addr";
const ASK_TIMEOUT_MS = 15000;
const LIVE_TIMEOUT_MS = 15000;
const APPROVAL_TIMEOUT_MS = 25000;

function initialLang(): Lang {
  if (URL_LANG === "en" || URL_LANG === "hi") return URL_LANG;
  try {
    return localStorage.getItem(LANG_KEY) === "en" ? "en" : "hi";
  } catch {
    return "hi";
  }
}

function initialStack(): Route[] {
  const path = window.location.pathname.replace(/\/+$/, "");
  if (path === "/family") return [{ screen: "home" }, { screen: "settings" }, { screen: "family" }];
  return [{ screen: "home" }];
}

export interface AppApi {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: StringKey, vars?: Record<string, string | number>) => string;

  route: Route;
  go: (r: Route) => void;
  back: () => void;
  goHome: () => void;

  // the assistant
  phase: WidgetPhase;
  voiceOpen: boolean;
  openVoice: () => void;
  closeVoice: () => void;
  /** Open the full Talk page and start the conversation. Call from a tap. */
  openTalk: () => void;
  endTalk: () => void;
  ask: (text: string) => Promise<boolean>;
  toast: string | null;

  // the one cart: filled by tapping in the shop or by voice (same cart in the store)
  cart: UiCart | null;
  cartId: string | null;
  count: number;
  total: number;
  qtyOf: (productId: string) => number;
  isPending: (productId: string) => boolean;
  addItem: (p: Pick<CatalogProduct, "id">) => void;
  incItem: (p: Pick<CatalogProduct, "id">) => void;
  decItem: (p: Pick<CatalogProduct, "id">) => void;
  clearCart: () => void;
  /** Counts up each time the cart goes from full to empty (for the "cleared" effect). */
  clearedTick: number;
  /** Check out by voice (the assistant reads it back). */
  requestCheckout: () => void;
  requestCancel: () => void;
  checkoutPending: boolean;
  /** Check out by tapping: choose the slot and address, then pay. Resolves false if it could not start. */
  startManualCheckout: (slotId: string, addressId: string) => Promise<boolean>;

  // payment + order
  paymentRequest: PaymentRequest | null;
  resolvePayment: (r: PaymentResult) => void;
  order: PlacedOrder | null;
  ordersBadge: boolean;

  // addresses
  addresses: SavedAddress[];
  addressesError: boolean;
  preferred: SavedAddress | null;
  setPreferred: (id: string) => void;
  reloadAddresses: () => Promise<void>;

  // demo-only extras
  demo: DemoState;
  setDemo: (patch: Partial<DemoState>) => void;

  // the widget element (for the host)
  widgetRef: React.RefObject<TalkToBuyAssistant>;
  bump: number;
}

const AppContext = createContext<AppApi | null>(null);

export function useApp(): AppApi {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp outside AppProvider");
  return ctx;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  const [stack, setStack] = useState<Route[]>(initialStack);
  const widgetRef = useRef<TalkToBuyAssistant>(null);

  const [phase, setPhase] = useState<WidgetPhase>("idle");
  const phaseRef = useRef<WidgetPhase>("idle");
  const waiters = useRef<Array<(ok: boolean) => void>>([]);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const [checkoutPending, setCheckoutPending] = useState(false);
  const skipClearedToast = useRef(false);

  const [paymentRequest, setPaymentRequest] = useState<PaymentRequest | null>(null);
  const paymentRef = useRef<PaymentRequest | null>(null);
  paymentRef.current = paymentRequest;
  const [order, setOrder] = useState<PlacedOrder | null>(null);
  const lastPaymentRef = useRef<PaymentRequestedDetail | null>(null);
  const approvalTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clearApprovalTimer = () => {
    if (approvalTimer.current) clearTimeout(approvalTimer.current);
    approvalTimer.current = null;
  };

  const [addresses, setAddresses] = useState<SavedAddress[]>([]);
  const [addressesError, setAddressesError] = useState(false);
  const [preferredId, setPreferredId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(ADDR_KEY);
    } catch {
      return null;
    }
  });

  const [demo, setDemoState] = useState<DemoState>({
    coupon: null,
    tip: 0,
    pay: "upi",
    share: true,
    members: [
      { id: "me", name: "You", canOrder: true, locked: true },
      { id: "rohit", name: "Rohit (son)", canOrder: false, locked: false },
    ],
  });

  const langRef = useRef(lang);
  langRef.current = lang;
  const route = stack[stack.length - 1];
  const routeRef = useRef(route);
  routeRef.current = route;

  // ------------------------------------------------------------ language
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(LANG_KEY, l);
    } catch {
      /* private mode: the choice just isn't remembered */
    }
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const t = useCallback((key: StringKey, vars?: Record<string, string | number>) => translate(lang, key, vars), [lang]);

  // ------------------------------------------------------------ navigation
  const go = useCallback((r: Route) => setStack((s) => [...s, r]), []);
  const back = useCallback(() => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s)), []);
  const goHome = useCallback(() => setStack([{ screen: "home" }]), []);

  // ------------------------------------------------------------ toast
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showToast = useCallback((msg: string) => {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4000);
  }, []);

  // ------------------------------------------------------------ the one cart
  const shop = useShopCart({
    widgetRef,
    onCleared: () => {
      if (!skipClearedToast.current) showToast(translate(langRef.current, "cartCleared"));
    },
    onError: () => showToast(translate(langRef.current, "cartSaveFailed")),
  });

  // ------------------------------------------------------------ the assistant's events
  useEffect(() => {
    const el = widgetRef.current;
    if (!el) return;
    // A fresh assistant (language change) is a fresh conversation; the cart stays (it is in the store).
    setCheckoutPending(false);
    if (!paymentRef.current?.manual) setPaymentRequest(null);
    phaseRef.current = "idle";
    setPhase("idle");

    const onPhase = (e: CustomEvent<{ phase: WidgetPhase }>) => {
      phaseRef.current = e.detail.phase;
      setPhase(e.detail.phase);
      if (e.detail.phase === "live") {
        waiters.current.splice(0).forEach((w) => w(true));
      } else if (e.detail.phase === "ended") {
        waiters.current.splice(0).forEach((w) => w(false));
      }
    };
    const onCart = (e: CustomEvent<{ cart: UiCart; cart_id?: string | null }>) => {
      shop.fromAssistant(e.detail.cart, e.detail.cart_id ?? null);
      setCheckoutPending(false);
    };
    const onPay = (e: CustomEvent<PaymentRequestedDetail>) => {
      lastPaymentRef.current = e.detail;
      setPaymentRequest(e.detail);
      setCheckoutPending(false);
      setVoiceOpen(false);
      setStack((s) => (s[s.length - 1].screen === "pay" ? s : [...s.filter((r) => r.screen !== "talk"), { screen: "pay" }]));
    };
    const onPayCancelled = () => {
      if (paymentRef.current?.manual) return; // the shop's own payment is not the assistant's to cancel
      clearApprovalTimer();
      setPaymentRequest(null);
      setStack((s) => (s[s.length - 1].screen === "pay" ? s.slice(0, -1) : s));
    };
    const onOrder = (e: CustomEvent<OrderPlacedDetail>) => {
      clearApprovalTimer();
      const snapshot = shop.cartRef.current;
      const placed: PlacedOrder = {
        id: e.detail.order_id,
        slot: { label_hi: e.detail.delivery.label_hi, label_en: e.detail.delivery.label_en },
        lines: snapshot?.lines ?? [],
        total: snapshot?.total ?? 0,
        addressText: lastPaymentRef.current?.address_text ?? "",
        placedAt: Date.now(),
      };
      shop.forget(); // the order used the cart: it is over, so the next item starts a new one
      setOrder(placed);
      setPaymentRequest(null);
      setVoiceOpen(false);
      setStack([{ screen: "home" }, { screen: "track" }]);
    };
    const onEnded = () => {
      clearApprovalTimer();
      if (!paymentRef.current?.manual) setPaymentRequest(null);
      setCheckoutPending(false);
    };
    const onOpenCart = () => {
      setVoiceOpen(false);
      setStack((s) => [...s.filter((r) => r.screen !== "talk"), { screen: "cart" }]);
    };

    el.addEventListener("ttb:phase", onPhase);
    el.addEventListener("ttb:cart-changed", onCart);
    el.addEventListener("ttb:payment-requested", onPay);
    el.addEventListener("ttb:payment-cancelled", onPayCancelled);
    el.addEventListener("ttb:order-placed", onOrder);
    el.addEventListener("ttb:session-ended", onEnded);
    el.addEventListener("ttb:open-cart", onOpenCart);
    return () => {
      el.removeEventListener("ttb:phase", onPhase);
      el.removeEventListener("ttb:cart-changed", onCart);
      el.removeEventListener("ttb:payment-requested", onPay);
      el.removeEventListener("ttb:payment-cancelled", onPayCancelled);
      el.removeEventListener("ttb:order-placed", onOrder);
      el.removeEventListener("ttb:session-ended", onEnded);
      el.removeEventListener("ttb:open-cart", onOpenCart);
    };
    // The widget element is re-created when the language changes (key={lang}).
  }, [lang]);

  // ------------------------------------------------------------ talking to the assistant
  const waitLive = useCallback((): Promise<boolean> => {
    if (phaseRef.current === "live") return Promise.resolve(true);
    return new Promise((resolve) => {
      const timer = setTimeout(() => resolve(false), LIVE_TIMEOUT_MS);
      waiters.current.push((ok) => {
        clearTimeout(timer);
        resolve(ok);
      });
    });
  }, []);

  /** Start the conversation if it is not running. Must run synchronously inside a tap. */
  const ensureStarted = useCallback(() => {
    const el = widgetRef.current;
    const p = phaseRef.current;
    if (el && (p === "idle" || p === "ended")) void el.start();
  }, []);

  const ask = useCallback(
    async (text: string): Promise<boolean> => {
      ensureStarted();
      const ok = await waitLive();
      if (!ok) {
        showToast(translate(lang, "assistantFailed"));
        return false;
      }
      return widgetRef.current?.sendText(text) ?? false;
    },
    [ensureStarted, waitLive, showToast, lang],
  );

  const openVoice = useCallback(() => {
    ensureStarted();
    setVoiceOpen(true);
  }, [ensureStarted]);
  const closeVoice = useCallback(() => setVoiceOpen(false), []);
  const openTalk = useCallback(() => {
    ensureStarted();
    setVoiceOpen(false);
    setStack((s) => (s[s.length - 1].screen === "talk" ? s : [...s, { screen: "talk" }]));
  }, [ensureStarted]);
  const endTalk = useCallback(() => {
    setStack((s) => (s[s.length - 1].screen === "talk" ? s.slice(0, -1) : s));
  }, []);

  // ------------------------------------------------------------ checkout and cancel by voice
  const requestCheckout = useCallback(() => {
    setCheckoutPending(true);
    setVoiceOpen(true);
    void ask(translate(lang, "checkoutAsk")).then((ok) => {
      if (!ok) setCheckoutPending(false);
    });
    setTimeout(() => setCheckoutPending(false), ASK_TIMEOUT_MS);
  }, [ask, lang]);
  const requestCancel = useCallback(() => {
    setVoiceOpen(true);
    void ask(translate(lang, "cancelAsk"));
  }, [ask, lang]);

  // ------------------------------------------------------------ checkout by tapping (no assistant)
  const startManualCheckout = useCallback(
    async (slotId: string, addressId: string): Promise<boolean> => {
      const id = shop.idRef.current;
      const cur = shop.cartRef.current;
      if (!id || !cur || cur.lines.length === 0) return false;
      try {
        const view = await putCart(id, linesOf(cur), { slot_id: slotId, address_id: addressId });
        if (view.status !== "ready_for_complete" || !view.slot || !view.address) throw new Error("not ready");
        setPaymentRequest({
          checkout_id: view.id,
          total: view.total,
          currency: "INR",
          item_count: view.item_count,
          delivery: { id: view.slot.id, label_hi: view.slot.label_hi, label_en: view.slot.label_en },
          address_text: `${view.address.label}: ${view.address.text}`,
          manual: true,
        });
        setStack((s) => [...s, { screen: "pay" }]);
        return true;
      } catch {
        showToast(translate(langRef.current, "checkoutFailed"));
        return false;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [showToast],
  );

  /** The store completed the shop's own order. */
  const placeManualOrder = useCallback(
    (view: StoreCart) => {
      const o = view.order;
      skipClearedToast.current = true; // an order is not "clearing the cart"
      shop.forget();
      widgetRef.current?.syncCart(); // a running conversation learns the cart is finished
      setPaymentRequest(null);
      setOrder({
        id: o?.id ?? "",
        slot: { label_hi: o?.delivery?.label_hi ?? "", label_en: o?.delivery?.label_en ?? "" },
        lines: view.lines,
        total: view.total,
        addressText: o?.address ? `${o.address.label}: ${o.address.text}` : "",
        placedAt: Date.now(),
      });
      setStack([{ screen: "home" }, { screen: "track" }]);
      setTimeout(() => (skipClearedToast.current = false), 500);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const resolvePayment = useCallback((r: PaymentResult) => {
    const req = paymentRef.current;
    if (req?.manual) {
      const leave = () => {
        setPaymentRequest(null);
        setStack((s) => (s[s.length - 1].screen === "pay" ? s.slice(0, -1) : s));
      };
      if (!r.approved || !r.mandate) return leave();
      // The store checks the signatures, the amount and the address the shopper approved.
      completeCart(req.checkout_id, { checkout_mandate: r.mandate.checkout_mandate, payment_mandate: r.mandate.payment_mandate })
        .then(placeManualOrder)
        .catch(() => {
          leave();
          showToast(translate(langRef.current, "payErrFailed"));
        });
      return;
    }
    widgetRef.current?.resolvePayment(r);
    if (!r.approved) {
      setPaymentRequest(null);
      setStack((s) => (s[s.length - 1].screen === "pay" ? s.slice(0, -1) : s));
    }
    // When approved, the Pay screen stays (busy) until the order or an end/cancel event arrives; if
    // the store turns the approval down, nothing arrives, so give up after a while.
    if (r.approved) {
      clearApprovalTimer();
      approvalTimer.current = setTimeout(() => {
        setPaymentRequest(null);
        setStack((s) => (s[s.length - 1].screen === "pay" ? s.slice(0, -1) : s));
        showToast(translate(langRef.current, "payErrFailed"));
      }, APPROVAL_TIMEOUT_MS);
    }
  }, [showToast, placeManualOrder]);

  // ------------------------------------------------------------ addresses
  const reloadAddresses = useCallback(async () => {
    try {
      setAddresses(await listAddresses());
      setAddressesError(false);
    } catch {
      setAddressesError(true);
    }
  }, []);
  useEffect(() => {
    void reloadAddresses();
  }, [reloadAddresses]);
  const preferred = useMemo(
    () => addresses.find((a) => a.id === preferredId) ?? addresses[0] ?? null,
    [addresses, preferredId],
  );
  const setPreferred = useCallback((id: string) => {
    setPreferredId(id);
    try {
      localStorage.setItem(ADDR_KEY, id);
    } catch {
      /* not remembered */
    }
  }, []);

  const setDemo = useCallback((patch: Partial<DemoState>) => setDemoState((d) => ({ ...d, ...patch })), []);

  const api: AppApi = {
    lang,
    setLang,
    t,
    route,
    go,
    back,
    goHome,
    phase,
    voiceOpen,
    openVoice,
    closeVoice,
    openTalk,
    endTalk,
    ask,
    toast,
    cart: shop.cart,
    cartId: shop.cartId,
    count: shop.count,
    total: shop.total,
    qtyOf: shop.qtyOf,
    isPending: shop.isPending,
    addItem: (p) => shop.add(p.id),
    incItem: (p) => shop.inc(p.id),
    decItem: (p) => shop.dec(p.id),
    clearCart: shop.clear,
    clearedTick: shop.clearedTick,
    requestCheckout,
    requestCancel,
    checkoutPending,
    startManualCheckout,
    paymentRequest,
    resolvePayment,
    order,
    ordersBadge: order !== null,
    addresses,
    addressesError,
    preferred,
    setPreferred,
    reloadAddresses,
    demo,
    setDemo,
    widgetRef,
    bump: shop.bump,
  };

  return (
    <LangContext.Provider value={lang}>
      <AppContext.Provider value={api}>
        {children}
      </AppContext.Provider>
    </LangContext.Provider>
  );
}
