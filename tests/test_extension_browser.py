"""Extension de bout en bout dans Chromium (DEC-28) : manuel, `pytest -m browser` (≈ 2 min).

La copie anonymisée de la page est servie à la place de www.boursedirect.fr : aucune requête
ne part vers le site. Le navigateur lance le vrai hôte natif, qui calcule les signaux du
jour sur Yahoo. Prérequis : `playwright install chromium` et l'hôte installé
(`src/install_native_host.py`, même identifiant d'extension qu'Opera, car même dossier).
"""
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parent.parent
EXTENSION = ROOT / "extension"
PAGE = (Path(__file__).parent / "fixtures" / "bourse_direct_positions.html").read_text(encoding="utf-8")
PAGE_URL = "https://www.boursedirect.fr/fr/mon-compte/portefeuilles"
FIXTURE_ACCOUNT = "508TI00000000001EUR"
OTHER_ACCOUNT = "508TI00000000002EUR"
# Attend le plan d'un compte dans le stockage de session (analyse ≈ 1 min 30 sans cache)
WAIT_FOR_RUNNING = """() => new Promise((resolve) => {
    const check = async () => {
        const { running } = await chrome.storage.session.get('running');
        running ? resolve(running) : setTimeout(check, 200);
    };
    check();
})"""
# Simule un changement de compte : nombre d'actifs annoncé par chaque carte (PEA, CTO)
SHOW_ACCOUNTS = """(counts) => document.querySelectorAll('[data-id]').forEach((card, i) => {
    card.querySelector('[class*=assetNb]').textContent = `${counts[i]} actifs`;
})"""
WAIT_FOR_PLAN = """(account) => new Promise((resolve, reject) => {
    const started = Date.now();
    const check = async () => {
        const { plans = {}, lastError } = await chrome.storage.session.get(['plans', 'lastError']);
        if (plans[account]) return resolve(plans);
        if (lastError) return reject(new Error(lastError.error));
        if (Date.now() - started > 300000) return reject(new Error('pas de plan après 5 min'));
        setTimeout(check, 1000);
    };
    check();
})"""


def serve_fixture(route):
    if route.request.url == PAGE_URL:
        route.fulfill(status=200, content_type="text/html; charset=utf-8", body=PAGE)
    elif route.request.url.startswith("chrome-extension://"):
        route.continue_()  # fichiers de l'extension (popup.js…)
    else:
        route.abort()  # logos, publicités… : rien ne sort


@pytest.fixture
def browser_context():
    with playwright.sync_playwright() as p, tempfile.TemporaryDirectory() as profile:
        context = p.chromium.launch_persistent_context(
            profile, channel="chromium", headless=True,
            args=[f"--disable-extensions-except={EXTENSION}", f"--load-extension={EXTENSION}"])
        context.route("**/*", serve_fixture)
        yield context
        context.close()
    # Journal écrit par l'hôte pour le compte fictif de la copie
    (ROOT / "journal" / f"{datetime.now():%Y-%m-%d}_{FIXTURE_ACCOUNT}.md").unlink(missing_ok=True)


