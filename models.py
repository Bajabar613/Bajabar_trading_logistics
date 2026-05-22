from sqlalchemy import Column, String, Text
from database import Base

class Contact(Base):

    __tablename__ = "contacts"

    id = Column(String, primary_key=True, index=True)

    name = Column(String)

    email = Column(String)

    phone = Column(String)

    company = Column(String)

    service = Column(String)

    message = Column(Text)

    division = Column(String)

    timestamp = Column(String)