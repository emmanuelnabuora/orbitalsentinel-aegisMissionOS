/** Active tenant workspace: persisted slug, sent as X-Workspace on API calls. */

const KEY = "aegis.workspace";

export function activeWorkspace(): string | null {
  return sessionStorage.getItem(KEY);
}

export function setActiveWorkspace(slug: string | null) {
  if (slug) sessionStorage.setItem(KEY, slug);
  else sessionStorage.removeItem(KEY);
  window.dispatchEvent(new Event("aegis:workspace"));
}
