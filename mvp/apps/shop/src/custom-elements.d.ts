import type { DetailedHTMLProps, HTMLAttributes } from "react";
import type { TalkToBuyAssistant } from "@talktobuy/assistant-widget";

type AssistantAttrs = DetailedHTMLProps<HTMLAttributes<TalkToBuyAssistant>, TalkToBuyAssistant> & {
  ticket?: string;
  "ticket-url"?: string;
  "server-url"?: string;
  language?: string;
  "show-translation"?: "true" | "false";
  "media-mode"?: "avatar" | "audio_only";
  "avatar-audio"?: "muxed" | "separate";
};

declare module "react" {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace JSX {
    interface IntrinsicElements {
      "talktobuy-assistant": AssistantAttrs;
    }
  }
}
