"""Branches router with branch CRUD operations."""

import uuid
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import APIRouter, Request, status

from app.exceptions import NotFoundError

router = APIRouter()

# ---------------------------------------------------------------------------
# Mock in-memory branch store
# ---------------------------------------------------------------------------
_mock_branches: Dict[str, Dict] = {}


def _generate_branch_id() -> str:
    """Generate a unique branch ID."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Branch CRUD endpoints (mock)
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=List[dict],
    status_code=status.HTTP_200_OK,
    summary="List all branches",
)
async def list_branches(request: Request) -> List[dict]:
    """List all branches (mock)."""
    return list(_mock_branches.values())


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new branch",
)
async def create_branch(request: Request, data: dict) -> dict:
    """Create a new branch (mock).

    Expected fields in data:
        - name (str, required): Branch name
        - company_id (str, required): Parent company ID
        - address (str, optional): Branch address
        - phone (str, optional): Contact phone
        - email (str, optional): Contact email
        - manager_name (str, optional): Branch manager name
        - is_active (bool, optional): Whether the branch is active
    """
    branch_id = _generate_branch_id()
    now = datetime.now(timezone.utc).isoformat()

    branch = {
        "id": branch_id,
        "name": data.get("name", "Unnamed Branch"),
        "company_id": data.get("company_id", ""),
        "address": data.get("address", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "manager_name": data.get("manager_name", ""),
        "is_active": data.get("is_active", True),
        "created_at": now,
        "updated_at": now,
    }

    _mock_branches[branch_id] = branch
    return branch


@router.get(
    "/{branch_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get a branch by ID",
)
async def get_branch(branch_id: str) -> dict:
    """Get a branch by ID (mock)."""
    branch = _mock_branches.get(branch_id)
    if not branch:
        raise NotFoundError(detail=f"Branch with ID '{branch_id}' not found")
    return branch


@router.put(
    "/{branch_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Update a branch",
)
async def update_branch(branch_id: str, data: dict) -> dict:
    """Update a branch by ID (mock)."""
    branch = _mock_branches.get(branch_id)
    if not branch:
        raise NotFoundError(detail=f"Branch with ID '{branch_id}' not found")

    updatable_fields = [
        "name", "company_id", "address", "phone",
        "email", "manager_name", "is_active",
    ]
    for field in updatable_fields:
        if field in data:
            branch[field] = data[field]

    branch["updated_at"] = datetime.now(timezone.utc).isoformat()
    _mock_branches[branch_id] = branch

    return branch


@router.delete(
    "/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a branch",
)
async def delete_branch(branch_id: str) -> None:
    """Delete a branch by ID (mock)."""
    if branch_id not in _mock_branches:
        raise NotFoundError(detail=f"Branch with ID '{branch_id}' not found")
    del _mock_branches[branch_id]
