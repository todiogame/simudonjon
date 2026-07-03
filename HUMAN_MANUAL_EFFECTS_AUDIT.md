# Audit effets humains auto

Objectif: tout effet optionnel d'objet ou de personnage qui concerne l'humain doit etre propose en action cliquable, pas execute automatiquement ni via prompt oui/non. Les effets a malus explicitement obligatoires restent automatiques: Arc enflamme, Arc du Neant, Casque Berserk, Sceau de Legalisation, Seringue du docteur fou.

## Methode de detection

- Source analysee: classes de `objets.py` et `heros.py` qui redefinissent un hook moteur (`debut_tour`, `fin_tour`, `combat_effet`, `combat_effet_late`, `survie_effet`, `vaincu_effet`, `rencontre_effet`, `rencontre_event_effet`, `subit_dommages_effet`, `activated_effet`, `fuite_definitive_effet`, `en_fuite`, `en_roll`).
- Flux moteur inspecte: appels directs dans `simu.py` et chemins de decision dans `joueurs.py`.
- Etat actuel important: les objets de `combat_effet` passent deja majoritairement par `choose_combat_source` pour l'humain. Les hooks hors combat restent le gros chantier.

## Exceptions obligatoires conservees

Ces effets sont a malus ou contraintes et doivent rester forces quand leur condition est vraie:

- `ArcEnflamme` (`combat_effet`)
- `ArcDuNeant` (`vaincu_effet`)
- `CasqueBerserk` (`subit_dommages_effet`)
- `SceauDeLegalisation` (`fin_tour`)
- `SeringueDuDocteurFou` (`combat_effet`, `rencontre_effet`, `rencontre_event_effet`)

## Corrige dans cette passe

- Personnages avec `combat_effet` normal: `ChevalierDragon`, `DocteurDePeste`, `InventeurGenial`, `Flutiste`.
  - Avant: `ordonnanceur` appelait `joueur.perso_obj.en_combat(...)` automatiquement pour l'humain. La base `Perso.condition()` pouvait ouvrir un prompt oui/non `combat_source`.
  - Maintenant: ces personnages sont ajoutes aux sources de combat cliquables via `choose_combat_source`, comme les objets. L'IA conserve l'appel automatique.
- `AnneauDeVie` (`fin_tour`).
  - Avant: l'humain gagnait automatiquement 1 PV en passant son tour.
  - Maintenant: l'objet est expose comme action cliquable pendant la decision principale du tour, avec `itemId` pour cliquer directement la carte. L'effet est utilisable une fois par tour humain et reste automatique pour l'IA.
- Objets simples de tour: `ChapeletDeVitalite`, `CoquillageMagique`, `GrimoireInconnu`, `RouletteInfernale`, `MasqueDeLInquisiteur`, `CoeurDeTarasque`.
  - Avant: les hooks `debut_tour` / `fin_tour` se resolvaient automatiquement pour l'humain.
  - Maintenant: ils sont proposes comme actions cliquables pendant la decision principale si leurs conditions sont reunies. Les hooks automatiques sont conserves pour l'IA.
- Deuxieme lot d'objets simples de tour: `BoiteDePandore`, `Chameau`, `ShotDAdrenaline`, `CanneAChep`, `FromagePuant`, `ParcheminDXP`, `ClocheDuDejaVu`, `SlipDeLaResurgence`, `PotionAuTheVert`, `EplucheDonjon`, `JournalDuFutur`, `PorteBoulesDuPonceur`.
  - Avant: ces effets se resolvaient automatiquement au debut ou en fin de tour humain.
  - Maintenant: ils sont exposes comme actions cliquables pendant la decision principale quand leur condition est vraie. `PotionAuTheVert` conserve son effet special de passage de tour apres clic.
- Troisieme lot d'objets de debut/fin de tour: `GantsDeGaia`, `EnclumeInstable`, `CorneDAbordage`, `EspritDuDonjon`, `SacDeConstantinople`, `Imprimante`, `BouleDeCristal`, `PierreDePressentiment`, `EventailMaudit`, `PelleDuFossoyeur`, `TaserManuel`, `CoursierVolant`, `DisqueDeVishnu`.
  - Avant: ces hooks pouvaient se resoudre automatiquement pour l'humain au debut/fin du tour, ou ouvrir une decision interne sans action de carte prealable.
  - Maintenant: ils passent par le registre `manual_turn_hook` et apparaissent comme actions cliquables dans la decision principale. Les sous-choix utiles restent disponibles apres clic (ex: objet a copier/voler, puissance annoncee).

