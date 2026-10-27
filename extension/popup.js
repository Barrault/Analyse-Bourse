// Affichage du plan renvoyé par l'hôte Python (DEC-28). Tout passe par textContent : un nom
// de titre venant de la page ne peut pas injecter de HTML.
const button = document.getElementById("analyze");
const statusLine = document.getElementById("status");
const planBox = document.getElementById("plan");
const accountsBar = document.getElementById("accounts");
let tabId = null;
let displayed = null;  // compte affiché sur la page Bourse Direct (null : inconnu)
let selected = null;   // compte dont le plan est montré
let store = {};        // { plans, running, lastError } du stockage de session
const STALE_MS = 5 * 60 * 1000;  // une analyse « en cours » plus ancienne a été interrompue

const eur = (x) => x.toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
const pct = (x) => `${x >= 0 ? "+" : ""}${x.toFixed(1).replace(".", ",")} %`;

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

// headers : [libellé, colonne numérique ?] ; rowClass(i) : classe CSS de la ligne i
function section(title, className, headers, rows, empty, rowClass = () => "") {
  const box = el("section", undefined, className);
  box.append(el("h2", title));
  if (!rows.length) { box.append(el("p", empty, "muted")); return box; }
  const table = el("table");
  const head = el("tr");
  headers.forEach(([label, num]) => head.append(el("th", label, num ? "num" : "")));
  table.append(head);
  rows.forEach((cells, r) => {
    const tr = el("tr", undefined, rowClass(r));
    cells.forEach((cell, i) => tr.append(el("td", String(cell), headers[i][1] ? "num" : "")));
    table.append(tr);
  });
  box.append(table);
  return box;
}

function renderPlan(result) {
  const p = result.plan;
  if (result.warning) planBox.append(el("p", result.warning, "warning"));
  planBox.append(el("h2", `${result.account_type} — ${result.account}`));
  planBox.append(el("p", `Disponible au comptant : ${eur(p.cash_start)}`, "muted"));
  planBox.append(section("1. Ventes (à passer en premier)", "sells",
    [["Titre"], ["Qté", 1], ["Cours", 1], ["+/- vs PRU", 1], ["Motif"], ["Produit estimé", 1]],
    p.sells.map((s) => [s.name, s.quantity, eur(s.price), pct(s.pnl_pct), s.reason, eur(s.proceeds)]),
    "Aucune vente."));
  // Tous les signaux ACHAT par priorité : d'abord ceux que le solde finance (le plan de la
  // stratégie), puis les autres, chiffrés au montant standard (DEC-32)
  const allBuys = [...p.buys, ...p.skipped_buys];
  planBox.append(section("2. Achats (tous les signaux ACHAT, par priorité)", "buys",
    [["#", 1], ["Titre"], ["Qté", 1], ["Cours", 1], ["Montant frais inclus", 1], ["Confiance", 1], ["Financé"]],
    allBuys.map((b, i) => [i + 1, `${b.name} (${b.ticker})`, b.quantity, eur(b.price), eur(b.cost),
                           `${(b.confidence * 100).toFixed(1).replace(".", ",")} %`,
                           i < p.buys.length ? "oui" : `non : ${b.reason}`]),
    "Aucun signal ACHAT.", (i) => (i < p.buys.length ? "" : "beyond")));
  if (p.skipped_buys.length) {
    const funded = p.buys.reduce((sum, b) => sum + b.cost, 0);
    const beyond = p.skipped_buys.reduce((sum, b) => sum + b.cost, 0);
    planBox.append(el("p", `Financés par le solde : ${eur(funded)}. Tout acheter demanderait ${eur(beyond)} ` +
      `de plus (${p.skipped_buys.length} ligne${p.skipped_buys.length > 1 ? "s" : ""}). Le backtest n'achète que les ` +
      "lignes financées, dans cet ordre.", "muted"));
  }
  planBox.append(section("3. Positions conservées", "", [["Titre"], ["Signal"], ["+/- vs PRU", 1]],
    p.keeps.map((k) => [k.name, k.recommendation, pct(k.pnl_pct)]), "Aucune."));
  if (p.manual.length) {
    planBox.append(section("4. Hors stratégie (décision manuelle)", "", [["Titre"], ["Motif"], ["+/- vs PRU", 1]],
      p.manual.map((m) => [m.name, m.reason, pct(m.pnl_pct)]), ""));
  }
  planBox.append(el("p", `Trésorerie : ${eur(p.cash_start)} → après ventes ${eur(p.cash_after_sells)} → ` +
    `après achats ${eur(p.cash_end)}. Montants estimés sur le dernier cours ; exécution au cours d'ouverture.`, "muted"));
}

