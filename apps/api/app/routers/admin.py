from fastapi import APIRouter
from app.legacy_routes import admin_overview
router = APIRouter()
router.add_api_route('/admin/overview', admin_overview, methods=['GET'], tags=['administration'])
