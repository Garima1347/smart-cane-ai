"""
Navigation utility functions.

These functions are independent of GPS, FastAPI, Raspberry Pi hardware,
or voice/audio systems so they can be tested separately.
"""

import math


EARTH_RADIUS_M = 6_371_000


def distance_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Calculate the distance between two GPS coordinates in meters
    using the Haversine formula.
    """

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_M * c


def maneuver_text(step: dict) -> str:
    """
    Convert an OSRM navigation step into a simple human-readable
    maneuver description.
    """

    maneuver = step.get("maneuver", {})
    maneuver_type = maneuver.get("type", "")
    modifier = maneuver.get("modifier", "")

    if maneuver_type == "arrive":
        return "You have arrived at your destination."

    if maneuver_type == "depart":
        return "Start moving."

    if maneuver_type == "turn":
        if modifier == "left":
            return "Turn left."
        if modifier == "right":
            return "Turn right."
        if modifier == "slight left":
            return "Slight left."
        if modifier == "slight right":
            return "Slight right."
        if modifier == "sharp left":
            return "Sharp left."
        if modifier == "sharp right":
            return "Sharp right."

        return "Turn."

    if maneuver_type == "continue":
        return "Continue straight."

    if maneuver_type == "new name":
        return "Continue on the road."

    if maneuver_type == "roundabout":
        exit_number = maneuver.get("exit")

        if exit_number is not None:
            return f"At the roundabout, take exit {exit_number}."

        return "Enter the roundabout."

    return "Continue."