from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .config import CORS_ORIGINS
from .db import Base, SessionLocal, engine
from .models import User
from .reference import seed_reference
from .routers import auth, data, insights
from .security import hash_password


def create_app() -> FastAPI:
    app = FastAPI(title='UHS Knowledge Discovery System', version='1.0.0',
                  description='Knowledge discovery on ailment incidence at the University Health Service (Jaja Clinic).')
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=['*'], allow_headers=['*'])
    app.include_router(auth.router)
    app.include_router(data.router)
    app.include_router(insights.router)

    @app.get('/api/health')
    def health():
        return {'status': 'ok'}

    @app.on_event('startup')
    def startup():
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            seed_reference(db)
            if not db.query(User).first():  # first run: create an administrator
                db.add(User(username='admin', full_name='System Administrator', role='admin',
                            password_hash=hash_password('Admin@12345')))
                db.commit()

    dist = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
    if dist.exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

        @app.get('/{path:path}', include_in_schema=False)
        def spa(path: str):
            f = (dist / path).resolve()  # dist is already resolved; reject anything outside it
            return FileResponse(f if path and f.is_file() and f.is_relative_to(dist) else dist / 'index.html')
    return app


app = create_app()