def test_plan_is_computed_from_the_page_and_displayed(browser_context):
    worker = browser_context.service_workers[0] if browser_context.service_workers \
        else browser_context.wait_for_event("serviceworker")
    assert worker.evaluate("() => new Promise((r) => { const port = chrome.runtime.connectNative(HOST); "
                           "port.onMessage.addListener(r); port.postMessage({type: 'ping'}); })") == {"ok": True}, \
        "hôte natif non installé : python src/install_native_host.py --extension-id <id>"

    page = browser_context.new_page()
    page.goto(PAGE_URL)
    tab_id = worker.evaluate("async (url) => (await chrome.tabs.query({url}))[0].id", PAGE_URL)
    assert worker.evaluate("(tabId) => displayedAccount(tabId)", tab_id) == FIXTURE_ACCOUNT  # règle de DEC-29
    # Aucun clic : l'arrivée sur la page lance l'analyse du compte affiché (DEC-30)
    worker.evaluate(WAIT_FOR_RUNNING)
    # Pendant l'analyse du PEA, l'utilisateur passe au CTO puis revient au PEA : la page du
    # CTO est copiée dès son affichage, et son plan calculé ensuite (DEC-31)
    page.evaluate(SHOW_ACCOUNTS, [1, 5])  # PEA « 1 actif », CTO « 5 actifs » = 5 lignes
    page.wait_for_timeout(5_000)          # deux relevés du script de contenu
    page.evaluate(SHOW_ACCOUNTS, [5, 7])  # retour au PEA
    plans = worker.evaluate(WAIT_FOR_PLAN, OTHER_ACCOUNT)
    store = worker.evaluate("() => chrome.storage.session.get(['plans', 'running', 'lastError'])")
    assert not store.get("lastError"), store["lastError"]
    result, other = plans[FIXTURE_ACCOUNT]["result"], plans[OTHER_ACCOUNT]["result"]
    assert result["account_type"] == "PEA" and result["plan"]["cash_start"] == 1234.56
    assert other["account_type"] == "CTO"
    # Signaux du PEA réutilisés en séance : le CTO ne retélécharge pas les cours
    assert plans[OTHER_ACCOUNT]["at"] - plans[FIXTURE_ACCOUNT]["at"] < 30_000

    # Nouvelle visite dans la même période : pas de nouvelle analyse
    page.reload()
    page.wait_for_timeout(6_000)  # trois relevés du script de contenu
    store = worker.evaluate("() => chrome.storage.session.get(['plans', 'running'])")
    assert not store.get("running") and store["plans"][FIXTURE_ACCOUNT]["at"] == plans[FIXTURE_ACCOUNT]["at"]

    popup = browser_context.new_page()
    errors = []
    popup.on("pageerror", lambda error: errors.append(error))
    popup.goto(f"{worker.url.rsplit('/', 1)[0]}/popup.html")

    def shown(heading: str) -> str:
        try:
            popup.locator("h2", has_text=heading).wait_for(timeout=10_000)
        finally:
            # Espaces insécables (séparateur de milliers fr-FR) → espaces ordinaires
            text = popup.inner_text("body").replace(" ", " ").replace(" ", " ")
            assert not errors, (errors, text)
        return text

    # Ouverte dans un onglet chrome-extension://, la fenêtre ne voit pas de compte affiché :
    # elle montre le plan le plus récent, et un onglet par compte analysé
    text = shown(f"CTO — {OTHER_ACCOUNT}")
    assert popup.locator("#accounts button").count() == 2
    popup.locator("#accounts button", has_text="PEA").click()
    text = shown(f"PEA — {FIXTURE_ACCOUNT}")
    assert "1. Ventes" in text and "2. Achats" in text and "Disponible au comptant : 1 234,56" in text
    assert "BNP PARIBAS ACT.A" in text                     # vendue ou conservée selon le signal du jour
    assert "APPLE INC" in text and "hors univers" in text  # marché étranger : décision manuelle
    assert popup.locator("#analyze").is_enabled()


@pytest.mark.parametrize("paris_time, phase", [
    ("2026-10-27T08:59:00+01:00", "2026-10-27 avant-ouverture"),
    ("2026-10-27T09:00:00+01:00", "2026-10-27 seance"),
    ("2026-10-27T17:39:00+01:00", "2026-10-27 seance"),
    ("2026-10-27T17:40:00+01:00", "2026-10-27 apres-cloture"),
    ("2026-10-31T12:00:00+01:00", "2026-10-31 apres-cloture"),  # samedi
    ("2026-07-01T07:30:00Z", "2026-07-01 seance"),               # 9 h 30 à Paris (heure d'été)
])
def test_one_automatic_analysis_per_market_phase(browser_context, paris_time, phase):
    worker = browser_context.service_workers[0] if browser_context.service_workers         else browser_context.wait_for_event("serviceworker")
    assert worker.evaluate("(t) => marketPhase(Date.parse(t))", paris_time) == phase
