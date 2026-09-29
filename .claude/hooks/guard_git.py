"""Hook PreToolUse (Bash) : garde-fous git du projet (voir CLAUDE.md, « Workflow git »).

1. Bloque `git add -A`, `git add --all` et `git add .` : l'utilisateur modifie parfois des
   fichiers en parallèle, qui ne doivent pas être embarqués dans un commit.
2. Avant tout `git commit`, lance la suite pytest (hors réseau, ~1 s) et bloque si elle échoue.

Code de sortie 2 = commande bloquée ; le message sur stderr est renvoyé à Claude.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
ADD_ALL = re.compile(r"\bgit\s+add\s+(?:[^;&|]*\s)?(?:-A|--all|\.)(?=\s|$|[;&|])")
COMMIT = re.compile(r"\bgit\s+commit\b")


def main() -> int:
    sys.stderr.reconfigure(encoding="utf-8")
    command = json.load(sys.stdin).get("tool_input", {}).get("command", "")

    if ADD_ALL.search(command):
        print("Bloqué : n'indexe pas tout le dépôt (git add -A / --all / .). "
              "Ajoute les fichiers un par un : `git add chemin1 chemin2`.", file=sys.stderr)
        return 2

    if COMMIT.search(command):
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                                cwd=PROJECT_DIR, capture_output=True, text=True, encoding="utf-8",
                                errors="replace")
        if result.returncode != 0:
            tail = "\n".join((result.stdout + result.stderr).strip().splitlines()[-15:])
            print(f"Bloqué : la suite de tests échoue, commit refusé.\n{tail}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
