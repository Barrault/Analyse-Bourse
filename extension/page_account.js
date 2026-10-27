// Partagé par le script de contenu et le service worker (importScripts).

// Compte affiché sur « Mes portefeuilles » : même règle que bourse_direct_page.displayed_account
// (DEC-29). La carte dont le nombre d'actifs égale le nombre de lignes affichées, sinon aucune.
// Exécutée dans la page.
function displayedAccountInPage() {
  const rows = document.querySelectorAll(".position-row").length;
  const cards = [...document.querySelectorAll("[data-testid]")].filter((c) => /^card-\d+$/.test(c.dataset.testid));
  const matching = cards.filter((c) => Number((c.textContent.match(/(\d+)\s*actif/) || [])[1]) === rows);
  return matching.length === 1 ? matching[0].dataset.id : null;
}

// Période de marché (heure de Paris), comme rebalance.signals_cache_path : avant l'ouverture
// (9 h), en séance (jusqu'à 17 h 40, jours ouvrés), après la clôture. Une analyse automatique
// par compte et par période (DEC-30).
function marketPhase(timestamp) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", weekday: "short", hourCycle: "h23",
  }).formatToParts(new Date(timestamp)).map((p) => [p.type, p.value]));
  const minutes = Number(parts.hour) * 60 + Number(parts.minute);
  const weekday = !["Sat", "Sun"].includes(parts.weekday);
  const phase = minutes < 9 * 60 ? "avant-ouverture"
    : weekday && minutes < 17 * 60 + 40 ? "seance" : "apres-cloture";
  return `${parts.year}-${parts.month}-${parts.day} ${phase}`;
}
