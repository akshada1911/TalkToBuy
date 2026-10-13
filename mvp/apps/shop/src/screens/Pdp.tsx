import { productDetail } from "../api";
import { categoryMeta, displayName } from "../catalog";
import { ProductCard } from "../components/ProductCard";
import { ProductImage } from "../components/ProductImage";
import { Stepper } from "../components/Stepper";
import { BackButton, VoiceButton } from "../components/TopBar";
import { Icon } from "../design/Icon";
import { useLoad } from "../hooks";
import { useApp } from "../state";

export function Pdp() {
  const { lang, t, route, go, count, qtyOf, isPending, addItem, incItem, decItem } = useApp();
  const id = route.pdpId ?? "";
  const { data: p, loading, error, reload } = useLoad(() => productDetail(id), [id]);

  if (!p) {
    return (
      <div className="screen">
        <div className="pdp-top">
          <BackButton float />
        </div>
        <div className="empty" style={{ marginTop: 120 }}>
          {error ? (
            <>
              <p>{t("loadError")}</p>
              <button type="button" className="btn btn-pill" onClick={reload}>
                {t("tryAgain")}
              </button>
            </>
          ) : (
            <p>{loading ? t("loading") : ""}</p>
          )}
        </div>
      </div>
    );
  }

  const name = displayName(p, lang);
  const meta = categoryMeta(p.category);
  const qty = qtyOf(p.id);
  const busy = isPending(p.id);
  const rows: [string, string][] = [];
  if (p.brand) rows.push([t("rowBrand"), p.brand]);
  rows.push([t("rowPack"), p.size]);
  rows.push([t("rowCategory"), t(meta.label)]);
  if (p.description) rows.push([t("rowAbout"), p.description]);
  if (p.usage) rows.push([t("rowUsage"), p.usage]);

  return (
    <div className="screen">
      <div className="scroll grow" style={{ paddingBottom: 110 }}>
        <div className="pdp-hero" style={{ background: meta.tint }}>
          <ProductImage product={p} size={140} />
        </div>
        <div className="pdp-body">
          <div className="stack" style={{ gap: 6 }}>
            {p.brand && (
              <span className="eyebrow" style={{ color: "var(--muted)" }}>
                {p.brand}
              </span>
            )}
            <h1 className="display" style={{ fontWeight: 800, fontSize: 26, lineHeight: 1.1, letterSpacing: "-0.02em" }}>
              {name}
            </h1>
            {!p.in_stock && <span style={{ color: "var(--danger)", fontWeight: 700 }}>{t("outOfStock")}</span>}
          </div>

          <div className="stack" style={{ gap: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 700 }}>{t("packSize")}</span>
            <div className="hs" style={{ padding: 0, margin: 0 }}>
              <span className="pack-chip" aria-current="true">
                <b style={{ fontSize: 14 }}>{p.size}</b>
                <span style={{ fontSize: 13 }}>₹{p.price}</span>
              </span>
            </div>
          </div>

          <div className="panel stack" style={{ gap: 4 }}>
            <span className="display" style={{ fontWeight: 800, fontSize: 28 }}>
              ₹{p.price}
            </span>
            <span className="psub">{t("inclTaxes")}</span>
          </div>

          <div className="panel" style={{ padding: "4px 14px" }}>
            <span className="display" style={{ display: "block", fontWeight: 700, fontSize: 16, padding: "12px 0 6px" }}>
              {t("productDetails")}
            </span>
            {rows.map(([k, v]) => (
              <div className="info-row" key={k}>
                <span>{k}</span>
                <span>{v}</span>
              </div>
            ))}
            {p.image_credit && (
              <div className="info-row" style={{ fontSize: 12 }}>
                <span>{t("imageCredit", { credit: p.image_credit })}</span>
                <span />
              </div>
            )}
          </div>

          {p.similar.length > 0 && (
            <div className="stack gap10" style={{ margin: "0 -16px" }}>
              <span className="display" style={{ fontWeight: 700, fontSize: 18, padding: "0 16px" }}>
                {t("similar")}
              </span>
              <div className="hs">
                {p.similar.map((s) => (
                  <ProductCard key={s.id} product={s} variant="rail" />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="pdp-top">
        <BackButton float />
        <div style={{ display: "flex", gap: 8 }}>
          <VoiceButton round />
          <button type="button" className="round-btn float" style={{ position: "relative" }} onClick={() => go({ screen: "cart" })} aria-label={t("openCart")}>
            <Icon name="i-cart" size={22} />
            {count > 0 && <span className="badge-dot">{count}</span>}
          </button>
        </div>
      </div>

      <div className="bottom-bar">
        <div className="total">
          <small>{p.size}</small>
          <b>₹{p.price}</b>
        </div>
        {!p.in_stock ? (
          <button type="button" className="btn btn-forest" style={{ flex: 1 }} disabled>
            {t("outOfStock")}
          </button>
        ) : qty === 0 ? (
          <button type="button" className="btn btn-forest" style={{ flex: 1 }} onClick={() => addItem(p)} disabled={busy}>
            {busy ? <span className="spinner" /> : t("addToCart")}
          </button>
        ) : (
          <div style={{ flex: 1 }}>
            <Stepper size="big" qty={qty} label={t("inCart", { n: qty })} name={name} busy={busy} onDec={() => decItem(p)} onInc={() => incItem(p)} />
          </div>
        )}
      </div>
    </div>
  );
}
