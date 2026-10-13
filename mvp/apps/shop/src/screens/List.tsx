import { useEffect, useState } from "react";
import { browse, type CatalogProduct } from "../api";
import { CATEGORIES } from "../catalog";
import { BottomNav } from "../components/BottomNav";
import { CartBar } from "../components/CartBar";
import { ProductCard } from "../components/ProductCard";
import { BackButton, VoiceButton } from "../components/TopBar";
import { Icon } from "../design/Icon";
import { useDebounced } from "../hooks";
import { useApp } from "../state";

const PAGE = 24;

export function List() {
  const { t, route, openVoice } = useApp();
  const [cat, setCat] = useState(route.listCat ?? "all");
  const [query, setQuery] = useState(route.query ?? "");
  const q = useDebounced(query.trim(), 250);
  const [items, setItems] = useState<CatalogProduct[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [nonce, setNonce] = useState(0);

  // A new category or search starts the list again.
  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(false);
    browse({ category: cat === "all" ? undefined : cat, q: q || undefined, limit: PAGE, offset: 0 })
      .then((r) => {
        if (!live) return;
        setItems(r.items);
        setTotal(r.total);
      })
      .catch(() => live && setError(true))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [cat, q, nonce]);

  const more = () => {
    setLoading(true);
    browse({ category: cat === "all" ? undefined : cat, q: q || undefined, limit: PAGE, offset: items.length })
      .then((r) => setItems((cur) => [...cur, ...r.items]))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  const catLabel = cat === "all" ? t("catAllProducts") : t((CATEGORIES.find((c) => c.id === cat) ?? CATEGORIES[0]).label);
  const resultText = q
    ? total === 1
      ? t("resultFor", { q })
      : t("resultsFor", { n: total, q })
    : t("categoryCount", { cat: catLabel, n: total });

  return (
    <div className="screen">
      <div style={{ background: "#fff", borderBottom: "1px solid var(--line)", padding: "10px 16px 0", display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <BackButton />
          <label className="search-input">
            <Icon name="i-search" size={20} />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("searchPlaceholder")}
              aria-label={t("searchPlaceholder")}
            />
          </label>
          <VoiceButton />
        </div>
        <div className="hs chips">
          {[{ id: "all", label: t("catAll") }, ...CATEGORIES.map((c) => ({ id: c.id, label: t(c.label) }))].map((c) => (
            <button type="button" key={c.id} className={`chip ${cat === c.id ? "on" : ""}`} aria-pressed={cat === c.id} onClick={() => setCat(c.id)}>
              {c.label}
            </button>
          ))}
        </div>
      </div>

      <div className="scroll grow stack gap10" style={{ padding: "12px 16px 176px" }}>
        <span className="hint-text">{loading && items.length === 0 ? t("loading") : resultText}</span>
        {error && (
          <div className="empty">
            <p>{t("loadError")}</p>
            <button type="button" className="btn btn-pill" onClick={() => setNonce((n) => n + 1)}>
              {t("tryAgain")}
            </button>
          </div>
        )}
        {!loading && !error && items.length === 0 && (
          <div className="empty">
            <span className="section-title">{t("nothingFound")}</span>
            <p>{t("nothingFoundHint")}</p>
            <button type="button" className="btn btn-pill" onClick={openVoice}>
              {t("askShopkeeper")}
            </button>
          </div>
        )}
        <div className="grid2">
          {items.map((p) => (
            <ProductCard key={p.id} product={p} variant="grid" />
          ))}
        </div>
        {items.length < total && (
          <button type="button" className="btn btn-outline" style={{ alignSelf: "center" }} onClick={more} disabled={loading}>
            {loading ? t("loading") : t("showMore")}
          </button>
        )}
      </div>
      <CartBar />
      <BottomNav />
    </div>
  );
}
