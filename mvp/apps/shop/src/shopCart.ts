import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import type { TalkToBuyAssistant, UiCart } from "@talktobuy/assistant-widget";
import { ApiError, createCart, getCart, linesOf, putCart, type StoreCart } from "./api";

const CART_KEY = "ttb-cart";

const countOf = (cart: UiCart | null) => cart?.lines.reduce((n, l) => n + l.qty, 0) ?? 0;
const toUi = (v: StoreCart): UiCart => ({ lines: v.lines, item_count: v.item_count, total: v.total });
const usable = (v: StoreCart) => v.status === "incomplete" || v.status === "ready_for_complete";

function remember(id: string | null) {
  try {
    if (id) localStorage.setItem(CART_KEY, id);
    else localStorage.removeItem(CART_KEY);
  } catch {
    /* not remembered */
  }
}

interface Options {
  widgetRef: RefObject<TalkToBuyAssistant>;
  /** The cart went from having items to empty (cleared by the button, by voice, or cancelled). */
  onCleared: () => void;
  /** A change could not be saved. */
  onError: () => void;
}

/**
 * The one cart. It lives in the store; the shop edits it by tapping, and the assistant edits the same
 * cart by voice. Changes from either side end up here: the shop's own edits come back from the
 * store, the assistant's come from its `cart` events (which carry the cart id).
 */
export function useShopCart({ widgetRef, onCleared, onError }: Options) {
  const [cart, setCart] = useState<UiCart | null>(null);
  const [cartId, setCartId] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, number>>({});
  const [clearedTick, setClearedTick] = useState(0);
  const [bump, setBump] = useState(0);
  const cartRef = useRef<UiCart | null>(null);
  const idRef = useRef<string | null>(null);
  const chain = useRef<Promise<unknown>>(Promise.resolve());
  const cb = useRef({ onCleared, onError });
  cb.current = { onCleared, onError };

  const set = useCallback((next: UiCart | null, id: string | null) => {
    const before = countOf(cartRef.current);
    cartRef.current = next;
    idRef.current = id;
    setCart(next);
    setCartId(id);
    remember(id);
    setBump((n) => n + 1);
    if (before > 0 && countOf(next) === 0) {
      setClearedTick((n) => n + 1);
      cb.current.onCleared();
    }
  }, []);

  /** The assistant changed the cart (voice), or the server refreshed it. */
  const fromAssistant = useCallback(
    (next: UiCart, id: string | null) => {
      set(next, id);
      setPending({});
    },
    [set],
  );

  /** The cart is gone (ordered): empty, with no cart id, and no "cleared" effect. */
  const forget = useCallback(() => {
    cartRef.current = null;
    idRef.current = null;
    setCart(null);
    setCartId(null);
    remember(null);
    setPending({});
  }, []);

  // Pick up the cart from the last visit (it is in the store).
  useEffect(() => {
    let id: string | null = null;
    try {
      id = localStorage.getItem(CART_KEY);
    } catch {
      /* none */
    }
    if (!id) return;
    getCart(id)
      .then((v) => {
        if (usable(v) && !cartRef.current) set(toUi(v), v.id);
        else if (!usable(v)) remember(null);
      })
      .catch(() => remember(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const write = async (lines: Record<string, number>): Promise<StoreCart> => {
    const id = idRef.current;
    if (!id) return createCart(lines);
    try {
      return await putCart(id, lines);
    } catch (err) {
      // The cart is finished or gone (ordered, or cancelled by voice): start a fresh one.
      if (err instanceof ApiError && (err.status === 404 || err.status === 409)) return createCart(lines);
      throw err;
    }
  };

  /** One change at a time, in order, so quick taps never overwrite each other. */
  const enqueue = (job: () => Promise<void>) => {
    chain.current = chain.current.then(job, job);
  };

  const change = useCallback(
    (productId: string, delta: number) => {
      enqueue(async () => {
        setPending((p) => ({ ...p, [productId]: Date.now() }));
        try {
          const lines = linesOf(cartRef.current);
          const qty = Math.max(0, Math.min(100, (lines[productId] ?? 0) + delta));
          if (qty === 0) delete lines[productId];
          else lines[productId] = qty;
          const view = await write(lines);
          set(toUi(view), view.id);
          widgetRef.current?.syncCart(); // a running conversation shows the change at once
        } catch {
          cb.current.onError();
        } finally {
          setPending(({ [productId]: _done, ...rest }) => rest);
        }
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [set, widgetRef],
  );

  const clear = useCallback(() => {
    enqueue(async () => {
      const id = idRef.current;
      if (!id || countOf(cartRef.current) === 0) return;
      try {
        const view = await putCart(id, {});
        set(toUi(view), view.id);
        widgetRef.current?.syncCart();
      } catch {
        cb.current.onError();
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [set, widgetRef]);

  return {
    cart,
    cartId,
    count: countOf(cart),
    total: cart?.total ?? 0,
    qtyOf: (productId: string) => cart?.lines.find((l) => l.product.id === productId)?.qty ?? 0,
    isPending: (productId: string) => productId in pending,
    clearedTick,
    bump,
    add: (productId: string) => change(productId, 1),
    inc: (productId: string) => change(productId, 1),
    dec: (productId: string) => change(productId, -1),
    clear,
    fromAssistant,
    forget,
    /** Re-read the cart from the store (after the shop chose a slot and address, or ordered). */
    refresh: async () => {
      const id = idRef.current;
      if (!id) return null;
      const v = await getCart(id);
      return v;
    },
    cartRef,
    idRef,
  };
}
