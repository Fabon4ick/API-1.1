import json
import os
import time
from multiprocessing.sharedctypes import synchronized

from sqlalchemy import or_, cast
from starlette.responses import JSONResponse
from database import *
from database import Feedback, Application
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
import datetime as dt
import base64
import logging
from fastapi import HTTPException, Depends, Query, Path, BackgroundTasks
from sqlalchemy.orm import Session, sessionmaker, joinedload
from datetime import date
import requests
import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging
from dotenv import load_dotenv

#firebase_credentials = os.getenv("FIREBASE_CREDENTIALS_JSON")
#if not firebase_credentials:
#    raise ValueError("Не найдены Firebase credentials")

#cred = credentials.Certificate(json.loads(firebase_credentials))
#firebase_admin.initialize_app(cred)

from fastapi import FastAPI

app = FastAPI()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TABLE_MODELS = {
    "civil_category": CivilCategory,
    "disability_category": DisabilityCategorie,
    "disease": Disease,
    "family_status": FamilyStatus,
    "service": Service,
    "application_duration": ApplicationDuration,
    "rejection_reason": RejectionReason
}

class user_response(BaseModel):
    id: int
    name: str
    surname: str
    patronymic: str
    phoneNumber: str
    birthday: datetime
    passportSeries: str
    passportNumber: str
    whoGave: str
    whenGet: datetime
    departmentCode: int
    photo: Optional[str] = None
    address: Optional[str] = None
    disabilityCategoriesId: Optional[int] = None
    pensionAmount: Optional[int] = None
    familyStatusId: Optional[int] = None
    password: str
    fcmToken: Optional[str] = None

    class Config:
        orm_mode = True

class application_response(BaseModel):
    id: Optional[int]
    userId: int
    isHaveReabilitation: bool
    dateStart: datetime
    dateEnd: datetime
    staffId: int
    durationId: int
    isRejected: bool
    rejectedDate: Optional[date] = None
    rejectionReasonId: Optional[int] = None

class FeedbackResponse(BaseModel):
    comment: str
    surname: str
    name: str
    patronymic: str
    photo: Optional[bytes]

class FeedbackRequest(BaseModel):
    userId: int
    staffId: int
    comment: str
    rating: int

class DiseaseRequest(BaseModel):
    userId: int
    diseaseIds: List[int]

    class Config:
        orm_mode = True

class CivilCategoryRequest(BaseModel):
    userId: int
    civilCategoryIds: List[int]

    class Config:
        orm_mode = True

class ServiceRequest(BaseModel):
    applicationId: int
    serviceIds: List[int]

    class Config:
        orm_mode = True

class ApplicationUpdateSchema(BaseModel):
    dateStart: dt.date
    dateEnd: dt.date
    staffId: Optional[int] = None

class StaffUpdate(BaseModel):
    photo: Optional[bytes] = None
    name: str
    surname: str
    patronymic: Optional[str] = None
    birth: datetime
    employmentDay: datetime
    bio: str
    isVisible: bool

class StaffCreate(BaseModel):
    photo: bytes | None = None
    name: str
    surname: str
    patronymic: str | None = None
    birth: date
    employmentDay: date
    bio: str
    isVisible: bool

class ItemRequest(BaseModel):
    name: str

class ReplaceRequest(BaseModel):
    old_id: int
    new_id: int

class FeedbackVisibilityUpdate(BaseModel):
    isVisible: bool

class RejectionData(BaseModel):
    rejectedDate: date
    rejectionReasonId: int

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def connection_test():
    return {
        "status" : 200,
        "message" : "Подключение установленно"
    }

@app.put("/applications/{id}/reject")
async def reject_application(
    id: int,
    data: RejectionData,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    application = db.query(Application).filter(Application.id == id).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    application.isRejected = True
    application.rejectedDate = data.rejectedDate
    application.rejectionReasonId = data.rejectionReasonId
    db.commit()

    # Получаем токен пользователя
    user = db.query(User).filter(User.id == application.userId).first()
    if user and user.fcmToken:
        title = "Заявка отклонена"
        body = "Ваша заявка была отклонена. Посмотрите причину в приложении."
        background_tasks.add_task(send_notification_with_fallback, user.fcmToken, title, body)

    return {"message": "Заявка отклонена успешно"}

@app.get("/test_firebase")
async def test_firebase():
    try:
        # Пробуем отправить тестовое уведомление
        message = messaging.Message(
            token="тестовый_токен",
            notification=messaging.Notification(title="Test", body="Test")
        )
        messaging.send(message)
        return {"status": "Firebase инициализирован корректно"}
    except Exception as e:
        return {"error": str(e)}

logger = logging.getLogger(__name__)

async def send_notification_with_fallback(fcm_token: str, title: str, body: str) -> bool:
    # Сначала пробуем через Firebase Admin
    if send_notification_to_user(fcm_token, title, body):
        return True

    # Если не получилось, пробуем через HTTP API
    return send_push_notification(fcm_token, title, body)

def send_notification_to_user(fcm_token: str, title: str, body: str) -> bool:
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=fcm_token
        )
        messaging.send(message)
        logger.info(f"Notification sent to {fcm_token[:5]}...")
        return True
    except Exception as e:
        logger.error(f"Firebase Admin error: {str(e)}")
        return False

