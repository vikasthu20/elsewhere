"""Idempotent starter seed data. Run: python scripts_seed.py"""
from app.db import Base, engine, SessionLocal
from app.models import Destination, User, Vehicle, Role
from app.security import hash_password

DESTINATION_SEEDS = [
    ("Munnar", "Kerala, India", "Nature", "Tea gardens, cloud-soft hills and slow mornings.", "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=1200"),
    ("Pondicherry", "Tamil Nadu, India", "Coastal", "French-quarter lanes, cafés and quiet beaches.", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1200"),
    ("Jaipur", "Rajasthan, India", "Heritage", "Palaces, craft traditions and colour at every turn.", "https://images.unsplash.com/photo-1477587458883-47145ed94245?w=1200"),
    ("Langkawi", "Kedah, Malaysia", "Island", "Rainforest, limestone cliffs and turquoise water.", "https://images.unsplash.com/photo-1513415277900-a62401e19be4?w=1200"),
    ("Bali", "Indonesia", "Culture", "Temple mornings, green terraces and island rituals.", "https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=1200"),
    ("Singapore", "Singapore", "City", "Garden architecture, neighbourhood food and design.", "https://images.unsplash.com/photo-1525625293386-3f8f99389edd?w=1200"),
]

USER_SEEDS = [
    ("Elsewhere Admin", "admin@elsewhere.com", "+919876543210", "Admin123!", Role.admin),
    ("Ravi Rides", "owner@elsewhere.com", "+919876543211", "Owner123!", Role.owner),
    ("Priya Traveller", "traveller@elsewhere.com", "+919876543212", "Traveller123!", Role.customer),
]

VEHICLE_SEEDS = [
    ("Toyota Innova Crysta", "SUV", "Toyota Innova", 7, 4200.0, "Chennai", "Spacious 7-seater with automatic transmission and AC.", "https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?w=1000"),
    ("Honda City", "Sedan", "Honda City", 5, 2500.0, "Chennai", "Comfortable sedan for city and highway drives.", "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=1000"),
    ("Tempo Traveller", "Van", "Force Motors Tempo Traveller", 12, 6800.0, "Coimbatore", "12-seat passenger van for family and group tours.", "https://images.unsplash.com/photo-1570125909232-eb263c188f7e?w=1000"),
    ("Royal Enfield Classic 350", "Bike", "Royal Enfield Classic 350", 2, 950.0, "Pondicherry", "Cruiser motorcycle including helmets.", "https://images.unsplash.com/photo-1558981806-ec527fa84c39?w=1000"),
]

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed destinations
        for name, region, category, description, image_url in DESTINATION_SEEDS:
            exists = db.query(Destination).filter(Destination.name == name).first()
            if not exists:
                db.add(Destination(name=name, region=region, category=category, description=description, image_url=image_url, is_published=True))
        
        # Seed users
        owner_user = None
        for name, email, phone, pwd, role in USER_SEEDS:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(name=name, email=email, phone=phone, password_hash=hash_password(pwd), role=role, is_active=True)
                db.add(user)
                db.flush()
            if role == Role.owner:
                owner_user = user

        # Seed vehicles
        if owner_user:
            for title, cat, make_model, seats, price, city, desc, img in VEHICLE_SEEDS:
                veh = db.query(Vehicle).filter(Vehicle.title == title).first()
                if not veh:
                    db.add(Vehicle(
                        owner_id=owner_user.id,
                        title=title,
                        category=cat,
                        make_model=make_model,
                        seats=seats,
                        price_per_day=price,
                        city=city,
                        description=desc,
                        image_url=img,
                        verified=True,
                        available=True
                    ))

        db.commit()
        print("Elsewhere seed data completed successfully.")
    finally:
        db.close()
