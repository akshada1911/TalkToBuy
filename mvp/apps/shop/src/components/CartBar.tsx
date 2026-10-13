import { Icon } from "../design/Icon";
import { useApp } from "../state";

/** The dark "N items · ₹total · View cart" bar above the navigation. */
export function CartBar() {
  const { t, count, total, go } = useApp();
  if (count === 0) return null;
  return (
    <div className="cartbar line">
      <div className="info">
        <small>{count === 1 ? t("itemCount1") : t("itemCount", { n: count })}</small>
        <b>₹{total}</b>
      </div>
      <button type="button" className="btn btn-amber" onClick={() => go({ screen: "cart" })}>
        <Icon name="i-cart" size={20} />
        {t("viewCart")}
      </button>
    </div>
  );
}
