/** Register a custom element once (safe under HMR and when two copies of the widget load). */
export function define(name: string, ctor: CustomElementConstructor): void {
  if (typeof customElements !== "undefined" && !customElements.get(name)) customElements.define(name, ctor);
}
