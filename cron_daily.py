from datetime import datetime, timedelta, timezone
import firebase_admin
from firebase_admin import credentials
from google.cloud import firestore

cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred)
db = firestore.Client()

def main():
    y = (datetime.now(timezone.utc) - timedelta(days=1)).astimezone().strftime("%Y%m%d")
    users = db.collection("users").stream()
    for u in users:
        uid = u.id
        day = db.collection("users").document(uid).collection("days").document(y).get()
        if not day.exists or not day.to_dict().get("checkedIn"):
            db.collection("users").document(uid).update({"buddy.mood": "sad"})
    print("done")

if __name__ == "__main__":
    main()