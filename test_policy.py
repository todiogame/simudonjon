from smoke_policy import (
    smoke_default_policy_normalizes_legacy_worthit,
    smoke_donjon_worker_batch_runs,
    smoke_draft_policy_equivalence,
    smoke_event_beast_policy_choice_and_decline,
    smoke_fortune_wheel_policy_can_decline,
    smoke_guardian_angel_attrape_reves_confidence,
    smoke_hero_policy_can_decline,
    smoke_invalid_policy_rejected,
    smoke_legacy_wrappers,
    smoke_object_policy_can_choose_target,
    smoke_object_policy_can_decline_combat_use,
    smoke_ordonnanceur_policy_equivalence,
    smoke_policy_controls_object_order,
    smoke_traquenard_legality_independent_from_object_policy,
    smoke_unavailable_hero_ability_does_not_call_policy,
    smoke_traquenard_detects_chevalier_dragon_candidate,
    smoke_traquenard_detects_docteur_de_peste_candidate,
    smoke_traquenard_detects_avatar_late_candidate,
    smoke_defausse_monstre_de_pile_policy_choice,
    smoke_barbecue_du_ponceur_policy_target,
    smoke_cloche_du_deja_vu_routes_distinct_fodder_and_pile_phases,
    smoke_default_policy_cloche_du_deja_vu_split_choices,
    smoke_default_policy_couteaux_de_lancer_targets_strongest,
    smoke_default_policy_divination_destinations_preserve_keep_bottom_rules,
    smoke_default_policy_fil_du_destin_orders_by_old_danger_heuristic,
    smoke_default_policy_fouet_du_fourbe_preserves_first_matching_choice,
    smoke_default_policy_tambour_de_kui_discards_dangerous_visible_monsters,
    smoke_fruit_du_destin_policy_category,
    smoke_fruit_du_destin_invalid_category_rejected,
)


def test_ordonnanceur_policy_equivalence():
    smoke_ordonnanceur_policy_equivalence()


def test_legacy_wrappers():
    smoke_legacy_wrappers()


def test_draft_policy_equivalence():
    smoke_draft_policy_equivalence()


def test_hero_policy_can_decline():
    smoke_hero_policy_can_decline()


def test_unavailable_hero_ability_does_not_call_policy():
    smoke_unavailable_hero_ability_does_not_call_policy()


def test_object_policy_can_decline_combat_use():
    smoke_object_policy_can_decline_combat_use()


def test_object_policy_can_choose_target():
    smoke_object_policy_can_choose_target()


def test_policy_controls_object_order():
    smoke_policy_controls_object_order()


def test_invalid_policy_rejected():
    smoke_invalid_policy_rejected()


def test_default_policy_normalizes_legacy_worthit():
    smoke_default_policy_normalizes_legacy_worthit()


def test_donjon_worker_batch_runs():
    smoke_donjon_worker_batch_runs()


def test_traquenard_legality_independent_from_object_policy():
    smoke_traquenard_legality_independent_from_object_policy()


def test_fortune_wheel_policy_can_decline():
    smoke_fortune_wheel_policy_can_decline()


def test_event_beast_policy_choice_and_decline():
    smoke_event_beast_policy_choice_and_decline()


def test_guardian_angel_attrape_reves_confidence():
    smoke_guardian_angel_attrape_reves_confidence()


def test_traquenard_detects_chevalier_dragon_candidate():
    smoke_traquenard_detects_chevalier_dragon_candidate()


def test_traquenard_detects_docteur_de_peste_candidate():
    smoke_traquenard_detects_docteur_de_peste_candidate()


def test_traquenard_detects_avatar_late_candidate():
    smoke_traquenard_detects_avatar_late_candidate()


def test_defausse_monstre_de_pile_policy_choice():
    smoke_defausse_monstre_de_pile_policy_choice()


def test_barbecue_du_ponceur_policy_target():
    smoke_barbecue_du_ponceur_policy_target()


def test_fruit_du_destin_policy_category():
    smoke_fruit_du_destin_policy_category()


def test_fruit_du_destin_invalid_category_rejected():
    smoke_fruit_du_destin_invalid_category_rejected()


def test_default_policy_couteaux_de_lancer_targets_strongest():
    smoke_default_policy_couteaux_de_lancer_targets_strongest()


def test_default_policy_tambour_de_kui_discards_dangerous_visible_monsters():
    smoke_default_policy_tambour_de_kui_discards_dangerous_visible_monsters()


def test_default_policy_divination_destinations_preserve_keep_bottom_rules():
    smoke_default_policy_divination_destinations_preserve_keep_bottom_rules()


def test_default_policy_fil_du_destin_orders_by_old_danger_heuristic():
    smoke_default_policy_fil_du_destin_orders_by_old_danger_heuristic()


def test_default_policy_fouet_du_fourbe_preserves_first_matching_choice():
    smoke_default_policy_fouet_du_fourbe_preserves_first_matching_choice()


def test_default_policy_cloche_du_deja_vu_split_choices():
    smoke_default_policy_cloche_du_deja_vu_split_choices()


def test_cloche_du_deja_vu_routes_distinct_fodder_and_pile_phases():
    smoke_cloche_du_deja_vu_routes_distinct_fodder_and_pile_phases()
