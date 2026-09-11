# Product Requirements — LMS and Exam System

**Product:** Flexavior LMS + Exam  
**Roles:** Teacher, Student, Admin Staff  
**Source of truth for BPMN:** this PRD → process JSON in `examples/lms_*.json` → Camunda 8 BPMN via the generator.

The studio in this repo does **not** implement the LMS product. It produces deployable BPMN diagrams for the processes below so Camunda 8 can orchestrate them.

---

## 1. Problem

Schools need one workflow system for enrollment, exam authoring, sitting an exam, staff user setup, and grade appeals. Work today is email-driven and easy to skip a control (eligibility, review, dual-control regrade).

## 2. Actors

| Role | Goal |
|------|------|
| Student | Enroll, sit exams, see results, file an appeal |
| Teacher | Author exams, grade non-auto items, release results, regrade |
| Admin staff | Confirm seats/payments, provision accounts, triage appeals |

## 3. Out of scope (this repo)

- Live exam delivery UI, question bank, or LMS pages
- Production Camunda cluster, IdP, or billing
- Auto-start of Zeebe jobs without `CAMUNDA_DEPLOY_ENABLED=true`

## 4. Processes (must have a diagram)

### P1 — Student course enrollment

Student submits a course request. The system checks eligibility. Ineligible students are notified and the case ends. Eligible requests reserve a seat and create an invoice in parallel. Staff confirm payment and seat. The system writes the enrollment and notifies the student.

**Controls:** eligibility gate; staff confirmation before enrollment is durable.

### P2 — Teacher exam authoring and publish

Teacher drafts the exam and adds questions. If policy requires review, staff review it. Rejected drafts return to the teacher. Approved (or review-exempt) exams get a schedule window and are published to the cohort.

**Controls:** optional dual control before students see the paper.

### P3 — Student exam attempt and grading

Student starts a locked session, submits answers. Auto-gradable items are scored by a service; constructed response goes to the teacher. After both paths join, the teacher releases results. The student is notified of pass or fail.

**Controls:** session lock; teacher release before results are official.

### P4 — Admin user provisioning

Staff create an account and pick a role. Student accounts attach to a program, teachers to a department, staff to a permission set. An invite is sent; the user activates the account.

**Controls:** role assignment is an exclusive gateway; no default admin role.

### P5 — Exam incident and appeal

Student files an appeal. Staff triage validity. Invalid appeals are rejected. Valid appeals go to the teacher for regrade. Staff record the outcome and notify the student.

**Controls:** staff triage before regrade; outcome is recorded by staff, not only the teacher.

## 5. Non-functionals (runtime, when deployed)

- AuthN/AuthZ on Camunda user tasks (IdP in the host LMS)
- Audit: who confirmed enrollment, published, released, regraded
- PII (names, marks) not stored in BPMN XML — only business keys
- Idempotent service tasks (`fxv.lms.<process>.<task>`)

## 6. Acceptance for this BPMN project

1. Each process JSON validates with zero errors.
2. Generated XML uses the BPMN 2.0 **MODEL** namespace and includes `bpmndi:BPMNDiagram`.
3. User tasks carry `zeebe:userTask`; service tasks carry `zeebe:taskDefinition`.
4. Exclusive-gateway conditions are FEEL (`= …`).
5. pytest in `backend/tests` is green without calling a paid LLM.
6. Studio UI can open each PRD process as a diagram.
