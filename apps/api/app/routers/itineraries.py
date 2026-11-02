from fastapi import APIRouter
from app.legacy_routes import create_itinerary, my_itineraries
router = APIRouter()
router.add_api_route('/itineraries', create_itinerary, methods=['POST'], status_code=201, tags=['itineraries'])
router.add_api_route('/itineraries/mine', my_itineraries, methods=['GET'], tags=['itineraries'])
