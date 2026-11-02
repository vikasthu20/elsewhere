from fastapi import APIRouter
from app.legacy_routes import review
router = APIRouter()
router.add_api_route('/reviews', review, methods=['POST'], status_code=201, tags=['reviews'])