const hhmm = (at) => {
  const d = new Date(at);
  const time = d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  return d.toDateString() === new Date().toDateString() ? time : `${d.toLocaleDateString("fr-FR")} ${time}`;
};

// Par défaut : le compte affiché sur la page s'il a un plan, sinon le plan le plus récent
function defaultSelection() {
  const plans = store.plans || {};
  if (displayed) return plans[displayed] ? displayed : null;
  const latest = Object.entries(plans).sort((a, b) => b[1].at - a[1].at)[0];
  return latest ? latest[0] : null;
}

function render() {
  const plans = store.plans || {};
  const running = store.running && Date.now() - store.running.at < STALE_MS;
  button.disabled = running || tabId === null;

  accountsBar.replaceChildren();
  Object.entries(plans).sort((a, b) => a[1].result.account_type.localeCompare(b[1].result.account_type))
    .forEach(([account, { at, result }]) => {
      const tab = el("button", `${result.account_type} · ${hhmm(at)}`, account === selected ? "selected" : "");
      tab.title = account + (account === displayed ? " (affiché sur la page)" : "");
      tab.addEventListener("click", () => { selected = account; render(); });
      accountsBar.append(tab);
    });

  planBox.replaceChildren();
  const latestPlan = Math.max(0, ...Object.values(plans).map((x) => x.at));
  if (store.lastError && store.lastError.at > latestPlan) {
    planBox.append(el("p", `Dernière analyse en échec (${hhmm(store.lastError.at)}) : ${store.lastError.error}`, "error"));
  }
  if (running) {
    const which = store.running.account ? ` du compte ${store.running.account}` : "";
    statusLine.textContent = `Analyse${which} en cours depuis ${hhmm(store.running.at)}… (≈ 1 min 30 sans cache)`;
  } else if (store.running) {
    statusLine.textContent = `Analyse lancée à ${hhmm(store.running.at)} interrompue : relancer.`;
  } else if (displayed && !plans[displayed]) {
    statusLine.textContent = `Le compte affiché (${displayed}) n'a pas encore été analysé.`;
  } else if (!selected) {
    statusLine.textContent = "Ouvrez la page de vos positions, puis lancez l'analyse.";
  } else {
    statusLine.textContent = selected === displayed ? "Plan du compte affiché sur la page."
      : displayed ? "Attention : ce plan n'est pas celui du compte affiché sur la page." : "";
  }
  if (selected && plans[selected]) {
    planBox.append(el("p", `Calculé à ${hhmm(plans[selected].at)} ; relancer l'analyse pour l'actualiser.`, "muted"));
    renderPlan(plans[selected].result);
  }
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "session") return;
  for (const [key, { newValue }] of Object.entries(changes)) store[key] = newValue;
  // Fin d'une analyse : montrer le compte qui vient d'être calculé
  if (changes.plans?.newValue) {
    const latest = Object.entries(changes.plans.newValue).sort((a, b) => b[1].at - a[1].at)[0];
    selected = latest[0];
  }
  render();
});

button.addEventListener("click", () => {
  button.disabled = true;
  statusLine.textContent = "Lecture de la page…";
  chrome.runtime.sendMessage({ type: "analyze", tabId })
    .catch((error) => { statusLine.textContent = `Erreur : ${error.message}`; button.disabled = false; });
});

chrome.tabs.query({ active: true, currentWindow: true }, async ([tab]) => {
  // Le bouton ne dépend pas de l'URL (Opera ne la donne pas toujours) : hors de Bourse Direct,
  // la lecture de la page échoue avec un message explicite.
  tabId = tab?.id ?? null;
  store = await chrome.storage.session.get(["plans", "running", "lastError"]);
  if (tabId !== null) displayed = await chrome.runtime.sendMessage({ type: "displayed-account", tabId });
  selected = defaultSelection();
  render();
  if (tab?.url && !new URL(tab.url).hostname.endsWith("boursedirect.fr")) {
    statusLine.textContent = "Cette extension ne fonctionne que sur boursedirect.fr.";
  }
});