## Hooks objets encore a migrer

### Debut de tour

`BottesDeVitesse`, `TatouageDuPonceur`, `MainInvisible`, `GlandePineale`, `FilDuDestin`.

### Fin de tour

`TatouageDuPonceur`, `ConcoctionInstable`, `SceauDeLegalisation` (obligatoire), `OiseauDeMauvaisAugure`.

### Apres victoire / vaincu

`ParcheminDeTeleportation`, `PotionFeerique`, `BottesDeVitesse`, `CraneDuRoiLiche`, `BoiteAButin`, `CasqueACornes`, `CoeurDeDragon`, `PierreDuNaga`, `GriffesEclair`, `TatouageDuPonceur`, `ArcDuNeant` (obligatoire), `UrneEnsorcelee`, `PierreDePressentiment`, `SiegeDeTroie`, `CleDeSalomon`, `EpeeDeDamocles`, `CouteauQuiTombe`, `OeilDHorus`.

### Rencontre monstre / evenement

`BouclierDragon`, `SeringueDuDocteurFou` (obligatoire), `PotionDeFeuLiquide`, `CodexDiabolus`, `ScotchDuSilencieux`, `PlanPresqueParfait`, `GrelotDuBouffon`, `PierreDePressentiment`.

### Subit dommages

`CaliceDuRoiSorcier`, `PerceuseABreche`, `CasqueBerserk` (obligatoire), `TrousseDeSecours`, `KitDeSoin`, `BinoclesDeLInventeur`.

### Survie

`Egide`, `PotionFeerique`, `PotionDraconique`, `CoquilleSalvatrice`, `AnkhDeReincarnation`, `ConcentreDeFun`, `LinceulDeResurrection`, `AnneauDuNovice`, `MainDuCreateur`, `PoigneeDeMain`, `Paratonnerre`.

Note: les objets de survie sont deja exposes comme sources de combat quand le monstre est lethal. Le vieux chemin post-degats existe encore pour certains cas et doit rester audite.

### Fuite / fuite definitive / roll

- Fuite: `PatinsAGlace`, `GetasDuNovice`, `TapisVolant`, `PotionDEscampette`, `ParachuteDore`, `CrocsEnflamees`, `BottesDePoncage`.
- Fuite definitive: `CorneDAbordage`, `PelleDuFossoyeur`, `SacDeConstantinople`.
- Roll: `FerACheval`, `DeDuTricheur`, `ElixirDeChance`, `TatouageMaudit`, `MasqueMaudit`, `ChevalierePirate`.

### Activated

`CoffreAnime`, `SceptreActif`, `LunettesDuBricoleur`, `ForgePortative`, `TrouNoirPortatif`.

## Hooks personnages encore a migrer

- Debut de tour: `Princesse`, `Tricheur`, `SavantFou`, `Prophete`, `LapinBlanc`, `Ponceur`, `BeteDeLEvenement`.
- Rencontre: `Flutiste` (son effet de boost adverse reste auto a auditer).
- Subit dommages: `RoiSorcier`.
- Survie: `Berserker`.
- Vaincu: `SavantFou`.
- Fuite / roll / fin de tour: `Ninja`, `DocteurDePeste`, `Shaman`, `Ponceur`.
- Combat late: `Avatar` etait deja cliquable via `choose_combat_source`.

## Prochaine etape technique

Le registre d'actions humaines existe maintenant pour les hooks `debut_tour` / `fin_tour` via `manual_turn_hook`. Prochaine extension:

- etendre le meme modele aux phases post-combat (`vaincu`, `rencontre`, `subit_dommages`, `fuite`, `roll`, `activated`) sans executer les effets optionnels a la collecte;
- separer les effets vraiment passifs/obligatoires des options humaines dans les listes restantes (`BottesDeVitesse`, `TatouageDuPonceur`, `MainInvisible`, `GlandePineale`, `ConcoctionInstable`);
- garder les exceptions obligatoires dans le chemin auto.
