from fastapi import APIRouter
from app.legacy_routes import budget
router = APIRouter()
router.add_api_route('/budget/estimate', budget, methods=['GET'], tags=['budget'])
