"""BPMN API — catalog, JSON->XML, validate, optional Camunda deploy."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import OUTPUT_FOLDER
from app.schemas.request import DeployRequest, GenerateBpmnRequest, ValidateRequest
from app.schemas.response import GenerateBpmnResponse, ValidationReport
from app.services import bpmn_generator, camunda_service, catalog_service, validator
from app.services.camunda_service import CamundaError
from app.utils import xml_util
from app.utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["BPMN"])


@router.get("/catalog")
def catalog() -> dict:
    return {"items": catalog_service.list_catalog()}


@router.get("/catalog/{process_id}")
def catalog_item(process_id: str) -> dict:
    try:
        model, bpmn = catalog_service.render_catalog_item(process_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "process": model.model_dump(by_alias=True),
        "bpmn": bpmn,
        "source": "prd",
    }


@router.post("/generate-bpmn", response_model=GenerateBpmnResponse)
def generate_bpmn(req: GenerateBpmnRequest) -> GenerateBpmnResponse:
    report = validator.validate_process(req.process)
    if not report.valid:
        raise HTTPException(
            status_code=422,
            detail="; ".join(i.message for i in report.issues if i.severity == "error"),
        )
    try:
        bpmn = bpmn_generator.generate_bpmn(req.process)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    saved = xml_util.output_file(OUTPUT_FOLDER, req.process.process.id, ".bpmn")
    saved.write_text(bpmn, encoding="utf-8")
    return GenerateBpmnResponse(bpmn=bpmn, bpmn_path=saved.name)


@router.post("/validate", response_model=ValidationReport)
def validate(req: ValidateRequest) -> ValidationReport:
    return validator.validate_process(req.process)


@router.post("/deploy")
def deploy(req: DeployRequest) -> dict:
    try:
        return camunda_service.deploy_bpmn(req.process_id, req.bpmn)
    except CamundaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
