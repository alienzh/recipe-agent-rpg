import importlib
import os, sys, tempfile, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import game  # noqa: E402


def fresh():
    path = os.path.join(tempfile.mkdtemp(), "rpg.db")
    return game.get_db(path), path


def test_default_db_path_is_in_server_root(monkeypatch):
    monkeypatch.delenv("RPG_DB_PATH", raising=False)
    importlib.reload(game)
    expected = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rpg.db"))
    assert os.path.normcase(game.DB_PATH) == os.path.normcase(expected)


def test_create_sets_class_and_hp():
    conn, _ = fresh()
    msg = game.create_character(conn, "Warrior")
    assert "warrior" in msg.lower()
    card = game.get_character(conn)
    assert "warrior" in card.lower() and "30/30" in card


def test_unknown_class_rejected():
    conn, _ = fresh()
    assert "warrior" in game.create_character(conn, "ninja").lower()


def test_get_character_before_creation():
    conn, _ = fresh()
    assert "class" in game.get_character(conn).lower()


def test_attack_requires_an_enemy():
    conn, _ = fresh()
    game.create_character(conn, "warrior")
    assert "no enemy" in game.attack(conn).lower()


def test_encounter_sets_combat_and_persists_across_connections():
    conn, path = fresh()
    game.create_character(conn, "warrior")
    assert "appears" in game.start_encounter(conn, random.Random(7)).lower()
    assert game.current_mode(game.get_db(path)) == "combat"


def test_seeded_combat_is_deterministic():
    def run():
        conn, _ = fresh()
        game.create_character(conn, "mage")
        game.start_encounter(conn, random.Random(1))
        return game.attack(conn, random.Random(1))
    assert run() == run()


def test_combat_resolves_back_to_narration():
    conn, path = fresh()
    game.create_character(conn, "warrior")
    game.start_encounter(conn, random.Random(3))
    rng = random.Random(3)
    for _ in range(60):
        if game.current_mode(game.get_db(path)) != "combat":
            break
        game.attack(conn, rng)
    assert game.current_mode(game.get_db(path)) == "narration"


def test_create_character_resets_game():
    conn, path = fresh()
    game.create_character(conn, "warrior")
    game.start_encounter(conn, random.Random(0))
    game.create_character(conn, "mage")
    assert game.current_mode(game.get_db(path)) == "narration"
    assert "mage" in game.get_character(conn).lower()
