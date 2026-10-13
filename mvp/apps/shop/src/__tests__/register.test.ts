import { describe, expect, it } from "vitest";
import { needsRegistration } from "../payment/register";

describe("needsRegistration", () => {
  it("is true for 404 and 409", () => {
    expect(needsRegistration(404)).toBe(true);
    expect(needsRegistration(409)).toBe(true);
  });

  it("is true for the store's 400 NOT_REGISTERED", () => {
    const body = { ucp: { status: "error" }, messages: [{ type: "error", code: "NOT_REGISTERED", content: "shopper has no registered authenticator" }] };
    expect(needsRegistration(400, body)).toBe(true);
  });

  it("is false for other failures", () => {
    expect(needsRegistration(400, { messages: [{ code: "INVALID_REQUEST" }] })).toBe(false);
    expect(needsRegistration(400)).toBe(false);
    expect(needsRegistration(500, null)).toBe(false);
  });
});
