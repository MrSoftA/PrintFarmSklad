from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///farm_erp.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Part(Base):
    __tablename__ = "parts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)  
    material = Column(String, default="PETG (Черный)")
    items_per_bed = Column(Integer, default=30)     
    weight_per_item_g = Column(Float, default=2.0)  
    print_time_mins = Column(Integer, default=300)  
    image_path = Column(String, nullable=True)

class MaterialStock(Base):
    __tablename__ = "material_stock"
    id = Column(Integer, primary_key=True, index=True)
    material_name = Column(String, unique=True) 
    total_weight_g = Column(Float, default=0.0) 

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    customer = Column(String, index=True)           
    part_id = Column(Integer, ForeignKey("parts.id"))
    target_quantity = Column(Integer)               
    completed_quantity = Column(Integer, default=0) 
    deadline = Column(DateTime, nullable=True)      
    status = Column(String, default="В процессе")   
    part = relationship("Part")

class PrintSession(Base):
    __tablename__ = "print_sessions"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    beds_started = Column(Integer)                  
    items_per_bed_actual = Column(Integer)          
    start_time = Column(DateTime, default=datetime.now)
    expected_end_time = Column(DateTime)            
    status = Column(String, default="Печатается")   
    order = relationship("Order")

class FinishedGoods(Base):
    __tablename__ = "finished_goods"
    id = Column(Integer, primary_key=True, index=True)
    part_id = Column(Integer, ForeignKey("parts.id"))
    location = Column(String, default="Главный склад") 
    quantity = Column(Integer, default=0)
    part = relationship("Part")

class HistoryLog(Base):
    __tablename__ = "history_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now)
    action_type = Column(String)  
    details = Column(String)      

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

