"""
Route planning for Smart Cane navigation.

Responsibilities:
- Convert a destination name into GPS coordinates using Nominatim.
- Request a walking route from OSRM.
- Return clean route information to Navigator.

This module does NOT handle:
- Voice/audio
- Sensors
- Camera/YOLO
- FastAPI
- Raspberry Pi GPIO
"""

from __future__ import annotations

from typing import Any

import requests


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/foot"

REQUEST_TIMEOUT = 10

USER_AGENT = "SmartCane/1.0"


class RoutePlannerError(Exception):
    """Raised when a route cannot be created."""


class RoutePlanner:
    """Create walking routes from the current GPS position to a destination."""

    def __init__(
        self,
        timeout: int = REQUEST_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()

        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
            }
        )

    def geocode_destination(self, destination: str) -> tuple[float, float]:
        """
        Convert a destination name/address into latitude and longitude.

        Returns:
            (latitude, longitude)
        """

        destination = destination.strip()

        if not destination:
            raise RoutePlannerError("Destination cannot be empty.")

        params = {
            "q": destination,
            "format": "json",
            "limit": 1,
            "countrycodes": "in",
        }

        try:
            response = self.session.get(
                NOMINATIM_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            results = response.json()

        except requests.RequestException as exc:
            raise RoutePlannerError(
                f"Unable to find destination: {exc}"
            ) from exc

        except ValueError as exc:
            raise RoutePlannerError(
                "Invalid response received from the geocoding service."
            ) from exc

        if not results:
            raise RoutePlannerError(
                f"Destination not found: {destination}"
            )

        try:
            latitude = float(results[0]["lat"])
            longitude = float(results[0]["lon"])

        except (KeyError, TypeError, ValueError) as exc:
            raise RoutePlannerError(
                "Destination coordinates are invalid."
            ) from exc

        return latitude, longitude

    def get_route(
        self,
        current_lat: float,
        current_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> dict[str, Any]:
        """
        Request a walking route from OSRM.

        Returns the complete OSRM route response containing:
        - route distance
        - route duration
        - route legs
        - navigation steps
        """

        coordinates = (
            f"{current_lon},{current_lat};"
            f"{destination_lon},{destination_lat}"
        )

        url = f"{OSRM_URL}/{coordinates}"

        params = {
            "overview": "false",
            "steps": "true",
        }

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        except requests.RequestException as exc:
            raise RoutePlannerError(
                f"Unable to get route: {exc}"
            ) from exc

        except ValueError as exc:
            raise RoutePlannerError(
                "Invalid response received from the routing service."
            ) from exc

        if data.get("code") != "Ok":
            raise RoutePlannerError(
                f"Routing service failed: {data.get('message', 'Unknown error')}"
            )

        routes = data.get("routes")

        if not routes:
            raise RoutePlannerError("No route was found.")

        return data

    def plan_route(
        self,
        current_lat: float,
        current_lon: float,
        destination: str,
    ) -> dict[str, Any]:
        """
        Complete route-planning operation.

        1. Geocode destination.
        2. Request route.
        3. Extract navigation steps.
        """

        destination_lat, destination_lon = self.geocode_destination(
            destination
        )

        route_data = self.get_route(
            current_lat=current_lat,
            current_lon=current_lon,
            destination_lat=destination_lat,
            destination_lon=destination_lon,
        )

        route = route_data["routes"][0]

        legs = route.get("legs", [])

        if not legs:
            raise RoutePlannerError("Route contains no navigation legs.")

        steps = legs[0].get("steps", [])

        if not steps:
            raise RoutePlannerError(
                "Route contains no navigation steps."
            )

        return {
            "destination": destination,
            "destination_lat": destination_lat,
            "destination_lon": destination_lon,
            "distance_m": route.get("distance", 0.0),
            "duration_s": route.get("duration", 0.0),
            "steps": steps,
        }