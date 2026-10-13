import { Icon } from "../design/Icon";
import { useApp } from "../state";

interface Props {
  qty: number;
  name: string;
  busy: boolean;
  onDec: () => void;
  onInc: () => void;
  size?: "normal" | "big" | "compact";
  label?: string;
}

/** − qty + : each tap asks the assistant, so it shows a spinner until the cart answers. */
export function Stepper({ qty, name, busy, onDec, onInc, size = "normal", label }: Props) {
  const { t } = useApp();
  const iconSize = size === "big" ? 22 : 20;
  return (
    <div className={`stepper ${size === "big" ? "big" : size === "compact" ? "compact" : ""}`}>
      <button type="button" onClick={onDec} disabled={busy} aria-label={t("removeOne", { name })}>
        <Icon name="i-minus" size={iconSize} />
      </button>
      <span className="qty" aria-live="polite">
        {busy ? <span className="spinner" style={{ display: "inline-block" }} /> : (label ?? qty)}
      </span>
      <button type="button" onClick={onInc} disabled={busy} aria-label={t("addOne", { name })}>
        <Icon name="i-plus" size={iconSize} />
      </button>
    </div>
  );
}
