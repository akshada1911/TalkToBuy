export const SHOPPER_ID = "u-ghanshyam";

// Empty in local dev (Vite proxies /v1 with WebSockets); the session server's Cloud Run URL when deployed.
export const SESSION_SERVER_URL: string = import.meta.env.VITE_PUBLIC_SESSION_SERVER_URL ?? "";

const PARAMS = new URLSearchParams(location.search);
// Cost control: English captions of the assistant's Hindi only on the judges' screen (?en=1).
export const SHOW_ENGLISH = PARAMS.get("en") === "1";
export const URL_LANG = PARAMS.get("lang");