def send_push_notification(token: str, title: str, body: str) -> bool:
    try:
        response = requests.post(
            'https://fcm.googleapis.com/fcm/send',
            headers={
                'Authorization': f'key={os.getenv("FIREBASE_SERVER_KEY")}',
                'Content-Type': 'application/json'
            },
            json={
                'to': token,
                'notification': {'title': title, 'body': body},
                'priority': 'high'
            },
            timeout=5  # Таймаут для запроса
        )
        success = response.status_code == 200
        if not success:
            logger.error(f"FCM HTTP error: {response.status_code} - {response.text}")
        return success
    except Exception as e:
        logger.error(f"FCM HTTP connection error: {str(e)}")
        return False

@app.put("/replace_item/{table_name}")
async def replace_item(table_name: str, request: ReplaceRequest, db: Session = Depends(get_db)):
    print(f"Запрос на замену: таблица={table_name}, старый ID={request.old_id}, новый ID={request.new_id}")

    model = TABLE_MODELS[table_name]  # Берём модель напрямую без проверки

    old_item = db.query(model).filter(model.id == request.old_id).first()
    new_item = db.query(model).filter(model.id == request.new_id).first()

    if table_name == "family_status":
        db.query(User).filter(User.familyStatusId == request.old_id).update(
            {User.familyStatusId: request.new_id}, synchronize_session=False
        )

    elif table_name == "civil_category":
        db.query(UserCivilCategory).filter(UserCivilCategory.civilCategoryId == request.old_id).update(
            {UserCivilCategory.civilCategoryId: request.new_id}, synchronize_session=False
        )

    elif table_name == "disability_category":
        db.query(User).filter(User.disabilityCategoriesId == request.old_id).update(
            {User.disabilityCategoriesId: request.new_id}, synchronize_session=False
        )

    elif table_name == "disease":
        db.query(ExistingDisease).filter(ExistingDisease.diseaseId == request.old_id).update(
            {ExistingDisease.diseaseId: request.new_id}, synchronize_session=False
        )

    elif table_name == "service":
        db.query(ApplicationService).filter(ApplicationService.serviceId == request.old_id).update(
            {ApplicationService.serviceId: request.new_id}, synchronize_session=False
        )

    elif table_name == "application_duration":
        db.query(Application).filter(Application.durationId == request.old_id).update(
            {Application.durationId: request.new_id}, synchronize_session=False
        )
    elif table_name == "rejection_reason":
        db.query(Application).filter(Application.rejectionReasonId == request.old_id).update(
            {Application.rejectionReasonId: request.new_id}, synchronize_session=False
        )

    db.commit()

    # Удаляем старую запись
    db.delete(old_item)
    db.commit()

    print(f"Элемент с ID {request.old_id} заменён на {request.new_id} и удалён")

    return {"message": f"Элемент с ID {request.old_id} заменён на {request.new_id} и удалён"}

@app.delete("/feedbacks/{id}")
def delete_feedback(id: int, db: Session = Depends(get_db)):
    feedback = db.query(Feedback).filter(Feedback.id == id).first()
    if feedback == None:
        return JSONResponse(status_code=404, content={ "message": "Отзыв не найден"})

    db.delete(feedback)
    db.commit()
    return feedback

