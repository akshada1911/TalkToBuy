import { useState } from "react";
import type { CatalogProduct } from "../api";
import { categoryMeta } from "../catalog";
import { Icon } from "../design/Icon";

interface Props {
  product: Pick<CatalogProduct, "image" | "category" | "name">;
  size?: number;
}

/** The product photo; the category drawing shows if there is no photo or it fails to load. */
export function ProductImage({ product, size = 58 }: Props) {
  const [failed, setFailed] = useState(false);
  const meta = categoryMeta(product.category);
  if (product.image && !failed) {
    return <img src={product.image} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} />;
  }
  return (
    <span className="fallback-art" style={{ background: meta.tint }} aria-hidden="true">
      <Icon name={meta.icon} size={size} />
    </span>
  );
}
