from database import *
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
import datetime as dt
import base64
import logging
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session, sessionmaker

app = FastAPI()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

@app.get("/user/{passport_series}/{passport_number}", response_model=user_response)
def get_user_by_passport(passport_series: str, passport_number: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.passportSeries == passport_series, User.passportNumber == passport_number).first()
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
        familyStatusId=user.familyStatusId
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

    try:
        db.commit()
        db.refresh(existing_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error saving to database: {e}")

    return existing_user

# --host 100.70.255.173


