"""
TaskFlow Backend - FastAPI Task Management Service

A RESTful API for task management with TDD approach.

TP 1 & 2: Uses in-memory storage for simplicity
TP 3: Will introduce PostgreSQL database (see migration guide)
"""

from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
import logging
from contextlib import asynccontextmanager
import uuid
from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from .database import get_db, init_db
from .models import TaskModel, TaskStatus, TaskPriority
from fastapi.middleware.cors import CORSMiddleware
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("taskflow")


# =============================================================================
# ENUMS & MODELS
# ============================================================================


class TaskCreate(BaseModel):
    """Model for creating a new task."""
    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    description: Optional[str] = Field(None, max_length=1000, description="Task description")
    status: TaskStatus = Field(default=TaskStatus.TODO, description="Task status")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task priority")
    assignee: Optional[str] = Field(None, max_length=100, description="Assigned user")
    due_date: Optional[datetime] = Field(None, description="Due date")


class TaskUpdate(BaseModel):
    """Model for updating a task - all fields optional for partial updates."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assignee: Optional[str] = Field(None, max_length=100)
    due_date: Optional[datetime] = None


class Task(BaseModel):
    """Model for task response."""
    id: str  # UUID → string
    title: str
    description: Optional[str] = None
    status: TaskStatus
    priority: TaskPriority
    assignee: Optional[str] = None
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # permet de lire un objet SQLAlchemy



# =============================================================================
# IN-MEMORY STORAGE (for Atelier 1 & 2)
# =============================================================================


# =============================================================================
# FASTAPI APP
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager - initialise la DB au démarrage."""
    logger.info("🚀 TaskFlow backend starting up...")
    init_db()  # Crée les tables en base
    logger.info("✅ Database initialized")
    yield
    logger.info("🛑 TaskFlow backend shutting down...")
    
    

app = FastAPI(
    title="TaskFlow API",
    description="Simple task management API for learning unit testing and CI/CD",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configuration CORS pour le frontend
cors_origins_str = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
)
cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "message": "Welcome to TaskFlow API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check with database status."""
    try:
        # Vérifie que la DB répond
        db.execute(text("SELECT 1"))

        tasks_count = db.query(TaskModel).count()
        return {
            "status": "healthy",
            "database": "connected",
            "tasks_count": tasks_count,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": str(e),
        }



@app.get("/tasks", response_model=List[Task])
async def get_tasks(
    status: Optional[TaskStatus] = None,
    priority: Optional[TaskPriority] = None,
    assignee: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(TaskModel)

    if status:
        query = query.filter(TaskModel.status == status)
    if priority:
        query = query.filter(TaskModel.priority == priority)
    if assignee:
        query = query.filter(TaskModel.assignee == assignee)

    return query.all()


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task



@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = TaskModel(
        id=str(uuid.uuid4()),
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        assignee=payload.assignee,
        due_date=payload.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)  # récupère created_at / updated_at
    return task



@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: str,
    payload: TaskUpdate,  # ou TaskCreate si tu n'as pas de modèle séparé
    db: Session = Depends(get_db),
):
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # On met à jour uniquement les champs fournis
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task



@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
    return Response(status_code=204)

    return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)