export type Lang = "hi" | "en";

/** Pick the Hindi or English string for the selected UI language (Hindi is the default). */
export function tr(lang: Lang | string | null | undefined, hi: string, en: string): string {
  return lang === "en" ? en : hi;
}
