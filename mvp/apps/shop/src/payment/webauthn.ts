/** WebAuthn JSON ⇄ ArrayBuffer helpers (base64url, as produced by py_webauthn / SimpleWebAuthn). */

export function b64urlToBuffer(s: string): ArrayBuffer {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(s.length / 4) * 4, "=");
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer;
}

export function bufferToB64url(buf: ArrayBuffer | ArrayBufferView | null | undefined): string | null {
  if (!buf) return null;
  const bytes = buf instanceof ArrayBuffer ? new Uint8Array(buf) : new Uint8Array(buf.buffer, buf.byteOffset, buf.byteLength);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

type Json = Record<string, unknown>;
interface CredDescJson {
  id: string;
  type?: string;
  transports?: string[];
}

/** Servers sometimes wrap options as `{publicKey: {...}}`. */
function unwrap(o: Json): Json {
  return (o.publicKey as Json | undefined) ?? o;
}

const toDescriptors = (list: unknown): PublicKeyCredentialDescriptor[] | undefined =>
  Array.isArray(list)
    ? (list as CredDescJson[]).map((d) => ({
        id: b64urlToBuffer(d.id),
        type: "public-key",
        transports: d.transports as AuthenticatorTransport[] | undefined,
      }))
    : undefined;

export function toRequestOptions(json: Json): PublicKeyCredentialRequestOptions {
  const o = unwrap(json);
  return {
    ...(o as object),
    challenge: b64urlToBuffer(o.challenge as string),
    allowCredentials: toDescriptors(o.allowCredentials),
  } as PublicKeyCredentialRequestOptions;
}

export function toCreationOptions(json: Json): PublicKeyCredentialCreationOptions {
  const o = unwrap(json);
  const user = o.user as Json;
  return {
    ...(o as object),
    challenge: b64urlToBuffer(o.challenge as string),
    user: { ...(user as object), id: b64urlToBuffer(user.id as string) },
    excludeCredentials: toDescriptors(o.excludeCredentials),
  } as PublicKeyCredentialCreationOptions;
}

/** Serialise a credential from create() or get() to the JSON shape servers expect. */
export function credentialToJson(cred: PublicKeyCredential): Json {
  const r = cred.response as AuthenticatorAttestationResponse & AuthenticatorAssertionResponse;
  const response: Json = { clientDataJSON: bufferToB64url(r.clientDataJSON) };
  if ("attestationObject" in r && r.attestationObject) {
    response.attestationObject = bufferToB64url(r.attestationObject);
    response.transports = typeof r.getTransports === "function" ? r.getTransports() : [];
  }
  if ("authenticatorData" in r && r.authenticatorData) {
    response.authenticatorData = bufferToB64url(r.authenticatorData);
    response.signature = bufferToB64url(r.signature);
    response.userHandle = bufferToB64url(r.userHandle);
  }
  return {
    id: cred.id,
    rawId: bufferToB64url(cred.rawId),
    type: cred.type,
    response,
    authenticatorAttachment: (cred as PublicKeyCredential & { authenticatorAttachment?: string | null }).authenticatorAttachment ?? null,
    clientExtensionResults: cred.getClientExtensionResults(),
  };
}

export class HttpError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`HTTP ${status}`);
  }
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) throw new HttpError(res.status, data);
  return data as T;
}
