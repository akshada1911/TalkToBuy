import { useEffect, useRef, useState } from "react";
import type { PaymentRequestedDetail, PaymentResult } from "@talktobuy/assistant-widget";
import { HttpError, credentialToJson, postJson, toRequestOptions } from "./webauthn";
import { needsRegistration, registerCredential } from "./register";

interface Props {
  request: PaymentRequestedDetail;
  shopperId: string;
  onResolve: (result: PaymentResult) => void;
}

interface ApproveResponse {
  checkout_mandate: string;
  payment_mandate: string;
  expires_at?: string | number;
}

type Status = "ready" | "working" | "registering" | "error";

const rupees = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

/**
 * The shop's OWN payment step (trusted surface, Constitution III): payment is approved only here,
 * with the fingerprint, never by voice. Flow: assert/options → navigator.credentials.get() →
 * /payment/approve → widget.resolvePayment({approved:true, mandate}).
 */
export function PaymentStep({ request, shopperId, onResolve }: Props) {
  const [status, setStatus] = useState<Status>("ready");
  const [message, setMessage] = useState<{ hi: string; en: string } | null>(null);
  const primary = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    primary.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") cancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function cancel() {
    onResolve({ checkout_id: request.checkout_id, approved: false });
  }

  async function assertOptions(): Promise<Record<string, unknown>> {
    const body = { shopper_id: shopperId, checkout_id: request.checkout_id };
    try {
      return await postJson<Record<string, unknown>>("/payment/webauthn/assert/options", body);
    } catch (err) {
      if (err instanceof HttpError && needsRegistration(err.status)) {
        setStatus("registering");
        await registerCredential(shopperId);
        setStatus("working");
        return await postJson<Record<string, unknown>>("/payment/webauthn/assert/options", body);
      }
      throw err;
    }
  }

  async function approve() {
    setStatus("working");
    setMessage(null);
    try {
      if (!window.PublicKeyCredential || !navigator.credentials) throw new Error("webauthn unsupported");
      const opts = await assertOptions();
      const cred = (await navigator.credentials.get({ publicKey: toRequestOptions(opts) })) as PublicKeyCredential | null;
      if (!cred) throw new Error("no credential");
      const res = await postJson<ApproveResponse>("/payment/approve", {
        shopper_id: shopperId,
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
      if (name === "NotAllowedError" || name === "AbortError") {
        setMessage({ hi: "फ़िंगरप्रिंट नहीं हुआ। फिर से कोशिश करें, या रद्द करें।", en: "Fingerprint not completed. Try again or cancel." });
      } else {
        setMessage({ hi: "भुगतान अभी नहीं हो पाया। फिर से कोशिश करें।", en: "Payment could not be approved. Please try again." });
      }
    }
  }

  const busy = status === "working" || status === "registering";
  return (
    <div className="modal-backdrop">
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="pay-title" aria-describedby="pay-summary">
        <div className="modal-head">
          <h2 id="pay-title">भुगतान / Payment</h2>
          <span className="test-badge">टेस्ट मोड / Test mode</span>
        </div>
        <dl id="pay-summary" className="pay-summary">
          <dt>सामान / Items</dt>
          <dd>{request.item_count}</dd>
          <dt>कुल / Total</dt>
          <dd className="pay-total">{rupees(request.total)}</dd>
          <dt>डिलीवरी / Delivery</dt>
          <dd>
            <span lang="hi">{request.delivery.label_hi}</span>
            <span className="pay-en" lang="en">
              {request.delivery.label_en}
            </span>
          </dd>
        </dl>
        <p className="pay-note">
          यह दुकान की अपनी भुगतान स्क्रीन है। मंज़ूरी सिर्फ़ आपके फ़िंगरप्रिंट से होगी। कोई OTP या PIN नहीं माँगा जाएगा।
          <span className="pay-en" lang="en">
            This is the shop's own payment screen. Approval is by your fingerprint only; no OTP or PIN is ever asked.
          </span>
        </p>
        {message && (
          <p className="pay-error" role="alert">
            {message.hi} <span className="pay-en" lang="en">{message.en}</span>
          </p>
        )}
        <div className="modal-actions">
          <button ref={primary} type="button" className="btn-primary btn-fingerprint" onClick={() => void approve()} disabled={busy}>
            <span className="fp-icon" aria-hidden="true">
              ☝️
            </span>
            <span>
              {status === "registering"
                ? "फ़िंगरप्रिंट जोड़ रहे हैं… / Setting up fingerprint…"
                : busy
                  ? "रुकिए… / Please wait…"
                  : `फ़िंगरप्रिंट से ${rupees(request.total)} दें / Pay with fingerprint`}
            </span>
          </button>
          <button type="button" className="btn-secondary" onClick={cancel} disabled={busy}>
            रद्द करें / Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
