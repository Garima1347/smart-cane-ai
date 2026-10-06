
"""
Turn-by-turn navigation state manager for Smart Cane.

Responsibilities:
- Track the current navigation step.
- Calculate distance to the next maneuver.
- Generate Hindi + English navigation messages.
- Advance a maneuver only when the user reaches it.
- Detect actual arrival.
- Optionally send messages to the existing voice system.

This module does NOT control:
- Camera / YOLO
- Ultrasonic sensors
- Ground hazard detection
- GPIO
- FastAPI
"""

from __future__ import annotations

from typing import Any, Callable

from .navigation_utils import distance_m


VoiceCallback = Callable[[str], None]


class Navigator:
    """
    Manages turn-by-turn navigation for an already-created route.

    The route format expected here is the dictionary returned by
    RoutePlanner.plan_route().
    """

    # Keep this small so we do not skip an actual turn.
    MANEUVER_REACHED_DISTANCE_M = 6.0

    # Arrival is based on the actual destination coordinate,
    # not merely on reaching the final OSRM step.
    ARRIVAL_DISTANCE_M = 8.0

    def __init__(
        self,
        voice_callback: VoiceCallback | None = None,
        language: str = "bilingual",
    ) -> None:
        self.voice_callback = voice_callback

        if language not in {"english", "hindi", "bilingual"}:
            raise ValueError(
                "language must be 'english', 'hindi', or 'bilingual'"
            )

        self.language = language

        self.route_steps: list[dict[str, Any]] = []
        self.current_step = 0

        self.destination_lat: float | None = None
        self.destination_lon: float | None = None
        self.destination_name: str | None = None

        self.navigation_active = False
        self.arrived = False

    def load_route(self, route: dict[str, Any]) -> None:
        """
        Load a route returned by RoutePlanner.plan_route().
        """

        steps = route.get("steps", [])

        if not steps:
            raise ValueError("Route contains no navigation steps.")

        if (
            route.get("destination_lat") is None
            or route.get("destination_lon") is None
        ):
            raise ValueError(
                "Route does not contain valid destination coordinates."
            )

        self.route_steps = steps
        self.current_step = 0

        self.destination_lat = float(route["destination_lat"])
        self.destination_lon = float(route["destination_lon"])
        self.destination_name = route.get("destination")

        self.navigation_active = True
        self.arrived = False

    def stop(self) -> None:
        """Stop the current navigation session."""

        self.navigation_active = False
        self.arrived = False
        self.route_steps = []
        self.current_step = 0

    def _get_current_step(self) -> dict[str, Any] | None:
        """Return the current route step."""

        if not self.route_steps:
            return None

        if self.current_step >= len(self.route_steps):
            return None

        return self.route_steps[self.current_step]

    @staticmethod
    def _step_location(
        step: dict[str, Any],
    ) -> tuple[float, float] | None:
        """
        Extract the maneuver location from an OSRM step.

        OSRM stores it as:
            step["maneuver"]["location"] = [longitude, latitude]
        """

        maneuver = step.get("maneuver", {})
        location = maneuver.get("location")

        if (
            not isinstance(location, (list, tuple))
            or len(location) < 2
        ):
            return None

        try:
            longitude = float(location[0])
            latitude = float(location[1])
        except (TypeError, ValueError):
            return None

        return latitude, longitude

    @staticmethod
    def _maneuver_parts(
        step: dict[str, Any],
    ) -> tuple[str, str, int | None]:
        """
        Extract maneuver type, modifier and roundabout exit.
        """

        maneuver = step.get("maneuver", {})

        maneuver_type = str(
            maneuver.get("type", "")
        ).lower()

        modifier = str(
            maneuver.get("modifier", "")
        ).lower()

        exit_number = maneuver.get("exit")

        try:
            if exit_number is not None:
                exit_number = int(exit_number)
        except (TypeError, ValueError):
            exit_number = None

        return maneuver_type, modifier, exit_number

    def _english_instruction(
        self,
        step: dict[str, Any],
        distance: float,
    ) -> str:
        """Create the English navigation instruction."""

        maneuver_type, modifier, exit_number = self._maneuver_parts(
            step
        )

        if maneuver_type == "arrive":
            return "You have arrived at your destination."

        if maneuver_type == "depart":
            return "Start moving."

        distance_text = self._distance_text(distance)

        if maneuver_type == "turn":
            direction = {
                "left": "left",
                "right": "right",
                "slight left": "slight left",
                "slight right": "slight right",
                "sharp left": "sharp left",
                "sharp right": "sharp right",
            }.get(
                modifier,
                "the indicated direction",
            )

            if distance <= self.MANEUVER_REACHED_DISTANCE_M:
                return f"Turn {direction} now."

            return f"Turn {direction} in {distance_text}."

        if maneuver_type == "continue":
            if distance <= self.MANEUVER_REACHED_DISTANCE_M:
                return "Continue straight now."

            return f"Continue straight for {distance_text}."

        if maneuver_type == "new name":
            if distance <= self.MANEUVER_REACHED_DISTANCE_M:
                return "Continue on the road now."

            return f"Continue on the road for {distance_text}."

        if maneuver_type == "roundabout":
            if exit_number is not None:
                if distance <= self.MANEUVER_REACHED_DISTANCE_M:
                    return (
                        f"At the roundabout, take exit "
                        f"{exit_number} now."
                    )

                return (
                    f"At the roundabout in {distance_text}, "
                    f"take exit {exit_number}."
                )

            if distance <= self.MANEUVER_REACHED_DISTANCE_M:
                return "Enter the roundabout now."

            return f"Enter the roundabout in {distance_text}."

        if distance <= self.MANEUVER_REACHED_DISTANCE_M:
            return "Continue now."

        return f"Continue for {distance_text}."

    def _hindi_instruction(
        self,
        step: dict[str, Any],
        distance: float,
    ) -> str:
        """Create the Hindi navigation instruction."""

        maneuver_type, modifier, exit_number = self._maneuver_parts(
            step
        )

        if maneuver_type == "arrive":
            return "आप अपनी मंज़िल पर पहुँच गए हैं।"

        if maneuver_type == "depart":
            return "चलना शुरू करें।"

        distance_text = self._distance_text_hindi(distance)

        directions = {
            "left": "बाएं",
            "right": "दाएं",
            "slight left": "हल्का बाएं",
            "slight right": "हल्का दाएं",
            "sharp left": "तेज़ बाएं",
            "sharp right": "तेज़ दाएं",
        }

        if maneuver_type == "turn":
            direction = directions.get(
                modifier,
                "निर्देशित दिशा में",
            )

            if distance <= self.MANEUVER_REACHED_DISTANCE_M:
                return f"अब {direction} मुड़ें।"

            return f"{distance_text} बाद {direction} मुड़ें।"

        if maneuver_type == "continue":
            if distance <= self.MANEUVER_REACHED_DISTANCE_M:
                return "अब सीधे चलते रहें।"

            return f"{distance_text} तक सीधे चलते रहें।"

        if maneuver_type == "new name":
            if distance <= self.MANEUVER_REACHED_DISTANCE_M:
                return "अब इसी सड़क पर चलते रहें।"

            return f"{distance_text} तक इसी सड़क पर चलते रहें।"

        if maneuver_type == "roundabout":
            if exit_number is not None:
                if distance <= self.MANEUVER_REACHED_DISTANCE_M:
                    return (
                        f"अब गोल चक्कर से {exit_number} नंबर "
                        f"निकास लें।"
                    )

                return (
                    f"{distance_text} बाद गोल चक्कर से "
                    f"{exit_number} नंबर निकास लें।"
                )

            if distance <= self.MANEUVER_REACHED_DISTANCE_M:
                return "अब गोल चक्कर में प्रवेश करें।"

            return f"{distance_text} बाद गोल चक्कर में प्रवेश करें।"

        if distance <= self.MANEUVER_REACHED_DISTANCE_M:
            return "अब सीधे चलते रहें।"

        return f"{distance_text} तक सीधे चलते रहें।"

    @staticmethod
    def _distance_text(distance: float) -> str:
        """Format distance for English speech."""

        distance = max(0.0, distance)

        if distance < 100:
            return f"{round(distance)} meters"

        return f"{round(distance / 10) * 10} meters"

    @staticmethod
    def _distance_text_hindi(distance: float) -> str:
        """Format distance for Hindi speech."""

        distance = max(0.0, distance)

        if distance < 100:
            meters = round(distance)
        else:
            meters = round(distance / 10) * 10

        return f"{meters} मीटर"

    def _build_instruction(
        self,
        step: dict[str, Any],
        distance: float,
    ) -> str:
        """
        Build the final voice instruction according to language mode.

        Arrival is intentionally NOT handled here.
        Arrival is handled only by update() after checking the
        actual destination distance.
        """

        english = self._english_instruction(
            step,
            distance,
        )

        hindi = self._hindi_instruction(
            step,
            distance,
        )

        if self.language == "english":
            return english

        if self.language == "hindi":
            return hindi

        return f"{english} {hindi}"

    def _speak(self, message: str) -> None:
        """Send the message to the configured voice system."""

        if self.voice_callback is not None:
            self.voice_callback(message)

    def _build_arrival_message(self) -> str:
        """Create the final arrival message."""

        english = "You have arrived at your destination."
        hindi = "आप अपनी मंज़िल पर पहुँच गए हैं।"

        if self.language == "english":
            return english

        if self.language == "hindi":
            return hindi

        return f"{english} {hindi}"

    def _mark_arrived(
        self,
        destination_distance: float,
    ) -> dict[str, Any]:
        """
        Mark navigation as completed and generate the arrival response.

        This method is called ONLY after the actual destination
        distance has been checked.
        """

        self.arrived = True
        self.navigation_active = False

        message = self._build_arrival_message()

        self._speak(message)

        return {
            "status": "arrived",
            "message": message,
            "distance_to_destination": round(
                destination_distance,
                1,
            ),
            "destination": self.destination_name,
        }

    def update(
        self,
        current_lat: float,
        current_lon: float,
    ) -> dict[str, Any]:
        """
        Update navigation using the user's current GPS position.

        Returns a status dictionary suitable for FastAPI or main.py.
        """

        if not self.navigation_active:
            return {
                "status": "inactive",
                "message": "Navigation is not active.",
            }

        if (
            self.destination_lat is None
            or self.destination_lon is None
        ):
            self.navigation_active = False

            return {
                "status": "error",
                "message": "Destination coordinates are unavailable.",
            }

        # ---------------------------------------------------------
        # STEP 1: Check actual destination distance.
        #
        # This is the ONLY normal condition that declares arrival.
        # Reaching an intermediate OSRM step does NOT mean arrival.
        # ---------------------------------------------------------

        destination_distance = distance_m(
            current_lat,
            current_lon,
            self.destination_lat,
            self.destination_lon,
        )

        if destination_distance <= self.ARRIVAL_DISTANCE_M:
            return self._mark_arrived(
                destination_distance
            )

        # ---------------------------------------------------------
        # STEP 2: Skip OSRM's initial "depart" instruction.
        # ---------------------------------------------------------

        while (
            self.current_step < len(self.route_steps) - 1
            and self._maneuver_parts(
                self.route_steps[self.current_step]
            )[0]
            == "depart"
        ):
            self.current_step += 1

        # ---------------------------------------------------------
        # STEP 3: Get current navigation step.
        # ---------------------------------------------------------

        step = self._get_current_step()

        if step is None:
            return {
                "status": "complete",
                "message": "No more navigation steps.",
            }

        # ---------------------------------------------------------
        # STEP 4: Validate the maneuver location.
        # ---------------------------------------------------------

        step_location = self._step_location(step)

        if step_location is None:
            self.current_step += 1

            return {
                "status": "skipped",
                "message": "Invalid navigation step skipped.",
                "step": self.current_step,
            }

        step_lat, step_lon = step_location

        distance_to_step = distance_m(
            current_lat,
            current_lon,
            step_lat,
            step_lon,
        )

        # ---------------------------------------------------------
        # STEP 5: Check whether the current maneuver has been
        # reached.
        # ---------------------------------------------------------

        if (
            distance_to_step
            <= self.MANEUVER_REACHED_DISTANCE_M
        ):
            maneuver_type, _, _ = self._maneuver_parts(step)

            # IMPORTANT:
            # An "arrive" OSRM step is not treated as arrival by
            # itself. We already checked the real destination
            # distance above.
            #
            # Therefore, if the OSRM arrive step is reached but
            # destination_distance is still > 8m, we do NOT say
            # "You have arrived".
            if maneuver_type == "arrive":
                return {
                    "status": "navigating",
                    "step": self.current_step,
                    "total_steps": len(self.route_steps),
                    "message": (
                        "Continue toward your destination. "
                        "अपने गंतव्य की ओर चलते रहें।"
                        if self.language == "bilingual"
                        else (
                            "Continue toward your destination."
                            if self.language == "english"
                            else "अपने गंतव्य की ओर चलते रहें।"
                        )
                    ),
                    "distance_to_step": round(
                        distance_to_step,
                        1,
                    ),
                    "distance_to_destination": round(
                        destination_distance,
                        1,
                    ),
                    "destination": self.destination_name,
                }

            # We reached a real maneuver.
            self.current_step += 1

            # If there is no next step, keep navigating toward the
            # destination. Do not falsely declare arrival.
            next_step = self._get_current_step()

            if next_step is None:
                return {
                    "status": "navigating",
                    "step": self.current_step,
                    "total_steps": len(self.route_steps),
                    "message": (
                        "Continue toward your destination. "
                        "अपने गंतव्य की ओर चलते रहें।"
                        if self.language == "bilingual"
                        else (
                            "Continue toward your destination."
                            if self.language == "english"
                            else "अपने गंतव्य की ओर चलते रहें।"
                        )
                    ),
                    "distance_to_destination": round(
                        destination_distance,
                        1,
                    ),
                    "destination": self.destination_name,
                }

            step = next_step

            step_location = self._step_location(step)

            if step_location is None:
                return {
                    "status": "error",
                    "message": "Next navigation step is invalid.",
                }

            step_lat, step_lon = step_location

            distance_to_step = distance_m(
                current_lat,
                current_lon,
                step_lat,
                step_lon,
            )

        # ---------------------------------------------------------
        # STEP 6: Build instruction for the CURRENT valid step.
        #
        # If this is an OSRM "arrive" step but the real destination
        # is still farther than 8m, give a normal continue message
        # instead of saying "arrived".
        # ---------------------------------------------------------

        maneuver_type, _, _ = self._maneuver_parts(step)

        if maneuver_type == "arrive":
            if self.language == "english":
                message = "Continue toward your destination."
            elif self.language == "hindi":
                message = "अपने गंतव्य की ओर चलते रहें।"
            else:
                message = (
                    "Continue toward your destination. "
                    "अपने गंतव्य की ओर चलते रहें।"
                )
        else:
            message = self._build_instruction(
                step,
                distance_to_step,
            )

        return {
            "status": "navigating",
            "step": self.current_step,
            "total_steps": len(self.route_steps),
            "message": message,
            "distance_to_step": round(
                distance_to_step,
                1,
            ),
            "distance_to_destination": round(
                destination_distance,
                1,
            ),
            "destination": self.destination_name,
        }
