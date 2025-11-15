from Address_model import Address
from  Address_audit_model import AddressAudit

def save_address(db, user, req):
    if req.address_id == 0:
        # Create new address
        address = Address(
            user_id=user.id,
            first_name=req.first_name,
            last_name=req.last_name,
            email=req.email,
            mobile=req.mobile,
            address_label=req.address_label,
            street_address=req.street_address,
            landmark=req.landmark,
            city=req.city,
            state=req.state,
            postal_code=req.postal_code,
            country=req.country,
            save_for_future=req.save_for_future
        )
        db.add(address)
        db.commit()
        db.refresh(address)
        action = "created"
    else:
        # Edit existing address
        address = db.query(Address).filter_by(id=req.address_id, user_id=user.id).first()
        if not address:
            return None
        address.first_name = req.first_name
        address.last_name = req.last_name
        address.email = req.email
        address.mobile = req.mobile
        address.address_label = req.address_label
        address.street_address = req.street_address
        address.landmark = req.landmark
        address.city = req.city
        address.state = req.state
        address.postal_code = req.postal_code
        address.country = req.country
        address.save_for_future = req.save_for_future
        db.commit()
        action = "updated"

    # Audit log
    audit = AddressAudit(
        user_id=user.id,
        username=user.name,
        phone_number=user.mobile,
        address_id=address.id,
        action=action
    )
    db.add(audit)
    db.commit()

    return address

def get_addresses_by_user(db, user):
    return db.query(Address).filter_by(user_id=user.id).all()