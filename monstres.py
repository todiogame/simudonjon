import numpy as np

class CarteMonstre:
    def __init__(self, titre, puissance, types=None, description="", effet=None):
        self.titre = titre
        self.puissance = puissance
        self.types = types if types else [titre]
        self.description = description
        self.effet = effet
        self.executed = False
        self.dommages = 0

class CarteEvent:
    def __init__(self, titre, description, effet=None):
        self.titre = titre
        self.description = description
        self.effet = effet
        self.event = True

class DonjonDeck:
    def __init__(self):
        self.cartes = [
            CarteMonstre("Gobelin", 1, ["Gobelin"]),
            CarteMonstre("Gobelin", 1, ["Gobelin"]),
            CarteMonstre("Gobelin", 1, ["Gobelin"]),
            CarteMonstre("Gobelin", 1, ["Gobelin"]),
            CarteMonstre("Squelette", 2, ["Squelette"]),
            CarteMonstre("Squelette", 2, ["Squelette"]),
            CarteMonstre("Squelette", 2, ["Squelette"]),
            CarteMonstre("Squelette", 2, ["Squelette"]),
            CarteMonstre("Orc", 3, ["Orc"]),
            CarteMonstre("Orc", 3, ["Orc"]),
            CarteMonstre("Orc", 3, ["Orc"]),
            CarteMonstre("Orc", 3, ["Orc"]),
            CarteMonstre("Vampire", 4, ["Vampire"]),
            CarteMonstre("Vampire", 4, ["Vampire"]),
            CarteMonstre("Vampire", 4, ["Vampire"]),
            CarteMonstre("Vampire", 4, ["Vampire"]),
            CarteMonstre("Golem", 5, ["Golem"]),
            CarteMonstre("Golem", 5, ["Golem"]),
            CarteMonstre("Golem", 5, ["Golem"]),
            CarteMonstre("Golem", 5, ["Golem"]),
            CarteMonstre("Liche", 6, ["Liche"]),
            CarteMonstre("Liche", 6, ["Liche"]),
            CarteMonstre("Démon", 7, ["Démon"]),
            CarteMonstre("Démon", 7, ["Démon"]),
            CarteMonstre("Dragon", 9, ["Dragon"]),
            CarteMonstre("Dragon", 9, ["Dragon"]),
            CarteMonstre("Fée", 0, []),
            CarteMonstre("Chevaucheur de rat", 1, ["Gobelin", "Rat"], "Inflige <b>2 dommages</b> supplémentaires.", "ADD_2_DOM"),
            CarteMonstre("Bon gros rat", 0, ["Rat"], "Inflige <b>2 dommages</b> supplémentaires.", "ADD_2_DOM"),
            CarteMonstre("L'Arracheur", 3, ["Orc"], "Si l'Arracheur vous inflige des dommages, remettez la carte du dessus de votre pile de monstres vaincus <b>sur le Donjon</b>.", "ARRA"),
            CarteMonstre("Dragon endormi", 0, ["Dragon"], "Lancez un dé pour determiner sa puissance.\nSur <b>3 ou moins</b>, ce monstre est <b>puissance 9</b>.\nSur <b>4 ou plus</b>, ce monstre est <b>puissance 0</b>.", "SLEEPING"),
            CarteMonstre("Limon glouton", 0, [], "Si vous affrontez ce monstre, <b>brisez</b> un de vos objets intact.", "LIMON"),
            CarteMonstre("Mimique", 0, [], "La <b>puissance</b> de ce monstre est égale au nombre d'objets que vous possédez quand vous la rencontrez.", "MIMIC"),
            CarteMonstre("Miroir Malefique (P)", 0, [], "Copie le monstre au sommet de votre pile de monstres vaincus.", "MIROIR"),
            CarteMonstre("Rongeur de medaille", 0, ["Rat"], "La <b>puissance</b> de ce monstre est égale au <b>nombre de Médailles</b> dans la partie. Si il vous inflige des dommages, perdez une Médaille.", "MEDAIL"),
            CarteMonstre("Rat Liche", 6, ["Rat","Liche"]),
            CarteMonstre("Golem d'or", 5, ["Golem"], "Vaut <b>2 Points de Victoire</b>\nau lieu d'un.", "GOLD"),
            CarteMonstre("Empaleur d'imprudent", 7, ["Squelette", "Démon"], "Si vous avez une <b>Médaille</b>, ce monstre est de <b>puissance 2</b>.", "NOOB"),
            CarteMonstre("Rat charognard", 0, ["Rat"], "La <b>puissance</b> de ce monstre est égale au nombre de monstres dans votre pile de monstres vaincus.", "SCAVENGER"),
            CarteMonstre("Seigneur Vampire", 4, ["Vampire"], "Si vous avez une <b>Médaille</b>,\ninflige <b>4 dommages</b> supplémentaires.",  "LORD"),
            CarteMonstre("Gobelin Fantôme", 1, ["Gobelin"], "<b>Défaussez</b> ce monstre après l'avoir vaincu.", "MAUDIT"),
            # CarteMonstre("Changeforme", 8, ["Gobelin", "Squelette", "Orc", "Vampire", "Golem", "Liche", "Démon", "Dragon", "Rat"]),
            CarteEvent("Descente angélique", "Gagnez 3pv.", "HEAL"),
            CarteEvent("Bricoleur", "Vous pouvez <b>réparer</b> un de vos objets <b>brisé</b>.", "REPAIR"),
            CarteEvent("Allié", "Si la prochaine carte est un monstre, vous pouvez <b>l'exécuter</b>.", "ALLY"),
            # CarteEvent("Inception", "Répétez l'effet de la dernière carte <b>Événement</b> de la défausse.", "INCEPTION"),
            CarteEvent("Dépeceur de Dragons", "Les joueurs ayant des <b>Dragons</b> dans leur pile peuvent en défausser pour <b>piocher</b> autant d'objets.", "DRAG"),
            CarteEvent("Echoppe Secrete", "Si vous avez <b>moins de 4</b> objets intacts, <b>piochez</b> un objet.", "SHOP"),
            CarteEvent("Injection argileuse", "Gagnez <b>3 PV</b> pour chaque <b>Golem</b> dans votre pile.", "INJECTION"),
            CarteEvent("Tempête des âmes", "Tous les joueurs doivent remettre un monstre de leur pile de monstres vaincus dans le Donjon. Mélangez-le.", "SOULSTORM"),
            CarteEvent("Traquenard", "Si la prochaine carte est un monstre, vous ne pouvez pas <b>l'exécuter</b>.", "TRAP"),
        ]
        for i, carte in enumerate(self.cartes):
            carte.index = i  # Assigner l'index à chaque carte
            carte.ordre = i  # Assigner l'ordre initial à chaque carte
        self.nb_cartes = len(self.cartes)
        self.ordre = None
        self.index = 0

    def melange(self):
        self.ordre = np.random.permutation(self.nb_cartes)
        self.index = 0

    def remelange(self):
        # Conserver les cartes restantes
        cartes_restantes = self.ordre[self.index:]
        # Mélanger les cartes restantes
        self.ordre = np.random.permutation(cartes_restantes)
        # Réinitialiser l'index
        self.index = 0
        self.nb_cartes = len(self.ordre)
    
    def ajouter_monstre(self, monstre_remis):
        # monstre_remis.executed = False --> maintenant quand on pioche la carte
        self.ordre = np.append(self.ordre, monstre_remis.index)
        self.nb_cartes += 1
        # Cette Fct ne re melange pas, le faire separement

    @property
    def vide(self):
        # assert self.nb_cartes == len(self.ordre) pour verifier
        return self.index == self.nb_cartes

    def prochaine_carte(self):
        index = self.index
        self.index += 1
        return self.cartes[self.ordre[index]]


    def rajoute_en_haut_de_la_pile(self, carte):
        carte.executed = False
        self.ordre = np.insert(self.ordre, self.index, carte.index)
        self.nb_cartes += 1

    def ajouter_carte(self, carte):
        assert carte not in self.cartes # faut copy pour pas avoir la meme instance
        self.cartes.append(carte)
        self.nb_cartes += 1
        self.ordre = np.append(self.ordre, len(self.cartes) - 1)
