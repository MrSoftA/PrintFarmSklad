import os
import shutil

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional

from database import (
    get_db,
    Part,
    MaterialStock,
    Order,
    PrintSession,
    FinishedGoods,
    HistoryLog,
)

app = FastAPI(title="PrintFarm ERP API", version="1.0.0")

IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class PartCreate(BaseModel):
    name: str
    material: str = "PETG (Черный)"
    items_per_bed: int = 30
    weight_per_item_g: float = 2.0
    print_time_mins: int = 300
    image_path: Optional[str] = None


class PartOut(BaseModel):
    id: int
    name: str
    material: str
    items_per_bed: int
    weight_per_item_g: float
    print_time_mins: int
    image_path: Optional[str]

    class Config:
        from_attributes = True


class MaterialAdd(BaseModel):
    material_name: str
    weight_to_add_g: float


class OrderCreate(BaseModel):
    customer: str
    part_id: int
    target_quantity: int
    deadline: Optional[datetime] = None


class OrderOut(BaseModel):
    id: int
    customer: str
    part_id: int
    target_quantity: int
    completed_quantity: int
    deadline: Optional[datetime]
    status: str

    class Config:
        from_attributes = True


class SessionStart(BaseModel):
    order_id: int
    beds_started: int
    items_per_bed_actual: int


class SessionOut(BaseModel):
    id: int
    order_id: int
    beds_started: int
    items_per_bed_actual: int
    start_time: datetime
    expected_end_time: datetime
    status: str

    class Config:
        from_attributes = True


class CollectBeds(BaseModel):
    successful_beds: int
    failed_beds: int


# ---------------------------------------------------------------------------
# Parts endpoints
# ---------------------------------------------------------------------------

