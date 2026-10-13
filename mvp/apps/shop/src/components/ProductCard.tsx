import type { CatalogProduct } from "../api";
import { categoryMeta, displayName } from "../catalog";
import { useApp } from "../state";
import { ProductImage } from "./ProductImage";
import { Stepper } from "./Stepper";

interface Props {
  product: CatalogProduct;
  variant: "rail" | "grid";
}

export function ProductCard({ product: p, variant }: Props) {
  const { lang, t, go, qtyOf, isPending, addItem, incItem, decItem } = useApp();
  const qty = qtyOf(p.id);
  const busy = isPending(p.id);
  const name = displayName(p, lang);
  const meta = categoryMeta(p.category);
  return (
    <div className={`pcard ${variant === "rail" ? "rail-card" : "grid-card"}`}>
      <button type="button" className="open" onClick={() => go({ screen: "pdp", pdpId: p.id })} aria-label={t("details", { name })}>
        <span className="pimg" style={{ background: meta.tint }}>
          <ProductImage product={p} />
          {!p.in_stock && <span className="badge">{t("outOfStock")}</span>}
        </span>
        <span className="pname clamp2">{name}</span>
        <span className="psub">{p.size}</span>
        <span className="pprice">₹{p.price}</span>
      </button>
      {!p.in_stock ? (
        <button type="button" className="add-btn" disabled>
          {t("outOfStock")}
        </button>
      ) : qty === 0 ? (
        <button type="button" className="add-btn" onClick={() => addItem(p)} disabled={busy} aria-label={t("addTo", { name })}>
          {busy ? <span className="spinner" /> : t("add")}
        </button>
      ) : (
        <Stepper qty={qty} name={name} busy={busy} onDec={() => decItem(p)} onInc={() => incItem(p)} />
      )}
    </div>
  );
}
