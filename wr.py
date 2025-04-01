import json

# Nom du fichier contenant les données JSON
json_filename = 'item_stats_progressive.json'

try:
    # Ouvrir et charger le fichier JSON
    with open(json_filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Données chargées avec succès depuis '{json_filename}'.")

except FileNotFoundError:
    print(f"Erreur : Le fichier '{json_filename}' est introuvable.")
    exit()
except json.JSONDecodeError:
    print(f"Erreur : Le contenu de '{json_filename}' n'est pas un JSON valide.")
    exit()
except Exception as e:
    print(f"Une erreur inattendue est survenue lors de la lecture du fichier : {e}")
    exit()

# Vérifier que la clé 'item_stats' existe et contient bien un dictionnaire
if 'item_stats' not in data or not isinstance(data['item_stats'], dict):
    print(f"Erreur: La clé 'item_stats' est manquante ou n'est pas un dictionnaire dans le fichier '{json_filename}'.")
    exit()

# Accéder directement au dictionnaire des statistiques d'items
items_dictionary = data['item_stats']

# Optionnel : récupérer le nombre total de drafts
drafts_completed = data.get('drafts_completed')
if drafts_completed is not None:
     print(f"Nombre total de drafts complétés trouvé : {drafts_completed}")

# --- Modification pour le tri et le formatage en tableau ---
# Liste pour stocker les données de chaque item pour le tri/tableau
table_data_list = []

# Itérer sur le dictionnaire des items pour calculer et collecter les données
for item_name, item_data in items_dictionary.items():
    if not isinstance(item_data, dict):
        print(f"Avertissement : L'entrée pour '{item_name}' n'est pas un dictionnaire valide, elle sera ignorée.")
        continue

    played = item_data.get('played', 0)
    win = item_data.get('win', 0)
    death = item_data.get('death', 0)
    fled = item_data.get('fled', 0)
    cleared = item_data.get('cleared', 0)
    pick = item_data.get('pick', 0)
    draft = item_data.get('draft', 0)

    # Calculer les taux
    win_rate = (win / played * 100) if played > 0 else 0
    death_rate = (death / played * 100) if played > 0 else 0
    fled_rate = (fled / played * 100) if played > 0 else 0 # 'fled_rate' pour 'fuiterate'
    cleared_rate = (cleared / played * 100) if played > 0 else 0 # 'cleared_rate' pour 'completion rate'
    # Utiliser le ratio pick/draft comme "pickrate" pour le tableau, car un vrai pickrate global n'est pas calculable facilement ici.
    pick_rate = (pick / draft * 100) if draft > 0 else 0

    # Ajouter les données nécessaires pour le tableau à la liste
    table_data_list.append({
        "nom": item_name,
        "winrate": win_rate,
        "pickrate": pick_rate, # Note: Ratio Pick/Draft
        "deathrate": death_rate,
        "fuiterate": fled_rate,
        "completion_rate": cleared_rate,
        "nb_parties": played # Nombre total de parties
    })

# Trier la liste par 'winrate' en ordre décroissant
# La fonction lambda spécifie que la clé de tri est la valeur associée à 'winrate' dans chaque dictionnaire
table_data_list.sort(key=lambda item: item['winrate'], reverse=True)

# --- Formatage et Affichage du Tableau ---
if not table_data_list:
    print("\nAucune donnée d'item à afficher dans le tableau.")
else:
    print("\n--- Tableau des Statistiques (Trié par Taux de Victoire Décroissant) ---")

    # Définir les en-têtes de colonnes demandés
    # Clés utilisées dans les dictionnaires de table_data_list
    col_keys = ["nom", "winrate", "pickrate", "deathrate", "fuiterate", "completion_rate", "nb_parties"]
    # Noms d'affichage pour les en-têtes
    headers = {
        "nom": "Nom Item",
        "winrate": "Winrate (%)",
        "pickrate": "Pick/Draft (%)", # On précise que c'est le ratio pick/draft
        "deathrate": "Deathrate (%)",
        "fuiterate": "Fuirate (%)",
        "completion_rate": "Complétion (%)",
        "nb_parties": "Nb Parties"
    }

    # Calculer la largeur maximale pour chaque colonne pour un affichage propre
    col_widths = {key: len(headers[key]) for key in col_keys}
    for item in table_data_list:
        for key in col_keys:
            # Formatter les nombres pour le calcul de largeur (ex: '99.99' ou '12345')
            if isinstance(item[key], float):
                value_str = f"{item[key]:.2f}" # Format avec 2 décimales
            else:
                value_str = str(item[key])
            # Mettre à jour la largeur max si la valeur actuelle est plus longue
            col_widths[key] = max(col_widths[key], len(value_str))

    # Créer la chaîne de format pour l'en-tête (Nom à gauche, autres à droite)
    header_format_parts = [f"{{:<{col_widths['nom']}}}"] # Nom à gauche
    for key in col_keys[1:]: # Autres colonnes à droite
        header_format_parts.append(f"{{:>{col_widths[key]}}}")
    header_format_string = " | ".join(header_format_parts)

    # Créer la chaîne de format pour les lignes de données
    row_format_parts = [f"{{item_nom:<{col_widths['nom']}}}"] # Nom à gauche
    # Pour les taux (float), spécifier .2f pour 2 décimales et > pour alignement à droite
    row_format_parts.append(f"{{item_win:>{col_widths['winrate']}.2f}}")
    row_format_parts.append(f"{{item_pick:>{col_widths['pickrate']}.2f}}")
    row_format_parts.append(f"{{item_death:>{col_widths['deathrate']}.2f}}")
    row_format_parts.append(f"{{item_fui:>{col_widths['fuiterate']}.2f}}")
    row_format_parts.append(f"{{item_comp:>{col_widths['completion_rate']}.2f}}")
    # Pour le nombre de parties (int), juste > pour alignement à droite
    row_format_parts.append(f"{{item_nb:>{col_widths['nb_parties']}}}")
    row_format_string = " | ".join(row_format_parts)

    # Imprimer l'en-tête
    print(header_format_string.format(*[headers[key] for key in col_keys]))

    # Imprimer la ligne de séparation
    separator = "-+-".join("-" * col_widths[key] for key in col_keys)
    print(separator)

    # Imprimer chaque ligne de données formatée
    for item in table_data_list:
        print(row_format_string.format(
            item_nom=item["nom"],
            item_win=item["winrate"],
            item_pick=item["pickrate"],
            item_death=item["deathrate"],
            item_fui=item["fuiterate"],
            item_comp=item["completion_rate"],
            item_nb=item["nb_parties"]
        ))

# Optionnel : Sauvegarder les résultats triés (table_data_list) dans un nouveau fichier JSON
# output_filename = 'item_calculated_stats_sorted.json'
# try:
#     with open(output_filename, 'w', encoding='utf-8') as outfile:
#         # Sauvegarder la liste triée
#         json.dump(table_data_list, outfile, indent=4, ensure_ascii=False)
#     print(f"\nStatistiques calculées et triées sauvegardées dans '{output_filename}'.")
# except Exception as e:
#     print(f"Erreur lors de la sauvegarde des résultats triés : {e}")