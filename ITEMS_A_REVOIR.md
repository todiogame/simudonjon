# Objets du tableur non ajoutés au simulateur — à revoir par un humain

Synchro de juin 2026 avec l'onglet `items` du tableur
(https://docs.google.com/spreadsheets/d/11HGOAimTwlpzDPj_m5IKssJrhFccuCSQ5K2uTAD3Z4s/).
95 objets manquants ont été ajoutés dans `objets.py`. Les objets ci-dessous ont été
**volontairement laissés de côté** car leur effet repose sur une mécanique que le
simulateur ne modélise pas (ou pas assez fidèlement pour produire des stats utiles).

## Objets supprimés du jeu (barrés dans le tableur, retirés du simulateur en juin 2026)
Faucille communiste, Cerveau auxiliaire, Implant cérébral, Tirelire, Bonne vieille guinze,
Defibrilateur en panne.

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

### Système de héros (niveaux, pouvoirs multiples) non modélisé
- **Potion X** — piocher un héros supplémentaire.
- **Ultime Sceptre** — accéder aux pouvoirs du héros d'un adversaire.
- **Potion de Jouvence** — repasser héros niveau 1.
- **Parchemin d'XP** — passer héros niveau 2.
- **Livre de Thot** — défausser son héros et en repiocher un.

### Couleurs des objets non modélisées
- **Lanterne chromatique** — exécute selon le nombre de couleurs dans ses objets.
- **Cinq pierres de Nüwa** — gagne des PV selon ses couleurs d'objets.

### Médailles inter-manches (le simulateur ne joue qu'une manche)
- **Coupe des champions** — gagner 2 Médailles au lieu d'une en cas de victoire.
- **Parfum de Scandale** — récupérer les Médailles perdues par les adversaires.

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

## Déjà présents dans le simulateur sous un autre nom (pas de doublon créé)
- **Casque à cornes** → implémenté sous le nom `Casque Plus`.
- **Midas de Bronze** → implémenté sous le nom `Main de Midas B`.
- À noter : le simulateur contient aussi `Potion de Mana` (survie à 1 PV si pile non vide)
  qui n'existe pas dans le tableur — peut-être une ancienne version du *Linceul de Résurrection*
  (désormais implémenté fidèlement). À trancher.

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
- **Oursin dodu** — PV+4 seulement : l'IA n'exploite pas la perte volontaire de PV (combos
  Shot d'adrénaline / Masque de l'Inquisiteur).
- **Toge du Nécromancien** — PV+2 seulement : l'IA n'utilise jamais la remise volontaire de son
  dernier monstre sur le Donjon (presque toujours perdant).
- **Sceptre du Maharal** — exécute le Golem en payant 1 PV ; l'option de le remettre sur le Donjon
  (farming) n'est pas utilisée.
- **Tatouage du Ponceur** — le plafond de 12 PV est appliqué en début/fin de tour et après chaque
  monstre vaincu, pas à l'instant exact de chaque gain.
- **Épée vengeresse** / **Dague vengeresse** — le choix du joueur est figé par l'IA :
  puissance 5 / type Golem (les plus représentés dans le Donjon).
- **Siège de Troie** — "le prochain tour de chaque autre joueur" est approximé par une fenêtre
  d'un tour de table après l'activation.
- **Épluche-Donjon** — la défausse de la carte du dessus se fait à l'aveugle quand les PV sont
  critiques (≤4), comme en vrai (pas de triche d'information).

## Petites extensions du moteur faites pour cette synchro
- `joueurs.py` / `Joueur.mort()` : un objet intact avec `protege_medailles = True`
  (Totem d'immunité) empêche la perte de Médaille.
- `joueurs.py` / `Joueur.deciderDeFuir()` : un objet intact avec `bloque_fuite_pv_bas = True`
  (Ceinture du Ponceur) interdit la fuite sous 6 PV ; `malus_pv_decision_fuite = 6` fait
  anticiper la fuite (l'IA évalue ses PV - 6 pour fuir à temps).
- `objets.py` : helpers `_peek_prochaine_carte`, `_defausse_monstre_de_pile`,
  `_choisir_objet_a_sacrifier`, `_execute_carte_suivante`, `_repare_un_objet`.

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
