from fastapi import APIRouter
from . import auth, destinations, itineraries, vehicles, bookings, reviews, budget, admin
api = APIRouter()
for module in (auth, destinations, itineraries, vehicles, bookings, reviews, budget, admin):
    api.include_router(module.router)
__all__ = ['api']
