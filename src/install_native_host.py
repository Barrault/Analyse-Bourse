"""
Déclare l'hôte Native Messaging auprès du navigateur (Windows, utilisateur courant, DEC-28).

    python src/install_native_host.py --extension-id <identifiant affiché dans opera://extensions>
    python src/install_native_host.py --uninstall

Écrit native_host/ (lanceur .bat et manifeste, chemins absolus de cette machine, non
versionné) et la clé de registre qui pointe vers le manifeste. À relancer si le projet ou le
venv est déplacé.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOST_NAME = "fr.analyse_boursiere.rebalance"
# Opera (Chromium) lit les hôtes natifs déclarés pour Chrome
REGISTRY_KEY = rf"Software\Google\Chrome\NativeMessagingHosts\{HOST_NAME}"
HOST_DIR = PROJECT_ROOT / "native_host"
EXTENSION_ID = re.compile(r"^[a-p]{32}$")


def host_files(python: Path, extension_id: str, root: Path = PROJECT_ROOT) -> Dict[Path, str]:
    """Contenu du lanceur et du manifeste. Seule l'extension `extension_id` peut lancer l'hôte."""
    if not EXTENSION_ID.match(extension_id):
        raise ValueError(f"identifiant d'extension invalide : {extension_id!r} (32 lettres a à p)")
    host_dir = root / "native_host"
    launcher = host_dir / "rebalance_host.bat"
    manifest = {"name": HOST_NAME, "description": "Plan de rebalance (Analyse boursière)",
                "path": str(launcher), "type": "stdio",
                "allowed_origins": [f"chrome-extension://{extension_id}/"]}
    return {launcher: f'@echo off\r\n"{python}" "{root / "src" / "native_host.py"}" %*\r\n',
            host_dir / f"{HOST_NAME}.json": json.dumps(manifest, indent=2)}


def main() -> None:
    import winreg
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--extension-id")
    group.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()

    if args.uninstall:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY)
        except FileNotFoundError:
            pass
        for path in HOST_DIR.glob("*"):
            path.unlink()
        print("Hôte natif désinstallé.")
        return

    files = host_files(Path(sys.executable), args.extension_id)
    HOST_DIR.mkdir(exist_ok=True)
    for path, content in files.items():
        path.write_text(content, encoding="utf-8", newline="")
    manifest = next(p for p in files if p.suffix == ".json")
    winreg.SetValue(winreg.HKEY_CURRENT_USER, REGISTRY_KEY, winreg.REG_SZ, str(manifest))
    print(f"Hôte natif installé : {manifest}\nRedémarrer Opera, puis tester le bouton de l'extension.")


if __name__ == "__main__":
    main()