@app.post("/parts/", response_model=PartOut, status_code=201, tags=["Parts"])
def create_part(payload: PartCreate, db: Session = Depends(get_db)):
    """Add a new part to the catalog."""
    existing = db.query(Part).filter(Part.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Part '{payload.name}' already exists.")

    part = Part(**payload.model_dump())
    db.add(part)
    db.commit()
    db.refresh(part)

    db.add(HistoryLog(
        action_type="PART_CREATED",
        details=f"Part '{part.name}' added to catalog (id={part.id}).",
    ))
    db.commit()

    return part


@app.get("/parts/", response_model=list[PartOut], tags=["Parts"])
def list_parts(db: Session = Depends(get_db)):
    """Return the full parts catalog."""
    return db.query(Part).all()


# ---------------------------------------------------------------------------
# Parts — image upload endpoint
# ---------------------------------------------------------------------------

@app.post("/parts/{part_id}/image", response_model=PartOut, tags=["Parts"])
async def upload_part_image(
    part_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload an image for a part and save its path in the database."""
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail=f"Part id={part_id} not found.")

    # Build a safe filename: part_<id>_<original_name>
    safe_filename = f"part_{part_id}_{file.filename}"
    dest_path = os.path.join(IMAGES_DIR, safe_filename)

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Store the relative URL (served via /images/...)
    part.image_path = f"/images/{safe_filename}"
    db.commit()
    db.refresh(part)

    db.add(HistoryLog(
        action_type="PART_IMAGE_UPLOADED",
        details=f"Image uploaded for part '{part.name}' (id={part.id}): {part.image_path}.",
    ))
    db.commit()

    return part


# ---------------------------------------------------------------------------
# Materials endpoint
# ---------------------------------------------------------------------------

@app.post("/materials/add", tags=["Materials"])
def add_material(payload: MaterialAdd, db: Session = Depends(get_db)):
    """Receive filament stock — creates the material entry if it does not exist."""
    if payload.weight_to_add_g <= 0:
        raise HTTPException(status_code=400, detail="weight_to_add_g must be positive.")

    stock = db.query(MaterialStock).filter(
        MaterialStock.material_name == payload.material_name
    ).first()

    if stock:
        stock.total_weight_g += payload.weight_to_add_g
    else:
        stock = MaterialStock(
            material_name=payload.material_name,
            total_weight_g=payload.weight_to_add_g,
        )
        db.add(stock)

    db.flush()

    db.add(HistoryLog(
        action_type="MATERIAL_RECEIVED",
        details=(
            f"+{payload.weight_to_add_g}g of '{payload.material_name}' received. "
            f"New total: {stock.total_weight_g}g."
        ),
    ))
    db.commit()
    db.refresh(stock)

    return {
        "material_name": stock.material_name,
        "total_weight_g": stock.total_weight_g,
    }


# ---------------------------------------------------------------------------
# Orders endpoint
# ---------------------------------------------------------------------------

@app.post("/orders/", response_model=OrderOut, status_code=201, tags=["Orders"])
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    """Create a new customer order."""
    part = db.query(Part).filter(Part.id == payload.part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail=f"Part id={payload.part_id} not found.")

    order = Order(**payload.model_dump())
    db.add(order)
    db.commit()
    db.refresh(order)

    db.add(HistoryLog(
        action_type="ORDER_CREATED",
        details=(
            f"Order #{order.id} for customer '{order.customer}': "
            f"{order.target_quantity}× '{part.name}'."
        ),
    ))
    db.commit()

    return order


# ---------------------------------------------------------------------------
# Print session endpoints
# ---------------------------------------------------------------------------

@app.post("/sessions/start", response_model=SessionOut, status_code=201, tags=["Sessions"])
def start_session(payload: SessionStart, db: Session = Depends(get_db)):
    """Start a new print session for an order."""
    order = db.query(Order).filter(Order.id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order id={payload.order_id} not found.")

    if order.status != "В процессе":
        raise HTTPException(
            status_code=400,
            detail=f"Order #{order.id} is not active (status: '{order.status}').",
        )

    part = db.query(Part).filter(Part.id == order.part_id).first()

    now = datetime.now()
    expected_end = now + timedelta(minutes=part.print_time_mins + 30)

    session = PrintSession(
        order_id=payload.order_id,
        beds_started=payload.beds_started,
        items_per_bed_actual=payload.items_per_bed_actual,
        start_time=now,
        expected_end_time=expected_end,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    db.add(HistoryLog(
        action_type="SESSION_STARTED",
        details=(
            f"Session #{session.id} started for Order #{order.id}: "
            f"{payload.beds_started} bed(s), {payload.items_per_bed_actual} items/bed. "
            f"Expected end: {expected_end.strftime('%Y-%m-%d %H:%M')}."
        ),
    ))
    db.commit()

    return session


@app.post("/sessions/{session_id}/collect", tags=["Sessions"])
def collect_session(
    session_id: int,
    payload: CollectBeds,
    db: Session = Depends(get_db),
):
    """
    Collect printed beds from a session.

    Steps:
      1. Deduct total plastic consumed (successful + failed beds) from MaterialStock.
      2. Add successful items to FinishedGoods.
      3. Update Order.completed_quantity.
      4. Mark session as 'Собрано'.
    """
    # --- Fetch session ---
    session = db.query(PrintSession).filter(PrintSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session id={session_id} not found.")

    if session.status == "Собрано":
        raise HTTPException(status_code=400, detail="Session has already been collected.")

    order = db.query(Order).filter(Order.id == session.order_id).first()
    part = db.query(Part).filter(Part.id == order.part_id).first()

    total_beds = payload.successful_beds + payload.failed_beds
    if total_beds <= 0:
        raise HTTPException(status_code=400, detail="Total beds (successful + failed) must be > 0.")

    # --- Step 1: Deduct material consumed ---
    plastic_consumed_g = total_beds * session.items_per_bed_actual * part.weight_per_item_g

    stock = db.query(MaterialStock).filter(
        MaterialStock.material_name == part.material
    ).first()

    if not stock:
        raise HTTPException(
            status_code=400,
            detail=f"No material stock entry found for '{part.material}'. Please receive stock first.",
        )

    if stock.total_weight_g < plastic_consumed_g:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient material: need {plastic_consumed_g}g of '{part.material}', "
                f"but only {stock.total_weight_g}g in stock."
            ),
        )

    stock.total_weight_g -= plastic_consumed_g

    # --- Step 2: Add successful items to FinishedGoods ---
    successful_items = payload.successful_beds * session.items_per_bed_actual

    finished = db.query(FinishedGoods).filter(FinishedGoods.part_id == part.id).first()
    if finished:
        finished.quantity += successful_items
    else:
        finished = FinishedGoods(part_id=part.id, quantity=successful_items)
        db.add(finished)

    # --- Step 3: Update Order.completed_quantity ---
    order.completed_quantity += successful_items
    if order.completed_quantity >= order.target_quantity:
        order.status = "Завершен"

    # --- Step 4: Mark session as collected ---
    session.status = "Собрано"

    db.flush()

    db.add(HistoryLog(
        action_type="SESSION_COLLECTED",
        details=(
            f"Session #{session.id} collected — "
            f"successful beds: {payload.successful_beds}, failed beds: {payload.failed_beds}. "
            f"Items produced: {successful_items}. "
            f"Material deducted: {plastic_consumed_g}g of '{part.material}' "
            f"(remaining: {stock.total_weight_g:.1f}g). "
            f"Order #{order.id} progress: {order.completed_quantity}/{order.target_quantity}."
        ),
    ))
    db.commit()

    return {
        "session_id": session.id,
        "status": session.status,
        "items_produced": successful_items,
        "plastic_consumed_g": plastic_consumed_g,
        "material_remaining_g": stock.total_weight_g,
        "order_completed_quantity": order.completed_quantity,
        "order_status": order.status,
    }

