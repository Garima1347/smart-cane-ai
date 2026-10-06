from src.navigation.navigator import Navigator


def make_test_route():
    return {
        "destination": "Test",
        "destination_lat": 28.0001,
        "destination_lon": 77.0000,
        "steps": [
            {
                "maneuver": {
                    "type": "depart",
                    "location": [77.0000, 28.0000],
                }
            },
            {
                "maneuver": {
                    "type": "turn",
                    "modifier": "left",
                    "location": [77.0000, 28.0005],
                }
            },
            {
                "maneuver": {
                    "type": "arrive",
                    "location": [77.0000, 28.0006],
                }
            },
        ],
    }


def test_navigator_loads_route():
    navigator = Navigator(language="bilingual")
    navigator.load_route(make_test_route())

    assert navigator.destination_lat == 28.0001
    assert navigator.destination_lon == 77.0000
    assert len(navigator.route_steps) == 3


def test_navigator_gives_turn_instruction():
    navigator = Navigator(language="bilingual")
    navigator.load_route(make_test_route())

    result = navigator.update(28.0003, 77.0000)

    assert result["status"] == "navigating"
    assert "Turn left" in result["message"]
    assert "बाएं" in result["message"]


def test_navigator_does_not_arrive_too_early():
    navigator = Navigator(language="bilingual")
    navigator.load_route(make_test_route())

    result = navigator.update(28.0005, 77.0000)

    assert result["status"] == "navigating"
    assert "arrived" not in result["message"].lower()
    assert "पहुँच" not in result["message"]


def test_navigator_arrives_at_destination():
    navigator = Navigator(language="bilingual")
    navigator.load_route(make_test_route())

    result = navigator.update(28.0001, 77.0000)

    assert result["status"] == "arrived"
    assert "arrived" in result["message"].lower()
    assert "पहुँच" in result["message"]


def test_navigator_english_mode():
    navigator = Navigator(language="english")
    navigator.load_route(make_test_route())

    result = navigator.update(28.0003, 77.0000)

    assert "Turn left" in result["message"]
    assert "बाएं" not in result["message"]


def test_navigator_hindi_mode():
    navigator = Navigator(language="hindi")
    navigator.load_route(make_test_route())

    result = navigator.update(28.0003, 77.0000)

    assert "बाएं" in result["message"]
    assert "Turn left" not in result["message"]
