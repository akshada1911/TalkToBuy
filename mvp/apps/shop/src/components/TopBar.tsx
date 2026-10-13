import type { ReactNode } from "react";
import { Icon } from "../design/Icon";
import { useApp } from "../state";

export function BackButton({ float }: { float?: boolean }) {
  const { t, back } = useApp();
  return (
    <button type="button" className={`round-btn ${float ? "float" : ""}`} onClick={back} aria-label={t("back")}>
      <Icon name="i-back" size={20} stroke={2.2} />
    </button>
  );
}

/** Back button + title (+ optional subtitle and a trailing control). */
export function TopBar({ title, sub, right, plain }: { title: string; sub?: string; right?: ReactNode; plain?: boolean }) {
  return (
    <div className={plain ? "topbar-plain" : "topbar"}>
      <BackButton />
      {plain ? (
        <span className="page-title">{title}</span>
      ) : (
        <div className="topbar-title">
          <b>{title}</b>
          {sub && <small>{sub}</small>}
        </div>
      )}
      {right}
    </div>
  );
}

/** The amber mic button that opens the voice sheet. */
export function VoiceButton({ round }: { round?: boolean }) {
  const { t, openVoice } = useApp();
  return (
    <button type="button" className={`mic-btn ${round ? "round" : ""}`} onClick={openVoice} aria-label={t("orderByTalking")}>
      <Icon name="i-mic" size={20} stroke={2.2} />
    </button>
  );
}
