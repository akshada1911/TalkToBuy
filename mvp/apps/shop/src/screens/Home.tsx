import { browse, lastOrderProducts, shortAddress, type CatalogProduct } from "../api";
import shopkeeper from "../assets/shopkeeper.png";
import { CATEGORIES } from "../catalog";
import { BottomNav } from "../components/BottomNav";
import { CartBar } from "../components/CartBar";
import { ProductCard } from "../components/ProductCard";
import { VoiceButton } from "../components/TopBar";
import { Icon } from "../design/Icon";
import { useLoad } from "../hooks";
import { useApp } from "../state";

function Rail({ title, products, onSeeAll }: { title: string; products: CatalogProduct[]; onSeeAll?: () => void }) {
  const { t } = useApp();
  if (products.length === 0) return null;
  return (
    <div className="rail" style={{ paddingTop: 14 }}>
      <div className="rail-head">
        <span className="section-title">{title}</span>
        {onSeeAll && (
          <button type="button" className="btn-link" onClick={onSeeAll}>
            {t("seeAll")}
          </button>
        )}
      </div>
      <div className="hs">
        {products.map((p) => (
          <ProductCard key={p.id} product={p} variant="rail" />
        ))}
      </div>
    </div>
  );
}

export function Home() {
  const { t, go, openTalk, preferred } = useApp();
  const popular = useLoad(() => browse({ limit: 10 }), []);
  const fresh = useLoad(() => browse({ category: "produce", limit: 10 }), []);
  const again = useLoad(() => lastOrderProducts(), []);
  const openCat = (id: string) => go({ screen: "list", listCat: id, query: "" });

  return (
    <div className="screen">
      <div className="scroll grow" style={{ paddingBottom: 176 }}>
        <div className="home-head">
          <div className="home-head-row">
            <button type="button" className="addr-btn" onClick={() => go({ screen: "address" })} aria-label={t("changeAddress")}>
              <span className="eyebrow">{t("deliveryEyebrow")}</span>
              <span className="where">
                <span>{preferred ? `${preferred.label} · ${shortAddress(preferred)}` : t("deliveryAddress")}</span>
                <Icon name="i-down" size={16} />
              </span>
            </button>
            <button type="button" className="account-btn" onClick={() => go({ screen: "settings" })} aria-label={t("accountSettings")}>
              <Icon name="i-user" size={22} />
            </button>
          </div>
          <div className="search-row">
            <button type="button" className="search-fake" onClick={() => go({ screen: "list", listCat: "all", query: "" })}>
              <Icon name="i-search" size={20} />
              {t("searchPlaceholder")}
            </button>
            <VoiceButton />
          </div>
        </div>

        <div className="hs" style={{ paddingTop: 16 }}>
          <button type="button" className="promo" style={{ background: "var(--amber)", color: "var(--ink)" }} onClick={() => openCat("produce")}>
            <span className="text">
              <span className="eyebrow">{t("promoFreshEyebrow")}</span>
              <span className="head">{t("promoFreshHead")}</span>
              <span className="cta">{t("promoFreshCta")}</span>
            </span>
            <span className="art">
              <Icon name="ic-banana" size={58} />
              <Icon name="ic-tomato" size={58} />
            </span>
          </button>
          <button type="button" className="promo" style={{ background: "var(--forest-2)", color: "#fff" }} onClick={openTalk}>
            <span className="text">
              <span className="eyebrow" style={{ color: "var(--amber)" }}>
                TalkToBuy
              </span>
              <span className="head">{t("promoTalkHead")}</span>
              <span className="cta" style={{ color: "#d8e6de" }}>
                {t("promoTalkCta")}
              </span>
            </span>
            <img src={shopkeeper} alt="" />
          </button>
          <button type="button" className="promo" style={{ background: "#e3eef0", color: "var(--ink)" }} onClick={() => openCat("dairy")}>
            <span className="text">
              <span className="eyebrow">{t("promoDairyEyebrow")}</span>
              <span className="head">{t("promoDairyHead")}</span>
              <span className="cta">{t("promoDairyCta")}</span>
            </span>
            <span className="art">
              <Icon name="ic-milk" size={58} />
              <Icon name="ic-butter" size={58} />
            </span>
          </button>
        </div>

        <div className="stack gap12" style={{ padding: "20px 16px 0" }}>
          <span className="section-title">{t("shopByCategory")}</span>
          <div className="cat-grid">
            {CATEGORIES.map((c) => (
              <button type="button" key={c.id} className="cat" onClick={() => openCat(c.id)}>
                <span className="tile" style={{ background: c.tint }}>
                  <Icon name={c.icon} size={44} />
                </span>
                <span className="name">{t(c.label)}</span>
              </button>
            ))}
          </div>
        </div>

        <Rail title={t("buyAgain")} products={again.data ?? []} onSeeAll={() => go({ screen: "list", listCat: "all", query: "" })} />
        <Rail title={t("popular")} products={popular.data?.items ?? []} onSeeAll={() => go({ screen: "list", listCat: "all", query: "" })} />
        <Rail title={t("freshVeg")} products={fresh.data?.items ?? []} onSeeAll={() => openCat("produce")} />
      </div>
      <CartBar />
      <BottomNav />
    </div>
  );
}
