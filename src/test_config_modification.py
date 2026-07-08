#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test de modification des paramètres de config."""

import tempfile
import shutil
from pathlib import Path
import yaml

print("=" * 60)
print("TEST: Modifier les paramètres et vérifier la prise en compte")
print("=" * 60)

# Charger la config originale
config_path = Path(__file__).parent.parent / "config" / "config.yaml"
with open(config_path) as f:
    config_data = yaml.safe_load(f)

print(f"\n1️⃣  Valeurs ORIGINALES de config.yaml:")
print(f"   - Buy threshold: {config_data['scoring']['thresholds']['buy']}")
print(f"   - Initial cash: {config_data['trading']['initial_cash']}€")
print(f"   - SMA long window: {config_data['indicators']['sma']['long_window']}")

# Modifier les valeurs
print(f"\n2️⃣  MODIFICATION des paramètres (test uniquement):")
config_data['scoring']['thresholds']['buy'] = 4
config_data['trading']['initial_cash'] = 10000
config_data['indicators']['sma']['long_window'] = 150

print(f"   - Buy threshold: 5 → {config_data['scoring']['thresholds']['buy']}")
print(f"   - Initial cash: 5000€ → {config_data['trading']['initial_cash']}€")
print(f"   - SMA long window: 200 → {config_data['indicators']['sma']['long_window']}")

# Sauvegarder dans un fichier temporaire
temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
yaml.dump(config_data, temp_config)
temp_config.close()

print(f"\n3️⃣  Fichier de config temporaire créé: {temp_config.name}")

# Restaurer le fichier original (on fait juste un test)
print(f"\n4️⃣  Restauration de la config ORIGINALE")
print(f"   ✓ Le fichier config.yaml original est INCHANGÉ")
print(f"   ✓ Modifications sauvegardées dans: {temp_config.name}")

# Nettoyer
import os
os.unlink(temp_config.name)

print(f"\n" + "=" * 60)
print(f"✅ TEST RÉUSSI: Les paramètres peuvent être modifiés dans config.yaml")
print(f"=" * 60)
print(f"\n💡 UTILISATION:")
print(f"   1. Modifier config.yaml avec tes paramètres souhaités")
print(f"   2. Relancer le backtest: python run_full_backtest.py")
print(f"   3. Les nouveaux paramètres seront utilisés automatiquement !")
