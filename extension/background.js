// Service worker : lit la page Bourse Direct et interroge l'hôte Python (DEC-28), au clic ou
// automatiquement sur « Mes portefeuilles » (DEC-30). Lecture seule : aucun clic, aucune
// saisie, aucun ordre. Seul interlocuteur : l'hôte natif local.
importScripts("page_account.js");  // displayedAccountInPage, marketPhase

const HOST = "fr.analyse_boursiere.rebalance";
let busy = null;          // compte en cours d'analyse ("" si inconnu) ; en mémoire : pas de course
const queue = new Map();  // compte signalé pendant une analyse → copie de la page prise à ce moment

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
//   running   { at, account } pendant une analyse (account : compte attendu, si connu)
//   lastError { at, error } si la dernière analyse a échoué
async function readPage(tabId) {
  const frames = await chrome.scripting.executeScript({
    target: { tabId, allFrames: true },
    func: () => document.documentElement.outerHTML,
  });
  return frames.map((f) => f.result).filter(Boolean);
}

// frames : copie de la page déjà prise (compte en file d'attente), sinon lue maintenant
async function analyze(tabId, account = null, frames = null) {
  if (busy !== null) return;  // une seule analyse à la fois (le bouton est grisé pendant ce temps)
  busy = account ?? "";
  await chrome.storage.session.set({ running: { at: Date.now(), account } });
  let result;
  try {
    result = await askHost({ type: "plan", frames: frames ?? await readPage(tabId) });
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
  busy = null;
  await drainQueue();
}

async function drainQueue() {
  if (busy !== null || queue.size === 0) return;
  const [account, frames] = queue.entries().next().value;
  queue.delete(account);
  await analyze(null, account, frames);
}

// Compte signalé par la page : analyse s'il n'a pas encore de plan pour la période en cours.
// Pendant une autre analyse, la page est copiée tout de suite : quand viendra son tour,
// l'utilisateur aura pu afficher un autre compte.
async function autoAnalyze(tabId, account) {
  const { plans = {} } = await chrome.storage.session.get("plans");
  if (plans[account] && marketPhase(plans[account].at) === marketPhase(Date.now())) return;
  if (busy === account) return;
  if (busy === null) return analyze(tabId, account);
  try {
    queue.set(account, await readPage(tabId));
  } catch {
    return;  // onglet fermé entre-temps
  }
  await drainQueue();  // l'analyse en cours a pu se terminer pendant la copie
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) return;
  if (message.type === "analyze") analyze(message.tabId);
  if (message.type === "page-account" && sender.tab) autoAnalyze(sender.tab.id, message.account);
  if (message.type === "displayed-account") {
    displayedAccount(message.tabId).then(sendResponse);
    return true;  // réponse asynchrone
  }
});
