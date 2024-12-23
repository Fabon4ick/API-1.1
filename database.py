from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, Text, LargeBinary, create_engine, Float
from sqlalchemy.orm import relationship, DeclarativeBase
import psycopg2

class Base(DeclarativeBase):
    pass

class Application(Base):
    __tablename__ = 'Application'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    userId = Column(Integer, ForeignKey('User.id'), nullable=False)
    requiredServicesId = Column(Integer, ForeignKey('Service.id'), nullable=False)
    isHaveReabilitation = Column(Boolean, nullable=False)
    dateStart = Column(Date, nullable=False)
    dateEnd = Column(Date, nullable=False)
    staffId = Column(Integer, ForeignKey('Staff.id'), nullable=False)

    user = relationship("User", back_populates="applications")
    service = relationship("Service", back_populates="applications")
    staff = relationship("Staff", back_populates="applications")

class CivilCategory(Base):
    __tablename__ = 'CivilCategory'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(200), nullable=False)

    users = relationship("User", back_populates="civilCategory")

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

    user = relationship("User", back_populates="feedbacks")
    staff = relationship("Staff", back_populates="feedbacks")

class Service(Base):
    __tablename__ = 'Service'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(200), nullable=False)

    applications = relationship("Application", back_populates="service")

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
    averageRating = Column(Float, nullable=True)

    applications = relationship("Application", back_populates="staff")
    feedbacks = relationship("Feedback", back_populates="staff")

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
    civilCategoryId = Column(Integer, ForeignKey('CivilCategory.id'), nullable=True)
    pensionAmount = Column(Integer, nullable=True)
    familyStatusId = Column(Integer, ForeignKey('FamilyStatus.id'), nullable=True)

    applications = relationship("Application", back_populates="user")
    existingDiseases = relationship("ExistingDisease", back_populates="user")
    feedbacks = relationship("Feedback", back_populates="user")
    civilCategory = relationship("CivilCategory", back_populates="users")
    disabilityCategorie = relationship("DisabilityCategorie", back_populates="users")
    familyStatus = relationship("FamilyStatus", back_populates="users")

engine = create_engine("postgresql://danil:rPH18yf5m5HijVUZC1wfqzqCzQbA4tj4@dpg-ctk8vdij1k6c73cnb5g0-a:5432/socialcompass", echo=True)

Base.metadata.create_all(engine)