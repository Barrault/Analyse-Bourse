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
    # Même chemin que le bouton de la fenêtre : lecture de la page, hôte natif, stockage de session
    worker.evaluate("(tabId) => analyze(tabId)", tab_id)
    state = worker.evaluate("async () => (await chrome.storage.session.get('state')).state")
    assert state["status"] == "done" and state["result"]["ok"], state["result"].get("error")
    assert state["result"]["account_type"] == "PEA" and state["result"]["plan"]["cash_start"] == 1234.56

    popup = browser_context.new_page()
    errors = []
    popup.on("pageerror", lambda error: errors.append(error))
    popup.goto(f"{worker.url.rsplit('/', 1)[0]}/popup.html")
    try:
        # Statut non vérifié : ouverte dans un onglet chrome-extension://, la fenêtre signale
        # qu'on n'est pas sur Bourse Direct, mais affiche le dernier plan calculé
        popup.locator("h2", has_text=f"PEA — {FIXTURE_ACCOUNT}").wait_for(timeout=10_000)
    finally:
        # Espaces insécables (séparateur de milliers fr-FR) → espaces ordinaires
        text = popup.inner_text("body").replace(" ", " ").replace(" ", " ")
        assert not errors, (errors, text)
    assert "1. Ventes" in text and "2. Achats" in text and "Disponible au comptant : 1 234,56" in text
    assert "BNP PARIBAS ACT.A" in text                     # vendue ou conservée selon le signal du jour
    assert "APPLE INC" in text and "hors univers" in text  # marché étranger : décision manuelle
    assert popup.locator("#analyze").is_enabled()
