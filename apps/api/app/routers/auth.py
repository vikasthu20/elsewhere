from fastapi import APIRouter
from app.legacy_routes import register, login, me
router = APIRouter()
router.add_api_route('/auth/register', register, methods=['POST'], status_code=201, tags=['authentication'])
router.add_api_route('/auth/login', login, methods=['POST'], tags=['authentication'])
router.add_api_route('/auth/me', me, methods=['GET'], tags=['authentication'])
