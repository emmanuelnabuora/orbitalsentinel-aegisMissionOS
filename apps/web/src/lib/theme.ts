/** Theme persistence: dark is the brand default; light is opt-in. */

const KEY = "aegis.theme";
export type Theme = "dark" | "light";

export function currentTheme(): Theme {
  return (localStorage.getItem(KEY) as Theme) || "dark";
}

export function applyTheme(t: Theme) {
  if (t === "light") document.documentElement.dataset.theme = "light";
  else delete document.documentElement.dataset.theme;
  localStorage.setItem(KEY, t);
}

export function initTheme() {
  applyTheme(currentTheme());
}
