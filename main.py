from database import *
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
import datetime as dt
import base64
import logging
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session, sessionmaker
from datetime import date

app = FastAPI()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TABLE_MODELS = {
    "civil_category": CivilCategory,
    "disability_category": DisabilityCategorie,
    "disease": Disease,
    "family_status": FamilyStatus,
    "service": Service,
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
    photo: str = None
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
    diseaseId: int

    class Config:
        orm_mode = True

class ApplicationUpdateSchema(BaseModel):
    dateStart: dt.date
    dateEnd: dt.date

class StaffUpdate(BaseModel):
    photo: Optional[bytes] = None
    name: str
    surname: str
    patronymic: Optional[str] = None
    birth: datetime
    employmentDay: datetime
    bio: str

class StaffCreate(BaseModel):
    photo: bytes | None = None
    name: str
    surname: str
    patronymic: str | None = None
    birth: date
    employmentDay: date
    bio: str

class ItemRequest(BaseModel):
    name: str

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


@app.delete("/{table_name}/{item_id}")
async def delete_item(table_name: str, item_id: int, db: Session = Depends(get_db)):
    print(f"Получен запрос на удаление: таблица={table_name}, ID={item_id}")  # Логируем запрос
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

    db.commit()
    db.refresh(staff)

    return {"message": "Данные сотрудника успешно обновлены", "staff_id": staff.id}

@app.delete("/staffs/{staff_id}")
async def delete_staff(staff_id: int, db: Session = Depends(get_db)):
    staff = db.query(Staff).filter(Staff.id == staff_id).first()

    if not staff:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    # Устанавливаем staffId в NULL во всех заявках, где есть этот сотрудник
    db.query(Application).filter(Application.staffId == staff_id).update(
        {"staffId": None}, synchronize_session=False
    )
    db.commit()

    # Теперь удаляем сотрудника
    db.delete(staff)
    db.commit()

    return {"message": "Сотрудник успешно удален, заявки обновлены"}

@app.get("/applications")
async def get_all_applications(db: Session = Depends(get_db)):
    applications = (
        db.query(Application, User, ExistingDisease, Disease, Staff, Service)
        .join(User, Application.userId == User.id)
        .join(Service, Application.requiredServicesId == Service.id)
        .outerjoin(ExistingDisease, ExistingDisease.userId == User.id)
        .outerjoin(Disease, ExistingDisease.diseaseId == Disease.id)
        .outerjoin(Staff, Application.staffId == Staff.id)  # Изменено на outerjoin
        .join(CivilCategory, User.civilCategoryId == CivilCategory.id)
        .join(DisabilityCategorie, User.disabilityCategoriesId == DisabilityCategorie.id)
        .join(FamilyStatus, User.familyStatusId == FamilyStatus.id)
        .filter(Application.dateStart == date(1970, 1, 1), Application.dateEnd == date(1970, 1, 1))
        .all()
    )

    result = []
    for app, user, existing_disease, disease, staff, service in applications:
        diseases = []
        if existing_disease:
            diseases.append(disease.name)

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
            "existingDiseases": diseases,
            "dateStart": app.dateStart.strftime("%Y-%m-%d"),
            "dateEnd": app.dateEnd.strftime("%Y-%m-%d"),
            "isHaveReabilitation": "Да" if app.isHaveReabilitation else "Нет",
            "staff": {
                "id": staff.id if staff else None,
                "name": staff.name if staff else None,
                "surname": staff.surname if staff else None,
                "patronymic": staff.patronymic if staff else None
            } if staff else None  # Проверяем, есть ли сотрудник
        })

    return result

@app.get("/active-applications")
async def get_active_applications(db: Session = Depends(get_db)):
    today = date.today()

    applications = (
        db.query(Application, User, ExistingDisease, Disease, Staff, Service)
        .join(User, Application.userId == User.id)
        .join(Service, Application.requiredServicesId == Service.id)
        .outerjoin(ExistingDisease, ExistingDisease.userId == User.id)
        .outerjoin(Disease, ExistingDisease.diseaseId == Disease.id)
        .outerjoin(Staff, Application.staffId == Staff.id)  # Изменено на outerjoin
        .join(CivilCategory, User.civilCategoryId == CivilCategory.id)
        .join(DisabilityCategorie, User.disabilityCategoriesId == DisabilityCategorie.id)
        .join(FamilyStatus, User.familyStatusId == FamilyStatus.id)
        .filter(Application.dateStart <= today, Application.dateEnd >= today)  # Фильтр по текущей дате
        .all()
    )

    result = []
    for app, user, existing_disease, disease, staff, service in applications:
        diseases = []
        if existing_disease:
            diseases.append(disease.name)

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
            "existingDiseases": diseases,
            "dateStart": app.dateStart.strftime("%Y-%m-%d"),
            "dateEnd": app.dateEnd.strftime("%Y-%m-%d"),
            "isHaveReabilitation": "Да" if app.isHaveReabilitation else "Нет",
            "staff": {
                "id": staff.id if staff else None,
                "name": staff.name if staff else None,
                "surname": staff.surname if staff else None,
                "patronymic": staff.patronymic if staff else None
            } if staff else None  # Проверяем, есть ли сотрудник
        })

    return result


@app.delete("/applications/{application_id}")
async def delete_application(application_id: int, db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == application_id).first()

    if not application:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    db.delete(application)
    db.commit()

    return {"message": "Заявка успешно удалена"}

@app.put("/applications/{application_id}")
async def update_application(application_id: int, update_data: ApplicationUpdateSchema, db: Session = Depends(get_db)):
    application = db.query(Application).filter(Application.id == application_id).first()

    if not application:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    application.dateStart = update_data.dateStart
    application.dateEnd = update_data.dateEnd
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
            .all()
        )

        if not feedbacks:
            raise HTTPException(status_code=404, detail="No feedback found for the specified staff member")

        # Преобразование данных в список словарей
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
        staffId=application.staffId
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

    # Создание нового отзыва
    new_feedback = Feedback(
        userId=feedback.userId,  # Использование правильного имени userId
        staffId=feedback.staffId,
        comment=feedback.comment,
        rating=feedback.rating
    )

    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)

    return {"message": "Отзыв успешно добавлен", "feedback_id": new_feedback.id}

@app.post("/add_disease")
async def add_disease(disease_request: DiseaseRequest, db: Session = Depends(get_db)):
    # Проверка наличия пользователя и болезни
    user = db.query(User).filter(User.id == disease_request.userId).first()
    disease = db.query(Disease).filter(Disease.id == disease_request.diseaseId).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not disease:
        raise HTTPException(status_code=404, detail="Disease not found")

    # Создание новой записи о болезни для пользователя
    new_disease = ExistingDisease(
        userId=disease_request.userId,
        diseaseId=disease_request.diseaseId
    )

    try:
        db.add(new_disease)
        db.commit()
        db.refresh(new_disease)
    except Exception as e:
        db.rollback()  # Откат транзакции в случае ошибки
        raise HTTPException(status_code=500, detail=f"Error saving to database: {e}")

    return {"message": "Disease successfully added", "disease_id": new_disease.id}


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

# --host 100.70.255.173


