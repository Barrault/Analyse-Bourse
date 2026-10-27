// Affichage du plan renvoyé par l'hôte Python (DEC-28). Tout passe par textContent : un nom
// de titre venant de la page ne peut pas injecter de HTML.
const button = document.getElementById("analyze");
const statusLine = document.getElementById("status");
const planBox = document.getElementById("plan");
let tabId = null;

const eur = (x) => x.toLocaleString("fr-FR", { style: "currency", currency: "EUR" });
const pct = (x) => `${x >= 0 ? "+" : ""}${x.toFixed(1).replace(".", ",")} %`;

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

// headers : [libellé, colonne numérique ?]
function section(title, className, headers, rows, empty) {
  const box = el("section", undefined, className);
  box.append(el("h2", title));
  if (!rows.length) { box.append(el("p", empty, "muted")); return box; }
  const table = el("table");
  const head = el("tr");
  headers.forEach(([label, num]) => head.append(el("th", label, num ? "num" : "")));
  table.append(head);
  rows.forEach((cells) => {
    const tr = el("tr");
    cells.forEach((cell, i) => tr.append(el("td", String(cell), headers[i][1] ? "num" : "")));
    table.append(tr);
  });
  box.append(table);
  return box;
}

function renderPlan(result) {
  planBox.replaceChildren();
  if (!result.ok) { planBox.append(el("p", `Erreur : ${result.error}`, "error")); return; }
  const p = result.plan;
  if (result.warning) planBox.append(el("p", result.warning, "warning"));
  planBox.append(el("h2", `${result.account_type} — ${result.account}`));
  planBox.append(el("p", `Disponible au comptant : ${eur(p.cash_start)}`, "muted"));
  planBox.append(section("1. Ventes (à passer en premier)", "sells",
    [["Titre"], ["Qté", 1], ["Cours", 1], ["+/- vs PRU", 1], ["Motif"], ["Produit estimé", 1]],
    p.sells.map((s) => [s.name, s.quantity, eur(s.price), pct(s.pnl_pct), s.reason, eur(s.proceeds)]),
    "Aucune vente."));
  planBox.append(section("2. Achats (par ordre de priorité)", "buys",
    [["#", 1], ["Titre"], ["Qté", 1], ["Cours", 1], ["Montant frais inclus", 1], ["Confiance", 1]],
    p.buys.map((b, i) => [i + 1, `${b.name} (${b.ticker})`, b.quantity, eur(b.price), eur(b.cost),
                          `${(b.confidence * 100).toFixed(1).replace(".", ",")} %`]),
    "Aucun achat."));
  if (p.skipped_buys.length) {
    planBox.append(el("p", "ACHAT non servis : " + p.skipped_buys.map((b) => `${b.name} (${b.reason})`).join(", "), "muted"));
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

function show(state) {
  if (!state) { statusLine.textContent = "Ouvrez la page de vos positions, puis lancez l'analyse."; return; }
  const when = new Date(state.at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  if (state.status === "running") {
    button.disabled = true;
    statusLine.textContent = `Analyse en cours depuis ${when}… (≈ 1 min la première fois de la journée)`;
    return;
  }
  button.disabled = tabId === null;
  statusLine.textContent = `Plan calculé à ${when}.`;
  renderPlan(state.result);
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "session" && changes.state) show(changes.state.newValue);
});

button.addEventListener("click", () => chrome.runtime.sendMessage({ type: "analyze", tabId }));

chrome.tabs.query({ active: true, currentWindow: true }, async ([tab]) => {
  // Sans permission « tabs », l'URL n'est visible que sur les sites autorisés (Bourse Direct)
  tabId = tab?.url && new URL(tab.url).hostname.endsWith("boursedirect.fr") ? tab.id : null;
  const { state } = await chrome.storage.session.get("state");
  show(state);
  if (tabId === null) statusLine.textContent = "Cette extension ne fonctionne que sur boursedirect.fr.";
});
