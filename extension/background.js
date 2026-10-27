// Service worker : lit la page Bourse Direct à la demande et interroge l'hôte Python (DEC-28).
// Lecture seule : aucun clic, aucune saisie, aucun ordre. Seul interlocuteur : l'hôte natif local.
const HOST = "fr.analyse_boursiere.rebalance";

// Icône active seulement sur Bourse Direct
chrome.runtime.onInstalled.addListener(() => {
  if (!chrome.declarativeContent) return;
  chrome.action.disable();
  chrome.declarativeContent.onPageChanged.removeRules(undefined, () => {
    chrome.declarativeContent.onPageChanged.addRules([{
      conditions: [new chrome.declarativeContent.PageStateMatcher({ pageUrl: { hostSuffix: "boursedirect.fr" } })],
      actions: [new chrome.declarativeContent.ShowAction()],
    }]);
  });
});

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

async function analyze(tabId) {
  await chrome.storage.session.set({ state: { status: "running", at: Date.now() } });
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
  // Stockage de session : effacé à la fermeture du navigateur, inaccessible aux pages web
  await chrome.storage.session.set({ state: { status: "done", at: Date.now(), result } });
}

chrome.runtime.onMessage.addListener((message, sender) => {
  if (sender.id === chrome.runtime.id && message.type === "analyze") analyze(message.tabId);
});
