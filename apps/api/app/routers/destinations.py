from fastapi import APIRouter
from app.legacy_routes import destinations, destination_detail, add_destination
router = APIRouter()
router.add_api_route('/destinations', destinations, methods=['GET'], tags=['destinations'])
router.add_api_route('/destinations/{destination_id}', destination_detail, methods=['GET'], tags=['destinations'])
router.add_api_route('/destinations', add_destination, methods=['POST'], status_code=201, tags=['administration'])
