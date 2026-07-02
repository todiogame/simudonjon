from joueurs import Joueur
from objets import CoeurDeTarasque, PorteBoulesDuPonceur
from simu import _preparer_debut_iteration_tour


class DummyHero:
    nom = "Dummy"
    pv_bonus = 10


class DummyMonster:
    def __init__(self, title):
        self.titre = title


def _player(*objets):
    return Joueur("Tester", DummyHero(), list(objets))


def test_turn_counter_survives_replay_segment():
    current = _player()
    other = _player()
    current.monstres_ajoutes_ce_tour = 4
    current.rejoue = True
    current.doit_passer = True
    other.rejoue = True
    other.doit_passer = True

    rejoue_precedent = _preparer_debut_iteration_tour([current, other], current)

    assert rejoue_precedent is True
    assert current.monstres_ajoutes_ce_tour == 4
    assert current.rejoue is False
    assert current.doit_passer is False
    assert other.rejoue is False
    assert other.doit_passer is False


def test_turn_counter_resets_on_new_real_turn():
    current = _player()
    current.monstres_ajoutes_ce_tour = 4

    rejoue_precedent = _preparer_debut_iteration_tour([current], current)

    assert rejoue_precedent is False
    assert current.monstres_ajoutes_ce_tour == 0


def test_porte_boules_counts_victories_from_whole_turn():
    porte_boules = PorteBoulesDuPonceur()
    player = _player(porte_boules)
    log_details = []

    for index in range(5):
        player.ajouter_monstre_vaincu(DummyMonster(f"M{index}"))

    porte_boules.fin_tour(player, None, log_details)

    assert player.pv_total == 15
    assert "gagner 5 PV" in log_details[-1]


def test_recovered_monsters_do_not_trigger_multi_kill_bonus():
    porte_boules = PorteBoulesDuPonceur()
    player = _player(porte_boules)
    log_details = []

    for index in range(5):
        player.ajouter_monstre_vaincu(DummyMonster(f"M{index}"), compte_tour=False)

    porte_boules.fin_tour(player, None, log_details)

    assert player.pv_total == 10
    assert log_details == []


def test_coeur_de_tarasque_uses_same_turn_counter():
    coeur = CoeurDeTarasque()
    player = _player(coeur)
    log_details = []

    player.ajouter_monstre_vaincu(DummyMonster("A"))
    player.ajouter_monstre_vaincu(DummyMonster("B"))

    coeur.fin_tour(player, None, log_details)

    assert player.pv_total == 14
    assert "gagner 1 PV" in log_details[-1]
