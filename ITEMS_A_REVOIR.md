# Objets du tableur non ajoutés au simulateur — à revoir par un humain

Synchro de juin 2026 avec l'onglet `items` du tableur
(https://docs.google.com/spreadsheets/d/11HGOAimTwlpzDPj_m5IKssJrhFccuCSQ5K2uTAD3Z4s/).
95 objets manquants ont été ajoutés dans `objets.py`. Les objets ci-dessous ont été
**volontairement laissés de côté** car leur effet repose sur une mécanique que le
simulateur ne modélise pas (ou pas assez fidèlement pour produire des stats utiles).

## Objets supprimés du jeu (barrés dans le tableur, retirés du simulateur en juin 2026)
Faucille communiste, Cerveau auxiliaire, Implant cérébral, Tirelire, Bonne vieille guinze,
Defibrilateur en panne.

## Maj du 12 juin 2026 (couleurs + nouvelle vague de suppressions)
- **Couleurs des objets** : chaque objet porte désormais `couleur` (1=rouge, 2=vert, 3=bleu,
  4=violet, 5=jaune), chargée depuis `item_visuals.json` (régénéré depuis le tableur).
- **Panoplie** : 3 objets de même couleur au début de la partie = +2 PV (bonus d'avant-partie,
  figé, cumulable : 6 objets de la même couleur ou 2 triplettes = +4). Appliqué dans
  `simu.py` / `Joueur.appliquer_panoplies`.
- **Supprimés du tableur (lignes retirées)** : Avis de recherche, Crocs enflamées, Glande
  pinéale, Miroir du Riséd, Oursin dodu, Sceau de Légalisation, Épluche-Donjon.
- **Nouvellement barrés** : Marteau Communiste, Toge du Nécromancien, Bouclier du Berserk,
  Baromètre de Gloire, Cygne Noir (et Miroir Déformant, qui n'était pas simulé).
- **Placeholders retirés du simulateur** (aucune existence dans le tableur) : Item 6PV,
  Item 3PV, Item 3PV 2, Item 2PV, ItemUseless, Potion de Mana (tranché : c'était bien une
  vieille version du Linceul de Résurrection).
- **Renommés vers les noms du tableur** : Item 5PV → Armure en cuir, Item 4PV → Cotte de
  mailles (+ effet « Exécutez les monstres de puissance 0 » ajouté), Casque Plus → Casque à
  cornes, Main de Midas B → Midas de Bronze, Harpe → Harpe Cinglante, Potion d'adrénaline →
  Shot d'adrénaline, Epaulette du Bourrin → Epaulette du Ponceur. Les clés de
  `priorites_objets.json`, `draft_priors.json` et `item_stats_progressive.json` ont été migrées.
- **Nouveaux implémentés** : Bourse garnie (PV+3, +1 PV de victoire), et grâce aux couleurs :
  **Lanterne chromatique** et **Cinq pierres de Nüwa** (retirés de la liste « écartés » ci-dessous).

## Mode soirée — party.py (12 juin 2026)
`party.py` simule des soirées complètes, au plus près de la vraie façon de jouer :
2 à 5 manches (uniforme) + manches de départage jusqu'à un leader strict en Médailles,
draft complet avant chaque manche (picks aux priors de draft.py, ajustés à l'état des
Médailles), vainqueur de manche +1 Médaille, survivant (fuite incluse) → héros N2,
mort → perte d'une Médaille et repioche d'un héros N1 (le héros mort retourne dans le
pool de la soirée). Métrique principale : winrate de soirée par objet/héros.
- **Nouveaux objets implémentés** : Coupe des champions (`medailles_victoire = 2`),
  Parfum de Scandale (`vole_medailles_perdues`, lu par `Joueur.perdre_medaille`),
  Parchemin d'XP et Potion de Jouvence (`Joueur.changer_niveau_perso`, instance de
  héros fraîche : la capacité une-fois-par-partie redevient disponible).
- **Moteur** : les deux sites de perte de Médaille (mort, Rongeur de medaille) passent
  par `Joueur.perdre_medaille` ; le Totem d'immunité ne protège que la perte à la mort,
  le Parfum de Scandale récupère les deux. `joueur.partie_joueurs` est posé par
  l'ordonnanceur.
- **IA médailles** (sans effet à 0 Médaille, donc neutre pour donjon.py/draft.py) :
  seuil de fuite `pv_min_fuite + 2/Médaille`, seuil de risque 0,25 abaissé de
  0,05/Médaille, `_degats_attendus` évalue le Rongeur de medaille au total des
  Médailles en jeu (plus 10 forfaitaire), l'Empaleur d'imprudent à 2 avec Médaille,
  le Saigneur Vampire à +2/Médaille. Constantes en tête de `joueurs.py`.
- **Draft soirée** : objets `bonus_sans_medaille` (les 6 « novice ») décotés quand on
  détient une Médaille ; Totem/Parfum/Coupe bonifiés selon l'état. Constantes en tête
  de `party.py`.

## Mécaniques non simulées → objets écartés

### Information cachée
Le simulateur modélise maintenant la divination via `joueur.cartes_connues` (cartes vues,
exploitées par l'IA de fuite et de repioche) : **Journal du futur, Binocles de l'inventeur,
Fil du destin, Oiseau de Mauvais Augure, Œil d'Horus** sont désormais implémentés,
ainsi que le **Prophète niveau 1** (héros).
- **Bâton des ombres** — cacher sa pile de monstres vaincus : toujours écarté
  (aucun adversaire IA ne lit la pile pour décider).

### Échange / interception en plein combat (la boucle de combat ne permet pas de changer la carte affrontée)
- **Sceptre du Nécromancien** — échanger le monstre combattu avec un monstre de sa pile.
- **Oeil du Changeforme** — piocher une carte de remplacement contre un monstre puissant.
- **Miroir Déformant** — copier l'effet spécial d'un monstre sur le suivant.

### Système de héros (pouvoirs multiples) non modélisé
Les niveaux de héros sont maintenant simulables (cf. section party.py du 12 juin 2026) :
**Parchemin d'XP** et **Potion de Jouvence** sont implémentés. Restent écartés :
- **Potion X** — piocher un héros supplémentaire.
- **Ultime Sceptre** — accéder aux pouvoirs du héros d'un adversaire.
- **Livre de Thot** — défausser son héros et en repiocher un.

### Médailles inter-manches
Résolu le 12 juin 2026 : `party.py` simule des soirées complètes (Médailles portées
entre les manches). **Coupe des champions** et **Parfum de Scandale** sont implémentés.

### Ordre du tour / structure de la boucle de jeu
- **Sablier occulte** — c'est au joueur précédent de jouer (ordre inversé non supporté).
- **Bécane du Ponceur** — "vous rentrez en premier dans le Donjon" (l'ordre des joueurs est fixé par le harnais).
- **Horloge maudite** — payer 1 PV pour passer son tour, répétable (même famille que le
  Hamac reposant / Sac de couchette, déjà désactivés dans `objets.py` à cause du spam de passes).
- **Boite de Schrödinger** — une fois brisée, "si vous passez votre tour, vous mourrez"
  (force un comportement de pioche que l'IA de fuite ne sait pas arbitrer).

### Hooks inexistants dans le moteur
- **Sac à dos scellé** et **Coffre-Fuite** — protection de la pile contre monstres/événements/joueurs :
  il faudrait vérifier un drapeau dans tous les effets qui retirent des cartes (SOULSTORM, Arracheur,
  Fouet du fourbe, Esprit du Donjon, Siège de Troie, Carapace Bleue…). Faisable mais transversal.
- **Masque du Saboteur** — intercepter l'activation d'un objet adverse *avant* son effet.
- **Corne d'Abondance** — déclencheur "un adversaire pioche un objet" inexistant.
- **Nuée de sangsues** — déclencheur "un joueur gagne des PV" inexistant.
- **Œil du Maître** — défausser un événement sans l'appliquer (les événements sont résolus en dur dans `simu.py`).

### Divers
- **Sceptre Changeur** — la description est vide dans le tableur (id 59, `hex.png`).
- **Parchemin divinatoire** — choisir n'importe quelle carte du Donjon au lieu de piocher.

## Déjà présents dans le simulateur sous un autre nom
(Résolu le 12 juin 2026 : tous renommés vers les noms du tableur, cf. section « Maj du 12 juin ».)

## Implémentés avec simplification (à connaître pour interpréter les stats)
- **Pomme d'Adam**, **Compas du Capitaine**, **Clé de Salomon**, **Miroir de Yata** —
  le coup d'œil sur le Donjon alimente désormais `cartes_connues` (vraie valeur d'information).
- **Œil d'Horus** — la restriction "si vous la piochez, vous ne pouvez pas l'exécuter"
  n'est pas appliquée (mineur).
- **Lance de Silence** — seul le cas "monstre à effet spécial (puissance X) devient 0" est simulé,
  pas l'annulation d'événement.
- **Main du Créateur** — survie avec 2 PV simulée ; la défausse d'un thème de Donjon ne l'est pas
  (pas de thèmes dans le simulateur).
- **Toupie du Chaos** — PV+4 seulement : remélanger le Donjon n'a aucun effet mesurable en simulation.
- **Sceptre du Maharal** — exécute le Golem en payant 1 PV ; l'option de le remettre sur le Donjon
  (farming) n'est pas utilisée.
- **Tatouage du Ponceur** — le plafond de 12 PV est appliqué en début/fin de tour et après chaque
  monstre vaincu, pas à l'instant exact de chaque gain.
- **Épée vengeresse** / **Dague vengeresse** — le choix du joueur est figé par l'IA :
  puissance 5 / type Golem (les plus représentés dans le Donjon).
- **Siège de Troie** — "le prochain tour de chaque autre joueur" est approximé par une fenêtre
  d'un tour de table après l'activation.
- **Cinq pierres de Nüwa** — l'IA l'utilise en urgence (dommages ≥ PV) ou dès que les
  5 couleurs sont réunies (pour le bonus +5 et la défausse).

## Petites extensions du moteur faites pour cette synchro
- `joueurs.py` / `Joueur.mort()` : un objet intact avec `protege_medailles = True`
  (Totem d'immunité) empêche la perte de Médaille.
- `joueurs.py` / `Joueur.deciderDeFuir()` : un objet intact avec `bloque_fuite_pv_bas = True`
  (Ceinture du Ponceur) interdit la fuite sous 6 PV ; `malus_pv_decision_fuite = 6` fait
  anticiper la fuite (l'IA évalue ses PV - 6 pour fuir à temps).
- `objets.py` : helpers `_peek_prochaine_carte`, `_defausse_monstre_de_pile`,
  `_choisir_objet_a_sacrifier`, `_execute_carte_suivante`, `_repare_un_objet`.

## Améliorations IA (12 juin 2026, après audit des taux de mort par objet)
Audit 200k parties : plusieurs objets avaient un taux de mort très au-dessus de la
moyenne (~30%) à cause d'une mauvaise utilisation par l'IA. Corrections :
- **Tapis volant** (32,6% → 9,4% de morts) — la carte dit « fuyez à tout moment » : l'IA
  s'envole désormais juste avant un coup fatal (`combat_effet`, pattern Gâteau spatial,
  la carte retourne sur le Donjon) et remplace un jet de fuite mal parti (≤5) par une
  sortie garantie (`en_fuite`). Avant, elle ne fuyait qu'après avoir vaincu un monstre.
- **Sac de Constantinople** (46,6% → 23,9%) — le gain de PV de la carte (« autant de PV
  que de Dragons dans votre pile ») n'était jamais appliqué ; le déclencheur ignore aussi
  les dragons de la défausse ; usage d'urgence en combat ajouté.
- **`Joueur._nb_options_combat`** (systémique) — la décision de fuite comptait *tous* les
  actifs intacts comme des « options », y compris ceux qui ne peuvent pas répondre à un
  coup (Parachute doré, Potion d'escampette, Pelle du Fossoyeur, soins automatiques de
  début de tour…). Leurs porteurs retardaient la fuite et mouraient (~+12 pts de morts).
  Ne comptent plus que les actifs avec un hook de combat ou de survie, hors objets marqués
  `non_combattant = True` (usage trop situationnel : Lance de Silence, Rose d'or, Cloche
  du Déjà-Vu, Sac de Constantinople, Slip de la Résurgence).
- **Slip de la Résurgence** (43,6% → 23,1%) — attendre PV ≤ 4 était contradictoire : les
  autres actifs sont consommés plus vite que les PV. S'utilise désormais tôt (≥3 autres
  actifs intacts) ou en urgence.
- **Rose d'or** (42,1% → 18,2%) — l'IA la gardait pour les +2 PV de victoire même face à
  un coup fatal ; elle la consomme maintenant pour survivre.
- **Cloche du Déjà-Vu** (39,3% → 22,3%) — usage d'urgence ajouté : remet son monstre le
  plus faible (ou un facile de la défausse) sur le Donjon pour les +3 PV qui sauvent.
- Effet global : mortalité moyenne par objet 29,3% → 24,7%, score moyen posé 4,92 → 5,00.
  Les winrates de quelques objets baissent de 1-3 pts (somme nulle : les ex-mourants
  reprennent leur part). `prio.py` est à relancer pour recaler les priorités de draft.

## Améliorations IA (juin 2026)
- **Fuite informée par le risque** : en plus du seuil de PV, l'IA fuit quand ≥25% des cartes
  restantes du Donjon la tueraient (et qu'elle a peu d'objets actifs). Seuil choisi par balayage.
  Effet mesuré (4j, 5 objets/joueur, 6000 parties par bras) : score moyen posé 3,06 → 3,33,
  médian 2 → 3, morts 42% → 32%.
- **Repioche volontaire** (`Joueur.deciderDeRejouer`, branché dans `simu.py`) : l'IA repioche
  quand (1) elle connaît la prochaine carte (divination) et qu'elle est bonne, (2) un objet
  multi-kill (`objectif_multi_kill` : Cœur de Tarasque, Porte-Boules) est à ≤2 monstres de son
  combo, (3) plus aucune carte restante ne fait plus de 2 dégâts. Globalement neutre sur les
  stats, mais rend ces objets fonctionnels.
- **Divination** : `joueur.cartes_connues` mémorise les cartes vues (l'identité de l'objet carte
  valide automatiquement la fraîcheur de l'info). Lue par `deciderDeFuir` et `deciderDeRejouer`.
- `joueur.doit_passer` est désormais respecté pour bloquer les repioches volontaires.
- `simu.py` pose `joueur.compte_au_score` au décompte (utilisé par la colonne « Score médian »
  de `donjon.py`).
