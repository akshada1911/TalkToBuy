export type Lang = "hi" | "en";

/** Pick the Hindi or English string for the selected UI language. */
export const tr = (lang: Lang, hi: string, en: string): string => (lang === "en" ? en : hi);
