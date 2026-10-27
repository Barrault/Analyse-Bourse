// Service worker : lit la page Bourse Direct à la demande et interroge l'hôte Python (DEC-28).
// Lecture seule : aucun clic, aucune saisie, aucun ordre. Seul interlocuteur : l'hôte natif local.
const HOST = "fr.analyse_boursiere.rebalance";

// Une première version désactivait l'icône hors de Bourse Direct (declarativeContent), ce
// qu'Opera n'applique pas : état et règles persistent, on les annule.
chrome.action.enable();
chrome.runtime.onInstalled.addListener(() => chrome.declarativeContent?.onPageChanged.removeRules());

// Un port ouvert garde le service worker en vie pendant l'analyse (≈ 1 min sans cache)
function askHost(message) {
  return new Promise((resolve) => {
    const port = chrome.runtime.connectNative(HOST);
    port.onMessage.addListener((response) => { resolve(response); port.disconnect(); });
    port.onDisconnect.addListener(() => resolve({
      ok: false,
      error: chrome.runtime.lastError?.message || "l'hôte natif s'est arrêté sans répondre",
    }));
    port.postMessage(message);
  });
}

// Exécutée dans la page. Même règle que bourse_direct_page.displayed_account (DEC-29) : la
// carte dont le nombre d'actifs égale le nombre de lignes affichées, sinon aucune.
function displayedAccountInPage() {
  const rows = document.querySelectorAll(".position-row").length;
  const cards = [...document.querySelectorAll("[data-testid]")].filter((c) => /^card-\d+$/.test(c.dataset.testid));
  const matching = cards.filter((c) => Number((c.textContent.match(/(\d+)\s*actif/) || [])[1]) === rows);
  return matching.length === 1 ? matching[0].dataset.id : null;
}

// Sert seulement à choisir quel plan mémorisé montrer ; le plan lui-même vient de Python
async function displayedAccount(tabId) {
  try {
    const frames = await chrome.scripting.executeScript({ target: { tabId, allFrames: true }, func: displayedAccountInPage });
    return frames.map((f) => f.result).find(Boolean) ?? null;
  } catch {
    return null;  // onglet hors Bourse Direct
  }
}

// Stockage de session (effacé à la fermeture du navigateur, inaccessible aux pages web) :
//   plans     { <n° de compte>: { at, result } }  dernier plan de chaque compte
//   running   { at } pendant une analyse
//   lastError { at, error } si la dernière analyse a échoué
async function analyze(tabId) {
  await chrome.storage.session.set({ running: { at: Date.now() } });
  let result;
  try {
    const frames = await chrome.scripting.executeScript({
      target: { tabId, allFrames: true },
      func: () => document.documentElement.outerHTML,
    });
    result = await askHost({ type: "plan", frames: frames.map((f) => f.result).filter(Boolean) });
  } catch (error) {
    result = { ok: false, error: String(error) };
  }
  const at = Date.now();
  if (result.ok) {
    const { plans = {} } = await chrome.storage.session.get("plans");
    plans[result.account] = { at, result };
    await chrome.storage.session.set({ plans, running: null, lastError: null });
  } else {
    await chrome.storage.session.set({ running: null, lastError: { at, error: result.error } });
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) return;
  if (message.type === "analyze") analyze(message.tabId);
  if (message.type === "displayed-account") {
    displayedAccount(message.tabId).then(sendResponse);
    return true;  // réponse asynchrone
  }
});
