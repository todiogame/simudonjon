import json
import os
from collections import defaultdict

# fonction pour fusionner les resultats de chaque simulation de draft
# Lancer plusieurs draft.py dans differents terminaux pour gagner du temps
# puis lancer ce script pour fusionner les resultats


def merge_dicts(dest, src):
    for key, value in src.items():
        if isinstance(value, dict):
            if key not in dest:
                dest[key] = {}
            merge_dicts(dest[key], value)
        else:
            dest[key] = dest.get(key, 0) + value

# Initialisation des structures
total_data = {
    "drafts_completed": 0,
    "item_stats": defaultdict(lambda: defaultdict(int)),
    "perso_stats": defaultdict(lambda: defaultdict(int))
}

# Lecture de tous les fichiers correspondants
for filename in os.listdir():
    if filename.startswith("item_stats_progressive_") and filename.endswith(".json"):
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            total_data["drafts_completed"] += data.get("drafts_completed", 0)
            merge_dicts(total_data["item_stats"], data.get("item_stats", {}))
            merge_dicts(total_data["perso_stats"], data.get("perso_stats", {}))

# Conversion des defaultdicts en dicts simples
def recursive_defaultdict_to_dict(d):
    if isinstance(d, defaultdict):
        d = {k: recursive_defaultdict_to_dict(v) for k, v in d.items()}
    return d

item_stats = recursive_defaultdict_to_dict(total_data["item_stats"])
perso_stats = recursive_defaultdict_to_dict(total_data["perso_stats"])
drafts_total = total_data["drafts_completed"]

# --- Calcul et Affichage final ---
print("\nCalcul stats finales...")
final_stats_items = []
total_picks_overall = sum(stats.get('pick', 0) for stats in item_stats.values())

for nom, stats in item_stats.items():
    played = stats.get('played', 0)
    drafts = stats.get('draft', 1); picks = stats.get('pick', 0)
    wins = stats.get('win', 0); deaths = stats.get('death', 0)
    fled = stats.get('fled', 0); cleared = stats.get('cleared', 0)
    pickrate = (picks / drafts * 100) if drafts > 0 else 0
    popularity = (picks / total_picks_overall * 100) if total_picks_overall > 0 else 0
    winrate = (wins / played * 100) if played > 0 else 0
    death_rate = (deaths / played * 100) if played > 0 else 0
    fled_rate = (fled / played * 100) if played > 0 else 0
    cleared_rate = (cleared / played * 100) if played > 0 else 0
    final_stats_items.append({
        'Objet': nom, 'Picks': picks, 'Played': played, 'Pick%': pickrate, 'Pop%': popularity,
        'Win%': winrate, 'Death%': death_rate, 'Fled%': fled_rate, 'Clear%': cleared_rate
    })

sorted_items = sorted(final_stats_items, key=lambda x: x['Win%'], reverse=True)
print("\n--- Statistiques Objets ---")
print("-" * 120)
print(f"{'Objet':<35} {'Picks':<10} {'Played':<10} {'Pick%':<8} {'Pop%':<8} {'Win%':<8} {'Death%':<8} {'Fled%':<8} {'Clear%':<8}")
print("-" * 120)
for s in sorted_items:
    print(f"{s['Objet']:<35} {s['Picks']:<10} {s['Played']:<10} {s['Pick%']:<8.0f} {s['Pop%']:<8.1f} {s['Win%']:<8.2f} {s['Death%']:<8.2f} {s['Fled%']:<8.2f} {s['Clear%']:<8.2f}")
print("-" * 120)

final_stats_persos = []
for nom, stats in perso_stats.items():
    played = stats.get('played', 0)
    wins = stats.get('win', 0); deaths = stats.get('death', 0)
    fled = stats.get('fled', 0); cleared = stats.get('cleared', 0)
    winrate = (wins / played * 100) if played > 0 else 0
    death_rate = (deaths / played * 100) if played > 0 else 0
    fled_rate = (fled / played * 100) if played > 0 else 0
    cleared_rate = (cleared / played * 100) if played > 0 else 0
    final_stats_persos.append({
        'Personnage': nom, 'Played': played, 'Win%': winrate,
        'Death%': death_rate, 'Fled%': fled_rate, 'Clear%': cleared_rate
    })

sorted_persos = sorted(final_stats_persos, key=lambda x: x['Win%'], reverse=True)
print("\n--- Statistiques Personnages ---")
print("-" * 70)
print(f"{'Personnage':<20} {'Played':<10} {'Win%':<8} {'Death%':<8} {'Fled%':<8} {'Clear%':<8}")
print("-" * 70)
for s in sorted_persos:
    print(f"{s['Personnage']:<20} {s['Played']:<10} {s['Win%']:<8.2f} {s['Death%']:<8.2f} {s['Fled%']:<8.2f} {s['Clear%']:<8.2f}")
print("-" * 70)

print(f"\nStats finales basées sur {drafts_total} drafts complétés.")
print("Données sauvegardées dans item_stats_totals.json")

with open("item_stats_totals.json", "w", encoding="utf-8") as f:
    json.dump({
        "drafts_completed": drafts_total,
        "item_stats": item_stats,
        "perso_stats": perso_stats
    }, f, indent=2, ensure_ascii=False)
