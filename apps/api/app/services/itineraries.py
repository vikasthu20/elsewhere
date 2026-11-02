"""Itinerary draft generation helpers. Route facts must be supplied by a maps provider."""
def build_draft_stops(days: int):
    return [{"day":n,"title":"Arrival & local discovery" if n == 1 else "Explore nearby highlights",
             "detail":"Draft suggestion. Confirm route, opening hours and travel times before departure."}
            for n in range(1, min(days, 5) + 1)]
