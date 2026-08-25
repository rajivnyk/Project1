from app import create_app
from config.database import db
from models import User, Employee, RevokedToken

app = create_app()
with app.app_context():
    db.create_all()
    print("Database tables created successfully!")
