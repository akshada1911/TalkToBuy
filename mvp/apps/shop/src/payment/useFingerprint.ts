import { useState } from "react";
import type { PaymentRequestedDetail, PaymentResult } from "@talktobuy/assistant-widget";
import { SHOPPER_ID } from "../config";
import type { StringKey } from "../i18n";
import { needsRegistration, registerCredential } from "./register";
import { HttpError, credentialToJson, postJson, toRequestOptions } from "./webauthn";

interface ApproveResponse {
  checkout_mandate: string;
  payment_mandate: string;
  expires_at?: string | number;
}

export type PayStatus = "ready" | "working" | "registering" | "error";

/**
 * The shop's OWN payment step (trusted surface): payment is approved only here, with the
 * fingerprint, never by voice. Flow: assert/options → navigator.credentials.get() → /payment/approve
 * → the result goes back to the assistant with the mandate.
 */
export function useFingerprint(request: PaymentRequestedDetail | null, onResolve: (r: PaymentResult) => void) {
  const [status, setStatus] = useState<PayStatus>("ready");
  const [error, setError] = useState<StringKey | null>(null);

  async function assertOptions(checkoutId: string): Promise<Record<string, unknown>> {
    const body = { shopper_id: SHOPPER_ID, checkout_id: checkoutId };
    try {
      return await postJson<Record<string, unknown>>("/payment/webauthn/assert/options", body);
    } catch (err) {
      if (err instanceof HttpError && needsRegistration(err.status, err.body)) {
        setStatus("registering");
        await registerCredential(SHOPPER_ID);
        setStatus("working");
        return await postJson<Record<string, unknown>>("/payment/webauthn/assert/options", body);
      }
      throw err;
    }
  }

  async function approve() {
    if (!request) return;
    setStatus("working");
    setError(null);
    try {
      if (!window.PublicKeyCredential || !navigator.credentials) throw new Error("webauthn unsupported");
      const opts = await assertOptions(request.checkout_id);
      const cred = (await navigator.credentials.get({ publicKey: toRequestOptions(opts) })) as PublicKeyCredential | null;
      if (!cred) throw new Error("no credential");
      const res = await postJson<ApproveResponse>("/payment/approve", {
        shopper_id: SHOPPER_ID,
        checkout_id: request.checkout_id,
        credential: credentialToJson(cred),
      });
      onResolve({
        checkout_id: request.checkout_id,
        approved: true,
        mandate: { checkout_mandate: res.checkout_mandate, payment_mandate: res.payment_mandate },
      });
    } catch (err) {
      const name = (err as DOMException)?.name;
      setStatus("error");
      setError(name === "NotAllowedError" || name === "AbortError" ? "payErrCancelled" : "payErrFailed");
    }
  }

  function decline() {
    if (request) onResolve({ checkout_id: request.checkout_id, approved: false });
  }

  return { status, error, busy: status === "working" || status === "registering", approve, decline };
}
