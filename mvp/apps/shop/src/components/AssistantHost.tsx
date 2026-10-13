import { Icon } from "../design/Icon";
import { SESSION_SERVER_URL, SHOW_ENGLISH } from "../config";
import { useApp } from "../state";

/**
 * The one assistant for the whole app. It stays mounted so the conversation and its cart survive
 * moving between screens: the Talk page shows it full screen, the voice sheet as a bottom sheet,
 * and elsewhere it is hidden (and its microphone muted, so nothing is heard in the background).
 */
export function AssistantHost() {
  const { lang, t, route, voiceOpen, closeVoice, endTalk, go, widgetRef, preferred, cartId } = useApp();
  const layout = route.screen === "talk" ? "page" : voiceOpen ? "sheet" : "hidden";
  const visible = layout !== "hidden";
  return (
    <>
      {layout === "sheet" && <div className="sheet-scrim" />}
      <div className="assistant-host" data-layout={layout}>
        {visible && (
          <div className="host-top">
            {layout === "page" ? (
              <button type="button" className="ghost-round" onClick={endTalk} aria-label={t("endTalk")}>
                <Icon name="i-close" size={20} stroke={2.2} />
              </button>
            ) : (
              <span />
            )}
            {layout === "page" && <span className="title">{t("assistantTitle")}</span>}
            <span style={{ display: "flex", gap: 8 }}>
              <button type="button" className="ghost-round" onClick={() => go({ screen: "settings" })} aria-label={t("settings")}>
                <Icon name="i-gear" size={21} />
              </button>
              {layout === "sheet" && (
                <button type="button" className="ghost-round" onClick={closeVoice} aria-label={t("close")}>
                  <Icon name="i-close" size={20} stroke={2.2} />
                </button>
              )}
            </span>
          </div>
        )}
        {/* key={lang}: switching language starts a fresh assistant in that language. */}
        <talktobuy-assistant
          key={lang}
          ref={widgetRef}
          ticket-url={`${SESSION_SERVER_URL}/v1/demo-ticket`}
          server-url={SESSION_SERVER_URL}
          language={lang}
          layout={layout === "sheet" ? "sheet" : "page"}
          muted={visible ? undefined : ""}
          preferred-address={preferred?.id}
          cart-id={cartId ?? undefined}
          show-translation={SHOW_ENGLISH && lang === "hi" ? "true" : "false"}
          media-mode="audio_only"
          avatar-audio="muxed"
        />
      </div>
    </>
  );
}
