# SimuDonjon 🐉

Simulation de donjons, combats et phases de draft pour l'analyse statistique et l'équilibrage. Ce projet permet de lancer des simulations de descentes de donjons avec des héros, des monstres et des objets, ainsi que des simulations incluant une phase de draft, afin d'analyser les résultats (notamment les taux de victoire) et potentiellement d'équilibrer le jeu.

## ✨ Fonctionnalités

* Simulation de multiples explorations de donjons.
* Simulation d'une phase de draft suivie d'explorations de donjons.
* Gestion détaillée des Héros, Monstres, Objets et Joueurs.
* Calcul et affichage des taux de victoire (Winrate) après un grand nombre de simulations.
* Affichage optionnel des détails des parties simulées.
* Système de priorités pour l'attribution ou l'utilisation des objets.
* Données de jeu (objets, priorités) gérées via des fichiers JSON.
* Utilisation de `colorama` pour un affichage en couleur dans le terminal.
* Minijeu interactif de draft via `minijeu.py`.

## 🔧 Installation

1.  **Clonez le dépôt :**
    ```bash
    git clone [https://github.com/todiogame/simudonjon.git](https://github.com/todiogame/simudonjon.git)
    cd simudonjon
    ```
2.  **Créez un environnement virtuel (recommandé) :**
    ```bash
    python -m venv venv
    ```
3.  **Activez l'environnement virtuel :**
    * Sous Windows :
        ```bash
        .\venv\Scripts\activate
        ```
    * Sous macOS/Linux :
        ```bash
        source venv/bin/activate
        ```
4.  **Installez les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

## 🚀 Utilisation Principale

Il existe deux modes principaux pour lancer les simulations : `donjon.py` pour une simulation standard et `draft.py` pour une simulation incluant une phase de draft.

L'argument passé en ligne de commande détermine le mode d'exécution :

1.  **Afficher les détails d'un nombre limité de parties :**
    Passez un nombre entier comme argument. Cela lancera ce nombre exact de simulations et affichera les détails de chacune.

    * Pour une simulation de donjon standard :
        ```bash
        # Lance 5 simulations et affiche les détails
        python donjon.py 5
        ```
    * Pour une simulation avec draft :
        ```bash
        # Lance 3 simulations avec draft et affiche les détails
        python draft.py 3
        ```

2.  **Calculer le Winrate sur un grand nombre de parties :**
    N'ajoutez aucun argument après le nom du script. Cela lancera un très grand nombre de simulations (par exemple, 100 000) sans afficher les détails, puis calculera et affichera un résumé statistique incluant le taux de victoire.

    * Pour une simulation de donjon standard :
        ```bash
        # Lance de nombreuses simulations et affiche le résumé/winrate
        python donjon.py
        ```
    * Pour une simulation avec draft :
        ```bash
        # Lance de nombreuses simulations avec draft et affiche le résumé/winrate
        python draft.py
        ```

3.  **Lancer plusieurs simulations en parallèle :**
    Pour accélérer la collecte de données, vous pouvez lancer plusieurs simulations simultanément dans différents terminaux, puis agréger les résultats :

    * Dans plusieurs terminaux :
        ```bash
        python draft.py
        ```
    
    * Utilisez `aggreg.py` pour combiner les résultats :
    ```bash
    python aggreg.py
    ```
    
    Cela produira un rapport consolidé avec les statistiques agrégées de toutes les simulations.

## 📁 Structure du Projet

* `donjon.py`: Point d'entrée pour les simulations de donjon standard. Gère les arguments `sys.argv` pour le nombre de parties ou le mode winrate.
* `draft.py`: Point d'entrée pour les simulations incluant une phase de draft. Gère les arguments `sys.argv`.
* `simu.py`: Point d'entrée alternatif offrant plus d'options via `argparse`. Peut-être utilisé pour des tests spécifiques ou par les autres scripts.
* `aggreg.py`: Module d'agrégation des statistiques et résultats de simulation. Permet de consolider et analyser les données sur plusieurs parties.
* `wr.py`: Contient la logique spécifique au calcul et à l'affichage formaté du winrate.
* `heros.py`, `monstres.py`, `objets.py`, `joueurs.py`: Modules définissant les classes principales du jeu (Héros, Monstre, Objet, Joueur).
* `prio.py`: Gère la logique de priorisation des objets.
* `minijeu.py`: Semble contenir la logique pour des mini-jeux potentiels.
* `*.json`: Fichiers contenant les données du jeu (statistiques des objets, priorités, visuels).
    * `item_visuals.json`
    * `priorites_objets.json`

## 📦 Dépendances

Les dépendances nécessaires sont listées dans `requirements.txt`:

* `numpy`: Utilisé pour des calculs numériques.
* `pandas`: Utilisé pour l'analyse et la manipulation des données.
* `tqdm`: Utilisé pour afficher des barres de progression.

