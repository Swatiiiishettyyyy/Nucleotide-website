from .Member_model import Member

def save_member(db, user, req):
    if req.member_id == 0:
        # Create new member
        member = Member(
            user_id=user.id,
            name=req.name,
            relation=req.relation
        )
        db.add(member)
        db.commit()
        db.refresh(member)
    else:
        # Update existing member
        member = db.query(Member).filter_by(id=req.member_id, user_id=user.id).first()
        if not member:
            return None
        member.name = req.name
        member.relation = req.relation
        db.commit()
    return member

def get_members_by_user(db, user):
    return db.query(Member).filter_by(user_id=user.id).all()