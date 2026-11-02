from fastapi import APIRouter
from app.legacy_routes import create_booking, my_bookings, owner_bookings, update_owner_booking
router = APIRouter()
router.add_api_route('/bookings', create_booking, methods=['POST'], status_code=201, tags=['bookings'])
router.add_api_route('/bookings/mine', my_bookings, methods=['GET'], tags=['bookings'])
router.add_api_route('/owner/bookings', owner_bookings, methods=['GET'], tags=['owner'])
router.add_api_route('/owner/bookings/{booking_id}', update_owner_booking, methods=['PATCH'], tags=['owner'])
