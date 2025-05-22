from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, Text, LargeBinary, create_engine, Float
from sqlalchemy.orm import relationship, DeclarativeBase
import psycopg2

class Base(DeclarativeBase):
    pass

class Application(Base):
    __tablename__ = 'Application'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    userId = Column(Integer, ForeignKey('User.id'), nullable=False)
    isHaveReabilitation = Column(Boolean, nullable=False)
    dateStart = Column(Date, nullable=False)
    dateEnd = Column(Date, nullable=False)
    durationId = Column(Integer, ForeignKey('ApplicationDuration.id'), nullable=False)
    staffId = Column(Integer, ForeignKey('Staff.id'), nullable=True)
    isRejected = Column(Boolean, default=False, nullable=False)
    rejectedDate = Column(Date, nullable=True)
    rejectionReasonId = Column(Integer, ForeignKey('RejectionReason.id'), nullable=True)

    user = relationship("User", back_populates="applications")
    applicationServices = relationship("ApplicationService", back_populates="application")
    staff = relationship("Staff", back_populates="applications")
    duration = relationship("ApplicationDuration", back_populates="applications")
    rejectionReason = relationship("RejectionReason", back_populates="applications")

class RejectionReason(Base):
    __tablename__ = 'RejectionReason'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(300), nullable=False)

    applications = relationship("Application", back_populates="rejectionReason")

class ApplicationService(Base):
    __tablename__ = "ApplicationService"
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    applicationId = Column(Integer, ForeignKey("Application.id"), nullable=False)
    serviceId = Column(Integer, ForeignKey("Service.id"), nullable=False)

    application = relationship("Application", back_populates="applicationServices")
    service = relationship("Service", back_populates="applicationServices")

class Service(Base):
    __tablename__ = 'Service'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(200), nullable=False)

    applicationServices = relationship("ApplicationService", back_populates="service")

class ApplicationDuration(Base):
    __tablename__ = 'ApplicationDuration'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(50), nullable=False)

    applications = relationship("Application", back_populates="duration")

class DisabilityCategorie(Base):
    __tablename__ = 'DisabilityCategorie'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(100), nullable=False)

    users = relationship("User", back_populates="disabilityCategorie")

class Disease(Base):
    __tablename__ = 'Disease'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(80), nullable=False)

    existingDiseases = relationship("ExistingDisease", back_populates="disease")

class ExistingDisease(Base):
    __tablename__ = 'ExistingDisease'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    userId = Column(Integer, ForeignKey('User.id'), nullable=False)
    diseaseId = Column(Integer, ForeignKey('Disease.id'), nullable=False)

    user = relationship("User", back_populates="existingDiseases")
    disease = relationship("Disease", back_populates="existingDiseases")

class FamilyStatus(Base):
    __tablename__ = 'FamilyStatus'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(80), nullable=False)

    users = relationship("User", back_populates="familyStatus")

class Feedback(Base):
    __tablename__ = 'Feedback'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    userId = Column(Integer, ForeignKey('User.id'), nullable=False)
    staffId = Column(Integer, ForeignKey('Staff.id'), nullable=False)
    comment = Column(Text, nullable=False)
    rating = Column(Integer, nullable=False)
    isVisible = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="feedbacks")
    staff = relationship("Staff", back_populates="feedbacks")

class Staff(Base):
    __tablename__ = 'Staff'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    photo = Column(LargeBinary, nullable=True)
    name = Column(String(80), nullable=False)
    surname = Column(String(80), nullable=False)
    patronymic = Column(String(80), nullable=True)
    birth = Column(Date, nullable=False)
    employmentDay = Column(Date, nullable=False)
    bio = Column(Text, nullable=False)
    isVisible = Column(Boolean, default=True, nullable=False)
    averageRating = Column(Float, nullable=True)

    applications = relationship("Application", back_populates="staff")
    feedbacks = relationship("Feedback", back_populates="staff")

class CivilCategory(Base):
    __tablename__ = 'CivilCategory'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(200), nullable=False)

    userCivilCategories = relationship("UserCivilCategory", back_populates="civilCategory")

class UserCivilCategory(Base):
    __tablename__ = "UserCivilCategory"
    id = Column(Integer, primary_key=True, autoincrement=True)
    userId = Column(Integer, ForeignKey("User.id"), nullable=False)
    civilCategoryId = Column(Integer, ForeignKey("CivilCategory.id"), nullable=False)

    user = relationship("User", back_populates="userCivilCategories")
    civilCategory = relationship("CivilCategory", back_populates="userCivilCategories")

class User(Base):
    __tablename__ = 'User'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(80), nullable=False)
    surname = Column(String(80), nullable=False)
    patronymic = Column(String(80), nullable=True)
    phoneNumber = Column(String(12), nullable=False)
    photo = Column(LargeBinary, nullable=True)
    birthday = Column(Date, nullable=False)
    passportSeries = Column(String(4), nullable=False)
    passportNumber = Column(String(6), nullable=False)
    whoGave = Column(String(80), nullable=False)
    whenGet = Column(Date, nullable=False)
    departmentCode = Column(Integer, nullable=False)
    address = Column(String(200), nullable=True)
    disabilityCategoriesId = Column(Integer, ForeignKey('DisabilityCategorie.id'), nullable=True)
    pensionAmount = Column(Integer, nullable=True)
    familyStatusId = Column(Integer, ForeignKey('FamilyStatus.id'), nullable=True)
    password = Column(String(30), nullable=False)
    fcmToken = Column(String, nullable=True)

    applications = relationship("Application", back_populates="user")
    existingDiseases = relationship("ExistingDisease", back_populates="user")
    feedbacks = relationship("Feedback", back_populates="user")
    userCivilCategories = relationship("UserCivilCategory", back_populates="user")
    disabilityCategorie = relationship("DisabilityCategorie", back_populates="users")
    familyStatus = relationship("FamilyStatus", back_populates="users")

engine = create_engine("postgresql://danil:iHnNUjL7sDmS3Gt3a0VLoW2tBPNeksVP@dpg-d0nj3vpr0fns7393qlm0-a.oregon-postgres.render.com/socialcompass_p4w0", echo=True)

Base.metadata.create_all(engine)