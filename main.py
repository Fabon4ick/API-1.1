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
from fastapi import FastAPI, HTTPException, Depends, Query, Path
from sqlalchemy.orm import Session, sessionmaker, joinedload
from datetime import date

app = FastAPI()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TABLE_MODELS = {
    "civil_category": CivilCategory,
    "disability_category": DisabilityCategorie,
    "disease": Disease,
    "family_status": FamilyStatus,
    "service": Service,
    "application_duration": ApplicationDuration
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
    civilCategoryId: Optional[int] = None
    pensionAmount: Optional[int] = None
    familyStatusId: Optional[int] = None
    password: str

    class Config:
        orm_mode = True

class application_response(BaseModel):
    userId: int
    requiredServicesId: int
    isHaveReabilitation: bool
    dateStart: datetime
    dateEnd: datetime
    staffId: int
    durationId: int

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
        db.query(User).filter(User.civilCategoryId == request.old_id).update(
            {User.civilCategoryId: request.new_id}, synchronize_session=False
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
        db.query(Application).filter(Application.requiredServicesId == request.old_id).update(
            {Application.requiredServicesId: request.new_id}, synchronize_session=False
        )

    elif table_name == "application_duration":
        db.query(Application).filter(Application.durationId == request.old_id).update(
            {Application.durationId: request.new_id}, synchronize_session=False
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

@app.delete("/applications/{id}")
def delete_application(id, db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == id).first()
    if application == None:
        return JSONResponse(status_code=404, content={ "message": "Заявка не найдена"})

    db.delete(application)
    db.commit()
    return application

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
        db.query(Application, User, Staff, Service, ApplicationDuration)
        .join(User, Application.userId == User.id)
        .join(Service, Application.requiredServicesId == Service.id)
        .join(ApplicationDuration, Application.durationId == ApplicationDuration.id)
        .outerjoin(Staff, Application.staffId == Staff.id)
        .join(CivilCategory, User.civilCategoryId == CivilCategory.id)
        .join(DisabilityCategorie, User.disabilityCategoriesId == DisabilityCategorie.id)
        .join(FamilyStatus, User.familyStatusId == FamilyStatus.id)
        .filter(Application.dateStart == date(1970, 1, 1), Application.dateEnd == date(1970, 1, 1))
        .all()
    )

    result = []
    for app, user, staff, service, applicationDuration in applications:
        # Отдельно получаем все болезни для текущего пользователя
        diseases_query = (
            db.query(Disease.name)
            .join(ExistingDisease, ExistingDisease.diseaseId == Disease.id)
            .filter(ExistingDisease.userId == user.id)
            .all()
        )
        diseases = [d[0] for d in diseases_query]

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
                "civilCategory": user.civilCategory.name if user.civilCategory else None,
                "pensionAmount": user.pensionAmount,
                "familyStatus": user.familyStatus.name if user.familyStatus else None
            },
            "service": service.name,
            "applicationDuration": applicationDuration.name,
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
        db.query(Application, User, Staff, Service, ApplicationDuration)
        .join(User, Application.userId == User.id)
        .join(Service, Application.requiredServicesId == Service.id)
        .join(ApplicationDuration, Application.durationId == ApplicationDuration.id)
        .outerjoin(Staff, Application.staffId == Staff.id)
        .join(CivilCategory, User.civilCategoryId == CivilCategory.id)
        .join(DisabilityCategorie, User.disabilityCategoriesId == DisabilityCategorie.id)
        .join(FamilyStatus, User.familyStatusId == FamilyStatus.id)
        .filter(Application.dateStart <= today, Application.dateEnd >= today)  # Фильтрация по текущей дате
        .distinct(Application.id)  # Обеспечиваем уникальность заявок
        .all()
    )

    result = []
    for app, user, staff, service, applicationDuration in applications:
        # Получаем все заболевания для пользователя, чтобы избежать дублирования
        diseases_query = (
            db.query(Disease.name)
            .join(ExistingDisease, ExistingDisease.diseaseId == Disease.id)
            .filter(ExistingDisease.userId == user.id)
            .all()
        )
        diseases = [d[0] for d in diseases_query]

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
                "civilCategory": user.civilCategory.name if user.civilCategory else None,
                "pensionAmount": user.pensionAmount,
                "familyStatus": user.familyStatus.name if user.familyStatus else None
            },
            "service": service.name,
            "applicationDuration": applicationDuration.name,
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
        .join(Service, Application.requiredServicesId == Service.id)
        .join(ApplicationDuration, Application.durationId == ApplicationDuration.id)
        .outerjoin(ExistingDisease, ExistingDisease.userId == User.id)
        .outerjoin(Disease, ExistingDisease.diseaseId == Disease.id)
        .outerjoin(Staff, Application.staffId == Staff.id)
        .join(CivilCategory, User.civilCategoryId == CivilCategory.id)
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
        service = app.service
        applicationDuration = app.duration
        staff = app.staff

        diseases = [d.disease.name for d in user.existingDiseases if d.disease] if user.existingDiseases else []

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
                "civilCategory": user.civilCategory.name if user.civilCategory else None,
                "pensionAmount": user.pensionAmount,
                "familyStatus": user.familyStatus.name if user.familyStatus else None
            },
            "service": service.name if service else None,
            "applicationDuration": applicationDuration.name if applicationDuration else None,
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
async def update_application(application_id: int, update_data: ApplicationUpdateSchema, db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == application_id).first()

    if not application:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    application.dateStart = update_data.dateStart
    application.dateEnd = update_data.dateEnd

    if update_data.staffId is not None:  # Меняем работника, если передан новый ID
        application.staffId = update_data.staffId

    db.commit()
    db.refresh(application)

    return {"message": "Заявка успешно обновлена", "applicationId": application.id}

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

@app.get("/necessary_services")
async def get_all_necessary_services():
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

@app.post('/add_user', response_model=user_response)
def add_user(user: user_response, db: Session = Depends(get_db)):
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
        civilCategoryId=user.civilCategoryId,
        pensionAmount=user.pensionAmount,
        familyStatusId=user.familyStatusId,
        password=user.password
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
        requiredServicesId=application.requiredServicesId,
        isHaveReabilitation=application.isHaveReabilitation,
        dateStart=application.dateStart,
        dateEnd=application.dateEnd,
        staffId=application.staffId,
        durationId=application.durationId
    )

    try:
        db.add(new_application)
        db.commit()
        db.refresh(new_application)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения в базе данных: {e}")

    return new_application

logging.basicConfig(level=logging.DEBUG)

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
    if user.civilCategoryId is not None:
        existing_user.civilCategoryId = user.civilCategoryId
    if user.pensionAmount is not None:
        existing_user.pensionAmount = user.pensionAmount
    if user.familyStatusId is not None:
        existing_user.familyStatusId = user.familyStatusId
    if user.password is not None:
        existing_user.password = user.password

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


