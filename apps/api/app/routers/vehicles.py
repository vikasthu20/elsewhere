from fastapi import APIRouter
from app.legacy_routes import vehicles, vehicle_detail, add_vehicle, my_vehicles
router = APIRouter()
router.add_api_route('/vehicles', vehicles, methods=['GET'], tags=['vehicles'])
router.add_api_route('/vehicles/mine', my_vehicles, methods=['GET'], tags=['vehicles'])
router.add_api_route('/vehicles/{vehicle_id}', vehicle_detail, methods=['GET'], tags=['vehicles'])
router.add_api_route('/vehicles', add_vehicle, methods=['POST'], status_code=201, tags=['vehicles'])
