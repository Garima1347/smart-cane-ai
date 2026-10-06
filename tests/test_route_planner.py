import requests

from src.navigation.route_planner import RoutePlanner, RoutePlannerError


class MockResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP {self.status_code}"
            )

    def json(self):
        return self.data


class MockSession:
    def __init__(self):
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        if "nominatim.openstreetmap.org" in url:
            return MockResponse(
                [
                    {
                        "lat": "28.6139",
                        "lon": "77.2090",
                    }
                ]
            )

        if "router.project-osrm.org" in url:
            return MockResponse(
                {
                    "code": "Ok",
                    "routes": [
                        {
                            "distance": 1200.0,
                            "duration": 900.0,
                            "legs": [
                                {
                                    "steps": [
                                        {
                                            "maneuver": {
                                                "type": "depart",
                                                "location": [
                                                    77.0000,
                                                    28.0000,
                                                ],
                                            }
                                        },
                                        {
                                            "maneuver": {
                                                "type": "turn",
                                                "modifier": "left",
                                                "location": [
                                                    77.0050,
                                                    28.0050,
                                                ],
                                            }
                                        },
                                    ]
                                }
                            ],
                        }
                    ],
                }
            )

        raise AssertionError(f"Unexpected URL: {url}")


def test_geocode_destination():
    planner = RoutePlanner(session=MockSession())

    latitude, longitude = planner.geocode_destination(
        "India Gate"
    )

    assert latitude == 28.6139
    assert longitude == 77.2090


def test_geocode_rejects_empty_destination():
    planner = RoutePlanner(session=MockSession())

    try:
        planner.geocode_destination("")
        assert False, "Expected RoutePlannerError"
    except RoutePlannerError as exc:
        assert "empty" in str(exc).lower()


def test_get_route():
    planner = RoutePlanner(session=MockSession())

    route = planner.get_route(
        current_lat=28.0000,
        current_lon=77.0000,
        destination_lat=28.0100,
        destination_lon=77.0100,
    )

    assert route["code"] == "Ok"
    assert len(route["routes"]) == 1
    assert route["routes"][0]["distance"] == 1200.0


def test_plan_route():
    planner = RoutePlanner(session=MockSession())

    route = planner.plan_route(
        current_lat=28.0000,
        current_lon=77.0000,
        destination="India Gate",
    )

    assert route["destination"] == "India Gate"
    assert route["destination_lat"] == 28.6139
    assert route["destination_lon"] == 77.2090
    assert route["distance_m"] == 1200.0
    assert route["duration_s"] == 900.0
    assert len(route["steps"]) == 2
    