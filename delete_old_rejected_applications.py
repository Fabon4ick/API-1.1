from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal  # <-- Импорт своей сессии
from database  import Application     # <-- Импорт модели Application

def delete_old_rejected_applications():
    db: Session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=1)
        applications_to_delete = db.query(Application).filter(
            Application.isRejected == True,
            Application.rejectedDate <= cutoff
        ).all()

        for app in applications_to_delete:
            print(f"Удаляем заявку ID={app.id}, отклонена {app.rejectedDate}")
            db.delete(app)

        db.commit()
        print(f"Удалено {len(applications_to_delete)} заявок")

    finally:
        db.close()

if __name__ == "__main__":
    delete_old_rejected_applications()