"""Vehicle listing serialization and availability helpers."""
def serialize_vehicle(vehicle):
    return {"id":vehicle.id,"title":vehicle.title,"category":vehicle.category,
            "make_model":vehicle.make_model,"seats":vehicle.seats,
            "price_per_day":float(vehicle.price_per_day),"city":vehicle.city,
            "description":vehicle.description,"image_url":vehicle.image_url,
            "verified":vehicle.verified,"available":vehicle.available}

def can_be_booked(vehicle) -> bool:
    return bool(vehicle and vehicle.available and vehicle.verified)
