"""Contract file routes: upload / parse / download / delete / set type."""
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.contract import ContractFile
from app.models.user import User
from app.schemas.base import GenericResponse
from app.schemas.contract import (
    ContractFileResponse,
    SetContractTypeRequest,
    UploadResponse,
)
from app.services.document_parse import extract_contract_info, parse_document

router = APIRouter(prefix="/contracts", tags=["contracts"])
settings = get_settings()

ALLOWED_TYPES = {"pdf", "docx", "doc"}


def _save_upload(file: UploadFile, user_id: int) -> str:
    if not file.filename:
        raise HTTPException(400, "Filename required")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type: {ext}")
    save_dir = Path(settings.upload_dir) / str(user_id)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / file.filename
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return str(save_path)


@router.post("/upload", response_model=GenericResponse[UploadResponse])
async def upload_contract(
    file: UploadFile,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传并解析：抽取文本 + LLM 抽取甲乙方/金额。"""
    save_path = _save_upload(file, current_user.id)
    file_type = file.filename.rsplit(".", 1)[-1].lower()

    content = parse_document(save_path, file_type)
    if not content.strip():
        raise HTTPException(422, "Failed to parse document text")

    parsed_dir = Path(settings.oss_bucket_dir)
    parsed_dir.mkdir(parents=True, exist_ok=True)
    content_path = str(parsed_dir / f"{Path(save_path).stem}.txt")
    with open(content_path, "w", encoding="utf-8") as f:
        f.write(content)

    info = await extract_contract_info(content)

    record = ContractFile(
        user_id=current_user.id,
        title=file.filename,
        file_type=file_type,
        file_path=save_path,
        content_path=content_path,
        parse_status="parsed",
        party_a=info["party_a"],
        party_b=info["party_b"],
        amount=float(info["amount"]) if info.get("amount") else None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return GenericResponse(
        data=UploadResponse(
            file_id=record.id, title=record.title, file_type=record.file_type,
            file_url=f"/api/contracts/{record.id}/download",
            party_a=record.party_a, party_b=record.party_b, amount=record.amount,
        )
    )


@router.post("/upload_raw", response_model=GenericResponse[UploadResponse])
async def upload_raw(
    file: UploadFile,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """仅保存不解析（比对用）。"""
    save_path = _save_upload(file, current_user.id)
    file_type = file.filename.rsplit(".", 1)[-1].lower()
    record = ContractFile(
        user_id=current_user.id,
        title=file.filename,
        file_type=file_type,
        file_path=save_path,
        content_path="",
        parse_status="uploaded",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return GenericResponse(
        data=UploadResponse(
            file_id=record.id, title=record.title, file_type=record.file_type,
            file_url=f"/api/contracts/{record.id}/download", parse_status="uploaded",
        )
    )


@router.get("/{file_id}/download")
async def download(file_id: int, db: DBSession = Depends(get_db)):
    record = db.get(ContractFile, file_id)
    if record is None:
        raise HTTPException(404, "File not found")
    if not os.path.exists(record.file_path):
        raise HTTPException(404, "File lost on disk")
    return FileResponse(record.file_path, filename=os.path.basename(record.file_path))


@router.delete("/{file_id}", response_model=GenericResponse)
async def delete_file(
    file_id: int, db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.get(ContractFile, file_id)
    if record is None or record.user_id != current_user.id:
        raise HTTPException(404, "File not found")
    db.delete(record)
    db.commit()
    return GenericResponse(msg="file deleted")


@router.post("/{file_id}/type", response_model=GenericResponse)
async def set_contract_type(
    file_id: int, request: SetContractTypeRequest,
    db: DBSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    record = db.get(ContractFile, file_id)
    if record is None or record.user_id != current_user.id:
        raise HTTPException(404, "File not found")
    record.contract_type_id = request.contract_type_id
    record.review_position = request.review_position
    db.commit()
    return GenericResponse(msg="contract type set")


@router.get("", response_model=GenericResponse[list[ContractFileResponse]])
async def list_files(
    db: DBSession = Depends(get_db), current_user: User = Depends(get_current_user),
):
    records = (
        db.query(ContractFile)
        .filter(ContractFile.user_id == current_user.id)
        .order_by(ContractFile.created_at.desc())
        .all()
    )
    return GenericResponse(data=[_to_response(r) for r in records])


def _to_response(r: ContractFile) -> ContractFileResponse:
    return ContractFileResponse(
        id=r.id, title=r.title, file_type=r.file_type, party_a=r.party_a, party_b=r.party_b,
        amount=r.amount, contract_type_id=r.contract_type_id, review_position=r.review_position,
        is_accepted=r.is_accepted, created_at=str(r.created_at),
    )
