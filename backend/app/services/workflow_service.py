"""Workflow orchestration — natural language -> reviewable process JSON."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app.config import OUTPUT_FOLDER
from app.schemas.process_json import ProcessModel
from app.schemas.response import ChatResponse
from app.services import bpmn_generator, prompt_service, validator as validator_service
from app.services.llm_gateway import LLMError, LLMGateway
from app.utils import xml_util
from app.utils.logger import get_logger

log = get_logger(__name__)


class WorkflowError(Exception):
    """Raised when the pipeline cannot produce a valid process model."""


class WorkflowService:
    def __init__(self, llm: LLMGateway | None = None) -> None:
        self.llm = llm or LLMGateway()

    def generate_process(
        self,
        user_input: str,
        model_override: str | None = None,
        provider: str | None = None,
    ) -> ChatResponse:
        started = time.monotonic()
        system, user = prompt_service.build_generate_prompt(user_input)
        raw = self.llm.chat(
            system, user, temperature=0.2, model=model_override, provider=provider
        )
        try:
            process_model = self._parse_model(raw)
            report = validator_service.validate_process(process_model)
            if not report.valid:
                raise WorkflowError(self._validation_error(report))
        except WorkflowError as first:
            log.info("First LLM draft failed validation; attempting one repair pass")
            repair_sys, repair_user = prompt_service.build_repair_prompt(
                user_input, raw, str(first)
            )
            raw = self.llm.chat(
                repair_sys,
                repair_user,
                temperature=0.1,
                model=model_override,
                provider=provider,
            )
            process_model = self._parse_model(raw)
            report = validator_service.validate_process(process_model)

        for issue in report.issues:
            log.info("[%s] %s", issue.severity, issue.message)
        json_rel = self._save_json(process_model)
        latency_ms = int((time.monotonic() - started) * 1000)
        provider_name, model_name = self.llm.last_result or ("unknown", "unknown")
        log.info(
            "Generated process JSON '%s' in %d ms via %s/%s",
            process_model.process.id,
            latency_ms,
            provider_name,
            model_name,
        )
        return ChatResponse(
            process=process_model,
            validation=report,
            bpmn=None,
            json_path=str(json_rel),
            bpmn_path=None,
            llm_model=str(model_name),
            latency_ms=latency_ms,
        )

    def render_model(self, process_model: ProcessModel) -> str:
        report = validator_service.validate_process(process_model)
        if not report.valid:
            raise WorkflowError(
                "Process model failed validation: "
                + "; ".join(i.message for i in report.issues if i.severity == "error")
            )
        return bpmn_generator.generate_bpmn(process_model)

    def _parse_model(self, raw: str) -> ProcessModel:
        try:
            data = prompt_service.parse_llm_json(raw)
            return ProcessModel.model_validate(data)
        except (ValueError, ValidationError) as exc:
            raise WorkflowError(f"LLM produced an invalid process model: {exc}") from exc

    @staticmethod
    def _validation_error(report) -> str:
        return "Process model failed validation: " + "; ".join(
            i.message for i in report.issues if i.severity == "error"
        )

    def _save_json(self, model: ProcessModel) -> Path:
        folder = Path(OUTPUT_FOLDER)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = xml_util.output_file(folder, model.process.id, ".json", stamp)
        json_path.write_text(model.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
        log.info("Saved process JSON: %s", json_path.name)
        return json_path
