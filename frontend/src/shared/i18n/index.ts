// English first; add a JSON file per language with the same keys.
import en from "./en.json";

const dictionaries: Record<string, Record<string, string>> = { en };
let lang = "en";

export function setLanguage(l: string): void {
  if (dictionaries[l]) lang = l;
}

export function t(key: keyof typeof en | string): string {
  return dictionaries[lang]?.[key] ?? (en as Record<string, string>)[key] ?? key;
}
