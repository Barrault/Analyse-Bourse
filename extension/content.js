// Script de contenu (DEC-30) : sur « Mes portefeuilles », signale au service worker le compte
// affiché, une fois la page chargée puis à chaque changement de compte. Lecture seule : il
// observe la page, ne clique sur rien et n'envoie rien d'autre que le n° de compte.
const POLL_MS = 2000;
let reported = null;
let previous = null;

setInterval(() => {
  if (!document.getElementById("portfolio-react")) return;  // autre page du site
  const account = displayedAccountInPage();
  // Deux relevés identiques de suite : le compte affiché a fini de se charger
  if (account && account === previous && account !== reported) {
    reported = account;
    chrome.runtime.sendMessage({ type: "page-account", account }).catch(() => {});
  }
  previous = account;
}, POLL_MS);