@app.delete("/{table_name}/{item_id}")
async def delete_item(table_name: str, item_id: int, db: Session = Depends(get_db)):
    print(f"Получен запрос на удаление: таблица={table_name}, ID={item_id}")
    model = TABLE_MODELS.get(table_name)

    if not model:
        raise HTTPException(status_code=400, detail="Неверное имя таблицы")

    item = db.query(model).filter(model.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Элемент не найден")

    db.delete(item)
    db.commit()

    return {"message": f"Элемент с ID {item_id} из таблицы {table_name} успешно удалён"}

@app.get("/get_items/{table_name}")
async def get_items(table_name: str, db: Session = Depends(get_db)):
    # Проверяем, из какой таблицы нужно получить данные
    if table_name == "civil_category":
        items = db.query(CivilCategory).all()
    elif table_name == "disability_category":
        items = db.query(DisabilityCategorie).all()
    elif table_name == "disease":
        items = db.query(Disease).all()
    elif table_name == "family_status":
        items = db.query(FamilyStatus).all()
    elif table_name == "service":
        items = db.query(Service).all()
    elif table_name == "application_duration":
        items = db.query(ApplicationDuration).all()
    elif table_name == "rejection_reason":
        items = db.query(RejectionReason).all()
    else:
        raise HTTPException(status_code=400, detail="Неверное имя таблицы")

    # Если таблица пуста, возвращаем сообщение
    if not items:
        return {"message": f"Нет данных в таблице {table_name}"}

    # Возвращаем список записей
    return {"data": items}

@app.post("/add_item/{table_name}")
async def add_item(table_name: str, item: ItemRequest, db: Session = Depends(get_db)):
    try:
        if table_name == "civil_category":
            new_item = CivilCategory(name=item.name)
            db.add(new_item)
            db.commit()
            db.refresh(new_item)
            return {"message": "Категория гражданства добавлена", "id": new_item.id}

        elif table_name == "disability_category":
            new_item = DisabilityCategorie(name=item.name)
            db.add(new_item)
            db.commit()
            db.refresh(new_item)
            return {"message": "Категория инвалидности добавлена", "id": new_item.id}

        elif table_name == "disease":
            new_item = Disease(name=item.name)
            db.add(new_item)
            db.commit()
            db.refresh(new_item)
            return {"message": "Заболевание добавлено", "id": new_item.id}

        elif table_name == "family_status":
            new_item = FamilyStatus(name=item.name)
            db.add(new_item)
            db.commit()
            db.refresh(new_item)
            return {"message": "Семейное положение добавлено", "id": new_item.id}

        elif table_name == "service":
            new_item = Service(name=item.name)
            db.add(new_item)
            db.commit()
            db.refresh(new_item)
            return {"message": "Услуга добавлена", "id": new_item.id}

        elif table_name == "application_duration":
            new_item = ApplicationDuration(name=item.name)
            db.add(new_item)
            db.commit()
            db.refresh(new_item)
            return {"message": "Услуга добавлена", "id": new_item.id}

        elif table_name == "rejection_reason":
            new_item = RejectionReason(name=item.name)
            db.add(new_item)
            db.commit()
            db.refresh(new_item)
            return {"message": "Причина отказа добавлена", "id": new_item.id}

        else:
            raise HTTPException(status_code=400, detail="Неверное имя таблицы")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Ошибка при добавлении элемента: {str(e)}")

@app.post("/staffs/")
async def create_staff(staff: StaffCreate, db: Session = Depends(get_db)):
    new_staff = Staff(
        photo=staff.photo,
        name=staff.name,
        surname=staff.surname,
        patronymic=staff.patronymic,
        birth=staff.birth,
        employmentDay=staff.employmentDay,
        bio=staff.bio,
        isVisible=staff.isVisible,
        averageRating=None  # Всегда устанавливаем NULL
    )

    db.add(new_staff)
    db.commit()
    db.refresh(new_staff)

    return {"message": "Сотрудник успешно добавлен", "staff_id": new_staff.id}

@app.put("/staffs/{staff_id}")
async def update_staff(staff_id: int, staff_data: StaffUpdate, db: Session = Depends(get_db)):
    staff = db.query(Staff).filter(Staff.id == staff_id).first()

    if not staff:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    # Обновляем только разрешённые поля
    staff.photo = staff_data.photo if staff_data.photo is not None else staff.photo
    staff.name = staff_data.name
    staff.surname = staff_data.surname
    staff.patronymic = staff_data.patronymic
    staff.birth = staff_data.birth
    staff.employmentDay = staff_data.employmentDay
    staff.bio = staff_data.bio
    staff.isVisible = staff_data.isVisible

    db.commit()
    db.refresh(staff)

    return {"message": "Данные сотрудника успешно обновлены", "staff_id": staff.id}

@app.put("/replace_and_delete_staff/")
async def replace_and_delete_staff(request: ReplaceRequest, db: Session = Depends(get_db)):
    old_staff = db.query(Staff).filter(Staff.id == request.old_id).first()
    new_staff = db.query(Staff).filter(Staff.id == request.new_id).first()

    if not old_staff:
        raise HTTPException(status_code=404, detail="Удаляемый сотрудник не найден")
    if not new_staff:
        raise HTTPException(status_code=404, detail="Новый сотрудник не найден")

    # Обновляем заявки, где был старый сотрудник
    updated_count = (
        db.query(Application)
        .filter(Application.staffId == request.old_id)
        .update({Application.staffId: request.new_id}, synchronize_session=False)
    )

    db.commit()

    # Удаляем старого сотрудника
    db.delete(old_staff)
    db.commit()

    return {
        "message": f"Сотрудник ID {request.old_id} заменён на {request.new_id} и удалён",
        "updated_applications": updated_count
    }

@app.get("/feedbacks")
async def get_all_feedbacks(db: Session = Depends(get_db)):
    feedbacks = (
        db.query(Feedback, User, Staff)
        .join(User, Feedback.userId == User.id)
        .join(Staff, Feedback.staffId == Staff.id)
        .filter(or_(Feedback.isVisible == True, Feedback.isVisible == None))
        .all()
    )

    result = []
    for feedback, user, staff in feedbacks:
        result.append({
            "commentId": feedback.id,
            "user": {
                "id": user.id,
                "photo": user.photo,
                "name": user.name,
                "surname": user.surname,
                "patronymic": user.patronymic
            },
            "comment": feedback.comment,
            "rating": feedback.rating,
            "isVisible": feedback.isVisible,
            "staff": {
                "id": staff.id if staff else None,
                "name": staff.name if staff else None,
                "surname": staff.surname if staff else None,
                "patronymic": staff.patronymic if staff else None
            }
        })

    return result

@app.put("/feedbacks/{feedback_id}")
async def update_feedback_visibility(
    feedback_id: int = Path(..., description="ID комментария"),
    visibility: FeedbackVisibilityUpdate = None,
    db: Session = Depends(get_db)
):
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()

    if not feedback:
        raise HTTPException(status_code=404, detail="Комментарий не найден")

    feedback.isVisible = visibility.isVisible
    db.commit()

    return {"message": "Статус видимости обновлён", "id": feedback.id, "isVisible": feedback.isVisible}

@app.get("/applications")
async def get_all_applications(db: Session = Depends(get_db)):
    # Сначала получаем все заявки (уникальные)
    applications = (
        db.query(Application, User, Staff, ApplicationDuration)
        .join(User, Application.userId == User.id)
        .join(ApplicationDuration, Application.durationId == ApplicationDuration.id)
        .outerjoin(Staff, Application.staffId == Staff.id)
        .join(DisabilityCategorie, User.disabilityCategoriesId == DisabilityCategorie.id)
        .join(FamilyStatus, User.familyStatusId == FamilyStatus.id)
        .filter(Application.dateStart == date(1970, 1, 1), Application.dateEnd == date(1970, 1, 1))
        .filter(Application.isRejected == False)
        .all()
    )

    result = []
    for app, user, staff, applicationDuration in applications:
        # Отдельно получаем все болезни для текущего пользователя
        diseases_query = (
            db.query(Disease.name)
            .join(ExistingDisease, ExistingDisease.diseaseId == Disease.id)
            .filter(ExistingDisease.userId == user.id)
            .all()
        )
        diseases = [d[0] for d in diseases_query]

        userCivilCategories_query = (
            db.query(CivilCategory.name)
            .join(UserCivilCategory, UserCivilCategory.civilCategoryId == CivilCategory.id)
            .filter(UserCivilCategory.userId == user.id)
            .all()
        )
        userCivilCategories = [d[0] for d in userCivilCategories_query]

        applicationServices_query = (
            db.query(Service.name)
            .join(ApplicationService, ApplicationService.serviceId == Service.id)
            .filter(ApplicationService.applicationId == app.id)
            .all()
        )
        applicationServices = [d[0] for d in applicationServices_query]

        result.append({
            "applicationId": app.id,
            "user": {
                "id": user.id,
                "name": user.name,
                "surname": user.surname,
                "patronymic": user.patronymic,
                "phoneNumber": user.phoneNumber,
                "birthday": user.birthday.strftime("%Y-%m-%d"),
                "passportSeries": user.passportSeries,
                "passportNumber": user.passportNumber,
                "whoGave": user.whoGave,
                "whenGet": user.whenGet.strftime("%Y-%m-%d"),
                "departmentCode": user.departmentCode,
                "photo": user.photo,
                "address": user.address,
                "disabilityCategory": user.disabilityCategorie.name if user.disabilityCategorie else None,
                "pensionAmount": user.pensionAmount,
                "familyStatus": user.familyStatus.name if user.familyStatus else None
            },
            "applicationServices": applicationServices,
            "applicationDuration": applicationDuration.name,
            "userCivilCategories": userCivilCategories,
            "existingDiseases": diseases,
            "dateStart": app.dateStart.strftime("%Y-%m-%d"),
            "dateEnd": app.dateEnd.strftime("%Y-%m-%d"),
            "isHaveReabilitation": "Да" if app.isHaveReabilitation else "Нет",
            "staff": {
                "id": staff.id if staff else None,
                "name": staff.name if staff else None,
                "surname": staff.surname if staff else None,
                "patronymic": staff.patronymic if staff else None
            } if staff else None
        })

    return result

@app.get("/active-applications")
async def get_active_applications(db: Session = Depends(get_db)):
    today = date.today()

    # Получаем уникальные заявки, соответствующие текущей дате
    applications = (
        db.query(Application, User, Staff, ApplicationDuration)
        .join(User, Application.userId == User.id)
        .join(ApplicationDuration, Application.durationId == ApplicationDuration.id)
        .outerjoin(Staff, Application.staffId == Staff.id)
        .join(DisabilityCategorie, User.disabilityCategoriesId == DisabilityCategorie.id)
        .join(FamilyStatus, User.familyStatusId == FamilyStatus.id)
        .filter(Application.dateStart <= today, Application.dateEnd >= today)  # Фильтрация по текущей дате
        .distinct(Application.id)  # Обеспечиваем уникальность заявок
        .filter(Application.isRejected == False)
        .all()
    )

    result = []
    for app, user, staff, applicationDuration in applications:
        # Получаем все заболевания для пользователя, чтобы избежать дублирования
        diseases_query = (
            db.query(Disease.name)
            .join(ExistingDisease, ExistingDisease.diseaseId == Disease.id)
            .filter(ExistingDisease.userId == user.id)
            .all()
        )
        diseases = [d[0] for d in diseases_query]

        userCivilCategories_query = (
            db.query(CivilCategory.name)
            .join(UserCivilCategory, UserCivilCategory.civilCategoryId == CivilCategory.id)
            .filter(UserCivilCategory.userId == user.id)
            .all()
        )
        userCivilCategories = [d[0] for d in userCivilCategories_query]

        applicationServices_query = (
            db.query(Service.name)
            .join(ApplicationService, ApplicationService.serviceId == Service.id)
            .filter(ApplicationService.applicationId == app.id)
            .all()
        )
        applicationServices = [d[0] for d in applicationServices_query]

        result.append({
            "applicationId": app.id,
            "user": {
                "id": user.id,
                "name": user.name,
                "surname": user.surname,
                "patronymic": user.patronymic,
                "phoneNumber": user.phoneNumber,
                "birthday": user.birthday.strftime("%Y-%m-%d"),
                "passportSeries": user.passportSeries,
                "passportNumber": user.passportNumber,
                "whoGave": user.whoGave,
                "whenGet": user.whenGet.strftime("%Y-%m-%d"),
                "departmentCode": user.departmentCode,
                "photo": user.photo,
                "address": user.address,
                "disabilityCategory": user.disabilityCategorie.name if user.disabilityCategorie else None,
                "pensionAmount": user.pensionAmount,
                "familyStatus": user.familyStatus.name if user.familyStatus else None
            },
            "applicationServices": applicationServices,
            "applicationDuration": applicationDuration.name,
            "userCivilCategories": userCivilCategories,
            "existingDiseases": diseases,
            "dateStart": app.dateStart.strftime("%Y-%m-%d"),
            "dateEnd": app.dateEnd.strftime("%Y-%m-%d"),
            "isHaveReabilitation": "Да" if app.isHaveReabilitation else "Нет",
            "staff": {
                "id": staff.id if staff else None,
                "name": staff.name if staff else None,
                "surname": staff.surname if staff else None,
                "patronymic": staff.patronymic if staff else None
            } if staff else None  # Проверка на наличие сотрудника
        })

    return result

@app.get("/applications/search")
async def search_applications(
    search: str = Query(..., description="Поиск по всем полям"),
    db: Session = Depends(get_db)
):
    today = date.today()

    query = (
        db.query(Application)
        .join(User, Application.userId == User.id)
        .join(ApplicationService, ApplicationService.applicationId == Application.id)
        .join(Service, ApplicationService.serviceId == Service.id)
        .join(ApplicationDuration, Application.durationId == ApplicationDuration.id)
        .outerjoin(ExistingDisease, ExistingDisease.userId == User.id)
        .outerjoin(Disease, ExistingDisease.diseaseId == Disease.id)
        .outerjoin(Staff, Application.staffId == Staff.id)
        .join(UserCivilCategory, UserCivilCategory.userId == User.id)
        .join(CivilCategory, UserCivilCategory.civilCategoryId == CivilCategory.id)
        .join(DisabilityCategorie, User.disabilityCategoriesId == DisabilityCategorie.id)
        .join(FamilyStatus, User.familyStatusId == FamilyStatus.id)
        .filter(
            or_(
                cast(User.id, String).ilike(f"%{search}%"),
                User.name.ilike(f"%{search}%"),
                User.surname.ilike(f"%{search}%"),
                User.patronymic.ilike(f"%{search}%"),
                User.phoneNumber.ilike(f"%{search}%"),
                cast(User.birthday, String).ilike(f"%{search}%"),
                User.passportSeries.ilike(f"%{search}%"),
                User.passportNumber.ilike(f"%{search}%"),
                User.whoGave.ilike(f"%{search}%"),
                cast(User.whenGet, String).ilike(f"%{search}%"),
                cast(User.departmentCode, String).ilike(f"%{search}%"),
                User.address.ilike(f"%{search}%"),
                DisabilityCategorie.name.ilike(f"%{search}%"),
                CivilCategory.name.ilike(f"%{search}%"),
                cast(User.pensionAmount, String).ilike(f"%{search}%"),
                FamilyStatus.name.ilike(f"%{search}%"),
                Service.name.ilike(f"%{search}%"),
                ApplicationDuration.name.ilike(f"%{search}%"),
                Disease.name.ilike(f"%{search}%"),
                Staff.name.ilike(f"%{search}%"),
                Staff.surname.ilike(f"%{search}%"),
                Staff.patronymic.ilike(f"%{search}%"),
                cast(Application.dateStart, String).ilike(f"%{search}%"),
                cast(Application.dateEnd, String).ilike(f"%{search}%"),
                cast(Application.isHaveReabilitation, String).ilike(f"%{search}%")
            ),
            Application.dateStart <= today,
            Application.dateEnd >= today
        )
    )

    applications = query.all()
    result = []
    for app in applications:
        user = app.user
        applicationDuration = app.duration
        staff = app.staff

        diseases = [d.disease.name for d in user.existingDiseases if d.disease] if user.existingDiseases else []

        civilCategories = [d.civilCategory.name for d in user.userCivilCategories if d.civilCategory] if user.userCivilCategories else []

        services = [d.service.name for d in app.applicationServices if d.service] if app.applicationServices else []

        result.append({
            "applicationId": app.id,
            "user": {
                "id": user.id,
                "name": user.name,
                "surname": user.surname,
                "patronymic": user.patronymic,
                "phoneNumber": user.phoneNumber,
                "birthday": user.birthday.strftime("%Y-%m-%d"),
                "passportSeries": user.passportSeries,
                "passportNumber": user.passportNumber,
                "whoGave": user.whoGave,
                "whenGet": user.whenGet.strftime("%Y-%m-%d"),
                "departmentCode": user.departmentCode,
                "photo": user.photo,
                "address": user.address,
                "disabilityCategory": user.disabilityCategorie.name if user.disabilityCategorie else None,
                "pensionAmount": user.pensionAmount,
                "familyStatus": user.familyStatus.name if user.familyStatus else None
            },
            "applicationServices": services,
            "applicationDuration": applicationDuration.name if applicationDuration else None,
            "userCivilCategories": civilCategories,
            "existingDiseases": diseases,
            "dateStart": app.dateStart.strftime("%Y-%m-%d"),
            "dateEnd": app.dateEnd.strftime("%Y-%m-%d"),
            "isHaveReabilitation": "Да" if app.isHaveReabilitation else "Нет",
            "staff": {
                "id": staff.id if staff else None,
                "name": staff.name if staff else None,
                "surname": staff.surname if staff else None,
                "patronymic": staff.patronymic if staff else None
            } if staff else None
        })

    return result

@app.put("/applications/{application_id}")
async def update_application(
        application_id: int,
        update_data: ApplicationUpdateSchema,
        db: Session = Depends(get_db)
):
    application = db.query(Application).get(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    old_values = {
        'start': application.dateStart,
        'end': application.dateEnd,
        'staff': application.staffId
    }

    # Применяем изменения
    application.dateStart = update_data.dateStart
    application.dateEnd = update_data.dateEnd
    application.staffId = update_data.staffId if update_data.staffId is not None else application.staffId

    db.commit()
    db.refresh(application)

    # Проверяем изменения
    dates_changed = (old_values['start'] != application.dateStart or
                     old_values['end'] != application.dateEnd)
    staff_changed = (old_values['staff'] != application.staffId)
    today = datetime.now().date()
    became_active = (dates_changed and
                     application.dateStart <= today <= application.dateEnd and
                     not (old_values['start'] <= today <= old_values['end']))

    # Отправляем уведомление только когда заявка становится активной
    if became_active:
        user = db.query(User).get(application.userId)
        if user and user.fcmToken:
            await send_notification_with_fallback(
                fcm_token=user.fcmToken,
                title="Статус заявки",
                body="Ваша заявка была принята!"
            )

    return {
        "message": "Заявка успешно обновлена",
        "changes": {
            "dates_changed": dates_changed,
            "staff_changed": staff_changed,
            "became_active": became_active
        }
    }

@app.get("/user/{phone_number}/{password}", response_model=user_response)
def get_user_by_passport(phone_number: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phoneNumber == phone_number, User.password == password).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/users")
async def get_all_users():
    with Session(bind=engine, autoflush=False) as db:
        users = db.query(User).all()
        return users

@app.get("/civil_categories")
async def get_all_civil_categories():
    with Session(bind=engine, autoflush=False) as db:
        civil_category = db.query(CivilCategory).all()
        return civil_category

@app.get("/application_duration")
async def get_all_application_duration():
    with Session(bind=engine, autoflush=False) as db:
        application_duration = db.query(ApplicationDuration).all()
        return application_duration

@app.get("/disability_categories")
async def get_all_disability_categories():
    with Session(bind=engine, autoflush=False) as db:
        disability_categorie = db.query(DisabilityCategorie).all()
        return disability_categorie

@app.get("/services")
async def get_all_services():
    with Session(bind=engine, autoflush=False) as db:
        necessary_service = db.query(Service).all()
        return necessary_service

@app.get("/marital_statuses")
async def get_all_marital_statuss():
    with Session(bind=engine, autoflush=False) as db:
        marital_status = db.query(FamilyStatus).all()
        return marital_status

@app.get("/diseases")
async def get_all_diseases():
    with Session(bind=engine, autoflush=False) as db:
        disease = db.query(Disease).all()
        return disease

@app.get("/staffs")
async def get_all_staffs():
    with Session(bind=engine, autoflush=False) as db:
        staff = db.query(Staff).all()
        return staff

@app.get("/staffs/hidden")
async def get_hidden_staffs():
    with Session(bind=engine, autoflush=False) as db:
        hidden_staff = db.query(Staff).filter(Staff.isVisible == False).all()
        return hidden_staff

@app.get("/existing_diseases")
async def get_all_existing_diseases():
    with Session(bind=engine, autoflush=False) as db:
        existing_diseases = db.query(ExistingDisease).all()
        return existing_diseases

@app.get("/feedback")
async def get_all_feedbacks():
    with Session(bind=engine, autoflush=False) as db:
        feedbacks = db.query(Feedback).all()
        return feedbacks

@app.get("/rejection_reason")
async def get_all_rejection_reasons():
    with Session(bind=engine, autoflush=False) as db:
        rejection_reasons = db.query(RejectionReason).all()
        return rejection_reasons

@app.get("/feedbacks/{staff_id}", response_model=List[FeedbackResponse])
async def get_feedback_for_staff(staff_id: int):
    with Session(bind=engine, autoflush=False) as db:
        feedbacks = (
            db.query(Feedback.comment, User.surname, User.name, User.patronymic, User.photo)
            .join(User, Feedback.userId == User.id)
            .filter(Feedback.staffId == staff_id)
            .filter(Feedback.isVisible == False)
            .all()
        )

        if not feedbacks:
            raise HTTPException(status_code=404, detail="No hidden feedback found for the specified staff member")

        feedback_list = [
            {
                "comment": feedback.comment,
                "surname": feedback.surname,
                "name": feedback.name,
                "patronymic": feedback.patronymic,
                "photo": feedback.photo
            }
            for feedback in feedbacks
        ]

        return feedback_list

@app.get("/CivilCategorys/{id}")
def get_civil(id: int, db: Session = Depends(get_db)):
    civils = db.query(CivilCategory).filter(CivilCategory.id == id).first()
    return civils


@app.get("/applications/{user_id}")
def get_active_user_applications(user_id: int, db: Session = Depends(get_db)):
    current_date = dt.date.today()  # Текущая дата
    # Получаем только актуальные заявки, где dateEnd >= текущей дате
    applications = db.query(Application).filter(
        Application.userId == user_id,
        Application.dateEnd >= current_date
    ).all()

    # Возвращаем даты, userId и staffId
    return [
        {
            "dateStart": app.dateStart,
            "dateEnd": app.dateEnd,
            "userId": app.userId,
            "staffId": app.staffId
        }
        for app in applications
    ]

@app.get("/applications/any/{user_id}")
def get_any_user_applications(user_id: int, db: Session = Depends(get_db)):
    # Получаем все заявки пользователя по user_id
    applications = db.query(Application).filter(
        Application.userId == user_id
    ).all()

    # Возвращаем список заявок
    return [
        {
            "dateStart": app.dateStart,
            "dateEnd": app.dateEnd,
            "userId": app.userId,
            "staffId": app.staffId
        }
        for app in applications
    ]


@app.post('/add_user', response_model=user_response)
def add_user(user: user_response, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(
        (User.passportSeries == user.passportSeries),
        (User.passportNumber == user.passportNumber)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Пользователь с такими паспортными данными уже существует"
        )

    existing_phone = db.query(User).filter(
        User.phoneNumber == user.phoneNumber
    ).first()

    if existing_phone:
        raise HTTPException(
            status_code=400,
            detail="Этот номер телефона уже зарегистрирован"
        )

    # Проверяем, передано ли фото
    if user.photo:
        try:
            # Декодируем строку Base64 в массив байтов
            photo = base64.b64decode(user.photo)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка декодирования фото: {e}")
    else:
        # Если фото отсутствует, сохраняем пустую бинарную строку
        photo = b""

    # Создаем нового пользователя
    new_user = User(
        name=user.name,
        surname=user.surname,
        patronymic=user.patronymic,
        phoneNumber=user.phoneNumber,
        birthday=user.birthday,
        passportSeries=user.passportSeries,
        passportNumber=user.passportNumber,
        whoGave=user.whoGave,
        whenGet=user.whenGet,
        departmentCode=user.departmentCode,
        photo=photo,
        address=user.address,
        disabilityCategoriesId=user.disabilityCategoriesId,
        pensionAmount=user.pensionAmount,
        familyStatusId=user.familyStatusId,
        password=user.password,
        fcmToken=user.fcmToken
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения в базе данных: {e}")

    return new_user

@app.post('/add_application', response_model=application_response)
def add_application(application: application_response, db: Session = Depends(get_db)):
    # Создаем нового пользователя
    new_application = Application(
        userId=application.userId,
        isHaveReabilitation=application.isHaveReabilitation,
        dateStart=application.dateStart,
        dateEnd=application.dateEnd,
        staffId=application.staffId,
        durationId=application.durationId,
        isRejected=application.isRejected,
        rejectedDate=application.rejectedDate,
        rejectionReasonId=application.rejectionReasonId
    )

    try:
        db.add(new_application)
        db.commit()
        db.refresh(new_application)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения в базе данных: {e}")

    return new_application

@app.post("/feedbacks")
async def add_feedback(feedback: FeedbackRequest, db: Session = Depends(get_db)):
    # Проверка наличия пользователя и сотрудника
    user = db.query(User).filter(User.id == feedback.userId).first()
    staff = db.query(Staff).filter(Staff.id == feedback.staffId).first()

    if not user or not staff:
        raise HTTPException(status_code=404, detail="User or Staff not found")

    # Создание нового отзыва с isVisible = True
    new_feedback = Feedback(
        userId=feedback.userId,
        staffId=feedback.staffId,
        comment=feedback.comment,
        rating=feedback.rating,
        isVisible=True
    )

    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)

    return {"message": "Отзыв успешно добавлен", "feedback_id": new_feedback.id}

@app.post("/add_application_services")
async def add_application_services(request: ServiceRequest, db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == request.applicationId).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    db.query(ApplicationService).filter(ApplicationService.applicationId == request.applicationId).delete()

    for service_id in request.serviceIds:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            db.rollback()
            raise HTTPException(status_code=404, detail=f"Service with id {service_id} not found")

        new_relation = ApplicationService(
            applicationId=request.applicationId,
            serviceId=service_id
        )
        db.add(new_relation)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error saving to database: {e}")

    return {"message": "Services successfully updated for application"}

@app.post("/add_civil_category")
async def add_civil_category(civil_category_request: CivilCategoryRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == civil_category_request.userId).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Удаляем старые записи
    db.query(UserCivilCategory).filter(UserCivilCategory.userId == civil_category_request.userId).delete()

    # Добавляем новые записи
    for civil_category_id in civil_category_request.civilCategoryIds:
        civil_category = db.query(CivilCategory).filter(CivilCategory.id == civil_category_id).first()
        if not civil_category:
            db.rollback()
            raise HTTPException(status_code=404, detail=f"Civil category with id {civil_category_id} not found")

        new_relation = UserCivilCategory(
            userId=civil_category_request.userId,
            civilCategoryId=civil_category_id
        )
        db.add(new_relation)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error saving to database: {e}")

    return {"message": "Civil categories successfully updated"}

@app.post("/add_disease")
async def add_disease(disease_request: DiseaseRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == disease_request.userId).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Удаляем старые записи
    db.query(ExistingDisease).filter(ExistingDisease.userId == disease_request.userId).delete()

    # Добавляем новые записи
    for disease_id in disease_request.diseaseIds:
        disease = db.query(Disease).filter(Disease.id == disease_id).first()
        if not disease:
            db.rollback()
            raise HTTPException(status_code=404, detail=f"Disease with id {disease_id} not found")

        new_disease = ExistingDisease(
            userId=disease_request.userId,
            diseaseId=disease_id
        )
        db.add(new_disease)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error saving to database: {e}")

    return {"message": "Diseases successfully updated"}

@app.put('/update_user/{user_id}', response_model=user_response)
def update_user(user_id: int, user: user_response, db: Session = Depends(get_db)):
    # Получаем пользователя из базы данных
    existing_user = db.query(User).filter(User.id == user_id).first()

    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Обновляем только нужные поля
    if user.name is not None:
        existing_user.name = user.name
    if user.surname is not None:
        existing_user.surname = user.surname
    if user.patronymic is not None:
        existing_user.patronymic = user.patronymic
    if user.phoneNumber is not None:
        existing_user.phoneNumber = user.phoneNumber
    if user.birthday is not None:
        existing_user.birthday = user.birthday
    if user.passportSeries is not None:
        existing_user.passportSeries = user.passportSeries
    if user.passportNumber is not None:
        existing_user.passportNumber = user.passportNumber
    if user.whoGave is not None:
        existing_user.whoGave = user.whoGave
    if user.whenGet is not None:
        existing_user.whenGet = user.whenGet
    if user.departmentCode is not None:
        existing_user.departmentCode = user.departmentCode
    if user.address is not None:
        existing_user.address = user.address
    if user.disabilityCategoriesId is not None:
        existing_user.disabilityCategoriesId = user.disabilityCategoriesId
    if user.pensionAmount is not None:
        existing_user.pensionAmount = user.pensionAmount
    if user.familyStatusId is not None:
        existing_user.familyStatusId = user.familyStatusId
    if user.password is not None:
        existing_user.password = user.password
    if user.fcmToken is not None:
        existing_user.fcmToken = user.fcmToken

    # Обработка поля photo
    if user.photo is not None:
        try:
            # Декодируем строку Base64 в массив байтов
            existing_user.photo = base64.b64decode(user.photo)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка декодирования фото: {e}")

    try:
        db.commit()
        db.refresh(existing_user)
    except Exception as e:
        db.rollback()  # Откат транзакции в случае ошибки
        raise HTTPException(status_code=500, detail=f"Ошибка обновления данных в базе: {e}")

    return existing_user

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

# --host 100.70.255.173


