from fastapi import APIRouter

from deps.auth import CurrentUser
from deps.db import Db

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("/")
def get_resumes(db: Db, current_user: CurrentUser):
    return {"message": "Get all resumes"}


@router.post("/")
def create_resume(db: Db, current_user: CurrentUser):
    return {"message": "Create a new resume"}


@router.get("/{resume_id}")
def get_resume(resume_id: int, db: Db, current_user: CurrentUser):
    return {"message": f"Get resume with ID {resume_id}"}


@router.patch("/{resume_id}")
def update_resume(resume_id: int, db: Db, current_user: CurrentUser):
    return {"message": f"Update resume with ID {resume_id}"}


@router.delete("/{resume_id}")
def delete_resume(resume_id: int, db: Db, current_user: CurrentUser):
    return {"message": f"Delete resume with ID {resume_id}"}
