"""Destination search and public serialization helpers."""
def serialize_destination(item):
    return {"id":item.id,"name":item.name,"region":item.region,"category":item.category,
            "description":item.description,"image_url":item.image_url,
            "latitude":item.latitude,"longitude":item.longitude}

def apply_destination_filters(query, *, search=None, category=None):
    if search:
        query = query.filter(query.column_descriptions[0]["entity"].name.ilike(f"%{search}%"))
    if category:
        query = query.filter(query.column_descriptions[0]["entity"].category.ilike(category))
    return query
