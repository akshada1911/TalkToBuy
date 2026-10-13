import { credentialToJson, postJson, toCreationOptions } from "./webauthn";

/**
 * One-time WebAuthn registration of the shopper's fingerprint (platform authenticator) with the
 * demo store's payment surface: /payment/webauthn/register/options → navigator.credentials.create()
 * → /payment/webauthn/register/verify.
 */
export async function registerCredential(shopperId: string): Promise<void> {
  const opts = await postJson<Record<string, unknown>>("/payment/webauthn/register/options", { shopper_id: shopperId });
  const publicKey = toCreationOptions(opts);
  const cred = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential | null;
  if (!cred) throw new Error("registration cancelled");
  const res = await postJson<{ ok?: boolean }>("/payment/webauthn/register/verify", {
    shopper_id: shopperId,
    credential: credentialToJson(cred),
  });
  if (!res?.ok) throw new Error("registration not accepted");
}

/**
 * The assert/options endpoint says no credential is registered yet with 404/409, or with the store's
 * own error: 400 and the code NOT_REGISTERED.
 */
export function needsRegistration(status: number, body?: unknown): boolean {
  if (status === 404 || status === 409) return true;
  const messages = (body as { messages?: { code?: string }[] } | null)?.messages;
  return messages?.[0]?.code === "NOT_REGISTERED";
}
