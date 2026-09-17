from fastapi import APIRouter, Depends

from app.api.deps import require_roles
from app.models.user import User, UserRole
from app.schemas.tasks import TaskStatusResponse
from app.worker import celery_app

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.super_admin)),
) -> TaskStatusResponse:
    result = celery_app.AsyncResult(task_id)
    return TaskStatusResponse(
        task_id=task_id,
        status=result.status,
        result=result.result if result.successful() else None,
    )
