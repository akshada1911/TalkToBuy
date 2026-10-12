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

/** The assert/options endpoint answers 404 or 409 when no credential is registered yet. */
export function needsRegistration(status: number): boolean {
  return status === 404 || status === 409;
}
