import { Icon } from "../design/Icon";
import { useApp } from "../state";

export function BottomNav() {
  const { t, route, go, goHome, openTalk, count, ordersBadge } = useApp();
  const on = (s: string) => (route.screen === s ? "on" : "");
  return (
    <nav className="nav" aria-label={t("mainNav")}>
      <button type="button" className={on("home")} onClick={goHome} aria-label={t("navHome")}>
        <Icon name="i-home" size={24} />
        {t("navHome")}
      </button>
      <button type="button" className={on("list")} onClick={() => go({ screen: "list", listCat: "all", query: "" })} aria-label={t("navBrowse")}>
        <Icon name="i-grid" size={24} />
        {t("navBrowse")}
      </button>
      <button type="button" className="talk" onClick={openTalk} aria-label="TalkToBuy">
        <span className="disc">
          <Icon name="i-mic" size={28} stroke={2.2} />
        </span>
        {t("navTalk")}
      </button>
      <button type="button" onClick={() => go({ screen: "cart" })} aria-label={t("navCart")}>
        <span className="icon-wrap">
          <Icon name="i-cart" size={24} />
          {count > 0 && <span className="count">{count}</span>}
        </span>
        {t("navCart")}
      </button>
      <button type="button" onClick={() => go({ screen: "track" })} disabled={!ordersBadge} aria-label={t("navOrders")}>
        <Icon name="i-bag" size={24} />
        {t("navOrders")}
      </button>
    </nav>
  );
}
