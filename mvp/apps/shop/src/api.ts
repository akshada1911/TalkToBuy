import { SHOPPER_ID } from "./config";

/** A product as the shop's browse screens see it (from the demo store's /demo/catalog). */
export interface CatalogProduct {
  id: string;
  name: string;
  local_name: string;
  brand: string | null;
  size: string;
  price: number;
  image: string;
  image_credit: string;
  category: string;
  in_stock: boolean;
  description: string;
  usage: string | null;
}

export interface ProductDetail extends CatalogProduct {
  similar: CatalogProduct[];
}

export interface BrowseResult {
  items: CatalogProduct[];
  total: number;
  limit: number;
  offset: number;
}

export interface SavedAddress {
  id: string;
  label: string;
  name: string;
  line1: string;
  area: string;
  city: string;
  pincode: string;
  phone: string;
}

export type NewAddress = Omit<SavedAddress, "id">;

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return (await res.json()) as T;
}

export function browse(params: { category?: string; q?: string; limit?: number; offset?: number }): Promise<BrowseResult> {
  const qs = new URLSearchParams();
  if (params.category) qs.set("category", params.category);
  if (params.q) qs.set("q", params.q);
  qs.set("limit", String(params.limit ?? 40));
  qs.set("offset", String(params.offset ?? 0));
  return getJson<BrowseResult>(`/demo/catalog?${qs}`);
}

export function productDetail(id: string): Promise<ProductDetail> {
  return getJson<ProductDetail>(`/demo/catalog/${encodeURIComponent(id)}`);
}

export function listAddresses(): Promise<SavedAddress[]> {
  return getJson<SavedAddress[]>(`/demo/shoppers/${SHOPPER_ID}/addresses`);
}

export async function addAddress(body: NewAddress): Promise<SavedAddress> {
  const res = await fetch(`/demo/shoppers/${SHOPPER_ID}/addresses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`address: ${res.status}`);
  return (await res.json()) as SavedAddress;
}

/** The products from the shopper's last order, newest first (for "Buy it again"). */
export async function lastOrderProducts(): Promise<CatalogProduct[]> {
  try {
    const data = await getJson<{ lines: { product: { id: string } }[] }>(`/demo/shoppers/${SHOPPER_ID}/last-order`);
    const ids = data.lines.map((l) => l.product.id);
    const found = await Promise.all(ids.map((id) => productDetail(id).catch(() => null)));
    return found.filter((p): p is ProductDetail => p !== null);
  } catch {
    return [];
  }
}

export function shortAddress(a: SavedAddress): string {
  return `${a.line1.split(",")[0]}, ${a.area}`;
}

export function fullAddress(a: SavedAddress): string {
  return `${a.line1}, ${a.area}, ${a.city} ${a.pincode}`;
}
