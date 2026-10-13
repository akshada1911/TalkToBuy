import type { CatalogProduct } from "./api";
import type { Lang } from "./lang";
import type { StringKey } from "./i18n";

/** The tiles on Home and the chips on the list. Colours and drawings come from the design sprite. */
export interface CategoryMeta {
  id: string;
  label: StringKey;
  icon: string;
  tint: string;
}

export const CATEGORIES: CategoryMeta[] = [
  { id: "produce", label: "cat_produce", icon: "ic-tomato", tint: "#F6DDD6" },
  { id: "dairy", label: "cat_dairy", icon: "ic-milk", tint: "#E3EEF0" },
  { id: "flours", label: "cat_flours", icon: "ic-atta", tint: "#EFE5CB" },
  { id: "staples", label: "cat_staples", icon: "ic-rice", tint: "#E6EEE2" },
  { id: "biscuits", label: "cat_biscuits", icon: "ic-biscuits", tint: "#F4E3CB" },
  { id: "snacks", label: "cat_snacks", icon: "ic-chips", tint: "#F9E1D6" },
  { id: "beverages", label: "cat_beverages", icon: "ic-juice", tint: "#F9E8D2" },
  { id: "spices", label: "cat_spices", icon: "ic-herbs", tint: "#E2EEDA" },
  { id: "baking", label: "cat_baking", icon: "ic-butter", tint: "#F8EDC0" },
  { id: "home", label: "cat_home", icon: "ic-tea", tint: "#EBDCCF" },
];

const BY_ID = new Map(CATEGORIES.map((c) => [c.id, c]));

export function categoryMeta(id: string): CategoryMeta {
  return BY_ID.get(id) ?? CATEGORIES[CATEGORIES.length - 1];
}

/** The product's name in the shopper's language (Hindi name in Hindi mode). */
export function displayName(p: Pick<CatalogProduct, "name" | "local_name">, lang: Lang): string {
  return lang === "hi" && p.local_name ? p.local_name : p.name;
}
