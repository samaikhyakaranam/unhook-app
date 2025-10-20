import os
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import os, json, firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    # Try to load from Render environment variable first
    if os.environ.get("FIREBASE_SERVICE_ACCOUNT"):
        cred_dict = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    else:
        # fallback for local dev only
        cred = credentials.Certificate("firebase-key.json")
        firebase_admin.initialize_app(cred)

db = firestore.client()

app = FastAPI(title="Unhook API")

def verify(id_token: str):
    try:
        decoded = auth.verify_id_token(id_token)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid ID token")

def today_key():
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%d")

class CheckInBody(BaseModel):
    vaped: bool | None = None
    cravings: int = 0
    mood: int = 3
    journal: str | None = None
    doneExercises: list[str] = []

@app.post("/api/checkin")
def check_in(body: CheckInBody, authorization: str = Header(...)):
    """
    Client sends Firebase ID token in Authorization header: 'Bearer <token>'
    """
    token = authorization.split("Bearer ")[-1]
    uid = verify(token)
    user_ref = db.collection("users").document(uid)
    day_ref  = user_ref.collection("days").document(today_key())

    user_ref.set({
        "coins": 0, "streak": 0,
        "buddy": {"type": "bunny", "mood": "ok"},
        "createdAt": firestore.SERVER_TIMESTAMP
    }, merge=True)

    earned = 0
    base_actions = 0

    earned += 5; base_actions += 1

    if body.journal:
        earned += 5; base_actions += 1
    if body.doneExercises:
        earned += 5; base_actions += 1
    if body.vaped is False:
        earned += 10
    elif body.vaped is True:
        earned += 0

    day_ref.set({
        "checkedIn": True,
        "vaped": body.vaped,
        "cravings": int(body.cravings),
        "mood": int(body.mood),
        "journal": (body.journal or "")[:800],
        "doneExercises": body.doneExercises,
        "pointsEarned": earned,
        "updatedAt": firestore.SERVER_TIMESTAMP
    }, merge=True)

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    y_doc = user_ref.collection("days").document(yesterday).get()
    user_doc = user_ref.get()
    curr = user_doc.to_dict() or {}
    streak = int(curr.get("streak", 0))
    if y_doc.exists and y_doc.to_dict().get("checkedIn"):
        streak += 1
    else:
        streak = 1

    coins = int(curr.get("coins", 0)) + earned
    mood = "happy" if base_actions >= 2 and (body.vaped is False) else "ok"
    if body.vaped is True:
        mood = "sad"

    user_ref.update({
        "coins": coins,
        "streak": streak,
        "buddy": {"type": curr.get("buddy", {}).get("type", "bunny"), "mood": mood}
    })

    return {"ok": True, "earned": earned, "coins": coins, "streak": streak, "buddyMood": mood}

class PurchaseBody(BaseModel):
    itemId: str
    price: int

@app.post("/api/purchase")
def purchase_item(body: PurchaseBody, authorization: str = Header(...)):
    token = authorization.split("Bearer ")[-1]
    uid = verify(token)
    user_ref = db.collection("users").document(uid)
    doc = user_ref.get().to_dict() or {}
    coins = int(doc.get("coins", 0))
    if coins < body.price:
        raise HTTPException(status_code=400, detail="Not enough coins")
    db.transaction()
    user_ref.update({"coins": coins - body.price})
    user_ref.collection("shopItems").document(body.itemId).set({"owned": True, "equipped": True}, merge=True)
    return {"ok": True, "coins": coins - body.price}