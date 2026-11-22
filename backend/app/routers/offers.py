from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.models import User
from app.schemas.common import ok
from app.schemas.offer import OfferIn, OfferRespondIn
from app.services import application_service, offer_service

router = APIRouter(prefix="/applications", tags=["offers"])


@router.get("/{application_id}/offer")
def get_offer(
    application_id: int,
    user: User = Depends(require_role("seeker", "employer")),
    db: Session = Depends(get_db),
):
    try:
        application_service.get_visible_application(db, user, application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    offer = offer_service.get_offer(db, application_id)
    return ok(offer_service.offer_to_dict(offer) if offer else None)


@router.post("/{application_id}/offer")
def create_offer(
    application_id: int,
    payload: OfferIn,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    try:
        offer = offer_service.create_offer(
            db, user, application_id, payload.model_dump()
        )
    except offer_service.OfferError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ok(offer_service.offer_to_dict(offer), message="Offer 已发送")


@router.post("/{application_id}/offer/respond")
def respond_offer(
    application_id: int,
    payload: OfferRespondIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        offer = offer_service.respond_offer(
            db, user, application_id, payload.action, payload.note
        )
    except offer_service.OfferError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    message = "已接受 Offer" if payload.action == "accept" else "已拒绝 Offer"
    return ok(offer_service.offer_to_dict(offer), message=message)
