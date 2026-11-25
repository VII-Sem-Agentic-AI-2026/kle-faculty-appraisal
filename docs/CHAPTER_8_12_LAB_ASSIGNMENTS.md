# Chapter 8 – Faculty Appraisal Management System: 12-Lab Assignment Structure

**Project:** Agentic AI-Based Faculty Appraisal Management System (FAMS)  
**Chapter:** 8  
**Original labs:** 14  
**Revised labs:** 12

## 1. Overview

The Faculty Appraisal Management System automates and streamlines faculty appraisal by collecting research, teaching-learning and administrative activity records, validating supporting evidence, calculating appraisal scores with approved weightages, and generating an appraisal report for HoD, Dean and IQAC review.

The system follows a coordinator-plus-specialist-agent architecture. Agents collect, process, validate and prepare appraisal information, while designated human authorities review and approve consequential decisions and final reports.

## Lab Consolidation

| Revised lab | Original labs merged | Combined focus |
|---|---|---|
| Lab 2 | Original Labs 2 and 5 | Tool-Using Agent and MCP-Style Connector |
| Lab 8 | Original Labs 9 and 10 | Evidence Grounding and Ops Resilience |

All remaining original labs are retained as individual assignments.

## Phase A – Foundations

### Assignment 01 – Agent vs Chatbot: Appraisal Planner

**Objective:** Develop an agentic planner that clarifies faculty appraisal requirements, creates an editable execution plan, and revises the plan based on user feedback.

**Prerequisites:** Basic understanding of agent loops and the faculty appraisal workflow.

**Tasks:**

1. Accept a faculty appraisal request in natural language.
2. Identify missing information and ask clarifying questions.
3. Generate a structured appraisal plan.
4. Allow the user to review and modify the proposed plan.
5. Revise the plan based on feedback.
6. Lock the approved plan before execution.

**Expected outputs:**

- Clarified appraisal request
- Structured and editable appraisal plan
- Locked execution blueprint

**Deliverables:**

- A working planner agent that demonstrates the clarify → plan → revise loop.

**Acceptance criteria:**

- [ ] The agent asks at least two clarifying questions when given a vague request.
- [ ] It generates a coherent, editable plan.
- [ ] It incorporates user feedback into the revised plan.

**Dependency:** None; this is the entry-point lab.

---

### Assignment 02 – Tool-Using Agent and MCP-Style Connector

*Merged original Labs 2 and 5.*

**Objective:** Develop a tool-using agent that accesses faculty records through a common, governed connector instead of relying on information supplied in prompts.

**Prerequisites:** Assignment 01 and understanding of the faculty activity data model.

**Tasks:**

1. Create typed tools to read teaching, research and administrative records.
2. Create tools to retrieve student feedback, publication and grant information.
3. Develop a domain calculator/checker for relevant appraisal values.
4. Create a common connector that exposes data sources through typed endpoints.
5. Include authentication and controlled data access in the connector.
6. Ensure all data-facing agents use the connector rather than accessing sources directly.
7. Verify that a data source can be replaced without changing the agents.

**Expected outputs:**

- Typed data-reading and computation tools
- Common connector interface
- Parsed and verified activity information
- Uniform data-access mechanism

**Deliverables:**

- A working tool-using agent connected to a governed MCP-style connector.

**Acceptance criteria:**

- [ ] Key numbers and lookups are obtained through tools.
- [ ] All data access goes through the connector.
- [ ] Replacing a source does not require changes to agent logic.

**Dependency:** Assignment 01.

---

### Assignment 03 – Skill Creation: Reusable Appraisal Skills

**Objective:** Create reusable, schema-typed skills for appraisal planning and report formatting.

**Prerequisites:** Assignment 01 and parsed inputs from Assignment 02.

**Tasks:**

1. Develop a reusable appraisal planning skill.
2. Define the input and output schemas for the skill.
3. Develop an appraisal report formatting skill.
4. Define a reusable report template.
5. Integrate both skills with the coordinator.
6. Test the skills using different faculty appraisal cases.

**Expected outputs:**

- Reusable planning skill
- Reusable report formatting skill
- Locked plan object
- Formatted appraisal report structure

**Deliverables:**

- Two callable skills with defined schemas.

**Acceptance criteria:**

- [ ] Both skills can be invoked by the agent.
- [ ] The same skills work for at least two different appraisal cases without code changes.

**Dependency:** Assignments 01 and 02.

---

### Assignment 04 – Memory and Retrieval: State vs Stored Knowledge

**Objective:** Implement short-term session memory and long-term retrieval for faculty records and previous appraisal cycles.

**Prerequisites:** Assignments 01–03 and a structured faculty activity data model.

**Tasks:**

1. Maintain the current appraisal draft in short-term session state.
2. Store faculty activity records and appraisal history separately.
3. Implement tag-based retrieval.
4. Implement similarity-based retrieval.
5. Retrieve relevant records from previous faculty appraisal cycles.
6. Test whether retrieved information is relevant to the current task.

**Expected outputs:**

- Short-term appraisal session state
- Long-term record store
- Tag-based retrieval
- Similarity-based retrieval of historical records

**Deliverables:**

- A memory and retrieval component that supports current and previous appraisal cases.

**Acceptance criteria:**

- [ ] The system distinguishes the current draft from stored records.
- [ ] Retrieval returns correctly tagged records.
- [ ] Similar prior items can be retrieved for a given task.

**Dependency:** Assignments 01–03.

---

### Assignment 05 – Runtime: Skills, Tools, Memory and Audit

**Objective:** Integrate agent skills, tools and memory into a controlled execution runtime with audit logging and checkpoints.

**Prerequisites:** Assignments 02, 03 and 04.

**Tasks:**

1. Integrate the skills developed in Assignment 03.
2. Connect the governed connector from Assignment 02.
3. Integrate the memory and retrieval component from Assignment 04.
4. Introduce execution budgets.
5. Configure approval gates for sensitive or consequential actions.
6. Log the inputs, actions and outputs of every execution step.
7. Implement checkpoint and resume functionality.

**Expected outputs:**

- Governed agent runtime
- Execution budget controls
- Approval checkpoints
- Audit log
- Checkpoint and resume functionality

**Deliverables:**

- A controlled runtime wrapping the appraisal agent.

**Acceptance criteria:**

- [ ] Every action is logged with its inputs and outputs.
- [ ] Risky actions wait for the required approval.
- [ ] A crashed execution can resume from its last checkpoint.

**Dependency:** Assignments 02–04.

## Phase B – Orchestration

### Assignment 06 – Agentic Node Graph: Complete Appraisal Pipeline

**Objective:** Connect specialist agents into an explicit node graph that executes the complete faculty appraisal workflow.

**Prerequisites:** Assignments 01–05.

**Tasks:**

1. Create the coordinator node.
2. Connect the Research Data Collection Agent.
3. Connect the Teaching-Learning Data Collection Agent.
4. Connect the Administrative Data Collection Agent.
5. Connect the Evidence Validation Agent.
6. Connect the API Calculation Agent.
7. Connect the Report Generation Agent.
8. Add the HoD/Dean/IQAC human review gate.
9. Add the governed publishing stage.
10. Implement a bounded validation-to-regeneration path.

**Expected outputs:**

- Complete agent node graph
- Shared execution state
- Connected specialist agents
- Validation and regeneration path
- Draft appraisal summary and rating recommendation

**Deliverables:**

- An executable end-to-end appraisal workflow.

**Acceptance criteria:**

- [ ] A single command executes the complete appraisal pipeline.
- [ ] The system generates a validated appraisal draft.
- [ ] Failed validation triggers a bounded retry.
- [ ] Publishing cannot bypass the human approval gate.

**Dependency:** Assignments 01–05.

---

### Assignment 07 – Parallel Swarm: Faculty Appraisal Processing

**Objective:** Implement parallel processing of multiple faculty appraisal cases and merge the results according to the locked plan.

**Prerequisites:** Assignment 06 and a locked appraisal plan.

**Tasks:**

1. Define multiple faculty members or appraisal cycles as separate work units.
2. Create parallel worker execution.
3. Distribute work units among specialist workers.
4. Collect outputs from all workers.
5. Implement a merge/selection mechanism.
6. Select results based on alignment with the locked plan.
7. Compare sequential and parallel execution.

**Expected outputs:**

- Parallel worker execution
- Individual faculty appraisal results
- Merged appraisal output
- Execution-time and quality comparison

**Deliverables:**

- A working fan-out/fan-in parallel processing mechanism.

**Acceptance criteria:**

- [ ] All planned work units are processed.
- [ ] The merge mechanism preserves plan alignment and coverage.
- [ ] Parallel execution matches or improves sequential quality with lower wall-clock time.

**Dependency:** Assignment 06.

## Phase C – Applied Reliability

### Assignment 08 – Evidence Grounding and Ops Resilience

*Merged original Labs 9 and 10.*

**Objective:** Ensure that appraisal outputs are grounded in verified records and that validation failures are diagnosed and repaired within a controlled retry budget.

**Prerequisites:** Assignments 06 and 07, approved appraisal rubric and verified records.

**Tasks:**

**Part A – Evidence grounding**

1. Use the approved appraisal rubric and verified faculty records.
2. Attach an evidence record to each appraisal candidate.
3. Record the source, scope and relevant tags for every claim.
4. Generate an evidence table for appraisal activities.
5. Reject candidates that cannot be linked to an in-scope source.

**Part B – Validation and resilience**

6. Validate whether every score is supported by evidence.
7. Verify that the calculation follows the approved weightage policy.
8. Identify the exact constraint responsible for a validation failure.
9. Regenerate only the affected component.
10. Maintain a bounded retry mechanism.
11. Escalate unresolved failures to the human reviewer.

**Expected outputs:**

- Evidence record for each appraisal claim
- Evidence table
- Validation report
- Failure diagnosis log
- Repaired output or escalation record

**Deliverables:**

- An evidence-grounded and self-healing validation pipeline.

**Acceptance criteria:**

- [ ] Every output maps to an in-scope source.
- [ ] Ungrounded candidates are rejected.
- [ ] Injected validation failures are detected.
- [ ] The system repairs the affected component within the retry budget.
- [ ] Unresolved failures are escalated rather than silently accepted.

**Dependency:** Assignments 06 and 07.

---

### Assignment 09 – SDLC Factory: Specification to Tested Output

**Objective:** Treat the locked appraisal plan as a specification and ensure that generated appraisal output passes automated acceptance tests before human review.

**Prerequisites:** Assignments 06–08.

**Tasks:**

1. Use the locked appraisal plan as the system specification.
2. Define acceptance criteria for the appraisal output.
3. Develop an automated acceptance test suite.
4. Integrate the test suite with the appraisal graph.
5. Generate the appraisal summary and rating recommendation.
6. Produce a test report showing passed and failed checks.
7. Prevent outputs from advancing when acceptance tests fail.

**Expected outputs:**

- Locked appraisal specification
- Automated acceptance suite
- Generated appraisal artifact
- Acceptance test report

**Deliverables:**

- A build process that produces an appraisal artifact with a passing test report.

**Acceptance criteria:**

- [ ] The system produces an appraisal output from the locked plan.
- [ ] Every required acceptance check is executed.
- [ ] No appraisal output advances to the HoD/appraisal committee without a fully passing acceptance report.

**Dependency:** Assignments 06–08.

## Phase D – Governance and Capstone

### Assignment 10 – Safety and Governance: Approval, Evaluation and Rollback

**Objective:** Implement access control, confidentiality, human approval, evaluation metrics, versioning and rollback.

**Prerequisites:** Assignments 05, 06 and 09.

**Tasks:**

1. Define role-based access permissions.
2. Separate draft appraisal records from approved records.
3. Restrict access to individual faculty appraisal data.
4. Implement the HoD/appraisal committee approval gate.
5. Record human edits, approvals and overrides.
6. Maintain evaluation metrics.
7. Version approved appraisal reports.
8. Implement rollback to a previous approved version.
9. Maintain an audit trail for governed publishing.

**Expected outputs:**

- Role-based access control
- Human approval workflow
- Confidentiality controls
- Evaluation metrics
- Version history
- Rollback functionality
- Audit records

**Deliverables:**

- A governed and reversible appraisal release workflow.

**Acceptance criteria:**

- [ ] Only authorized reviewers can approve appraisal results.
- [ ] Only approved results can be published.
- [ ] Faculty appraisal information remains confidential.
- [ ] Released versions can be rolled back cleanly.

**Dependency:** Assignments 05, 06 and 09.

---

### Assignment 11 – Discipline-Specific Agents: Domain Specialisation

**Objective:** Develop pluggable specialist agents that adapt appraisal processing to different faculty profiles.

**Prerequisites:** Assignment 06 and the appraisal generation workflow.

**Tasks:**

1. Define faculty domain profiles.
2. Create a teaching-heavy profile.
3. Create a research-heavy profile.
4. Create an administrative-heavy profile.
5. Implement a specialist registry.
6. Connect the selected specialist to the generation node.
7. Validate outputs against the relevant domain scheme.

**Expected outputs:**

- Domain profile definitions
- Specialist registry
- Domain-specific appraisal outputs
- Checkable appraisal schemes

**Deliverables:**

- A domain-specialisation component integrated with the generation agent.

**Acceptance criteria:**

- [ ] The appropriate specialist is selected for each domain profile.
- [ ] Outputs follow the correct domain patterns.
- [ ] Each output produces checkable results.

**Dependency:** Assignment 06.

---

### Assignment 12 – Capstone: Team-Owned Faculty Appraisal System

**Objective:** Integrate all previous assignments into a complete Faculty Appraisal Management System and demonstrate the appraisal process end to end.

**Prerequisites:** Assignments 01–11.

**Tasks:**

1. Integrate the governed data connector.
2. Integrate the controlled runtime.
3. Integrate the complete agent node graph.
4. Enable parallel faculty appraisal processing.
5. Integrate evidence grounding and validation.
6. Integrate targeted self-healing.
7. Integrate automated acceptance testing.
8. Integrate governance, approval and rollback.
9. Integrate discipline-specific specialists.
10. Build the HoD/appraisal committee dashboard.
11. Demonstrate the complete workflow using a real appraisal case with authorized records and an approved rubric.
12. Generate the appraisal report and maintain its audit trail.

**Expected outputs:**

- Integrated Faculty Appraisal Management System
- Appraisal dashboard
- Validated appraisal summary
- Rating recommendation
- Human approval workflow
- Versioned report and audit trail

**Deliverables:**

- A deployed, team-owned system demonstrated end to end.

**Acceptance criteria:**

- [ ] The system completes the appraisal workflow in one session.
- [ ] The appraisal summary and rating recommendation are grounded in verified evidence.
- [ ] Validation checks pass before human review.
- [ ] The HoD/appraisal committee approves the final result.
- [ ] The published result has a complete audit trail.

**Dependency:** Assignments 01–11.

## 2. Overall Dependency Structure

The recommended implementation order is:

| Revised lab | Assignment |
|---|---|
| 1 | Appraisal Planner |
| 2 | Tool-Using Agent and MCP-Style Connector |
| 3 | Reusable Skills |
| 4 | Memory and Retrieval |
| 5 | Governed Runtime |
| 6 | Agentic Node Graph |
| 7 | Parallel Swarm |
| 8 | Evidence Grounding and Ops Resilience |
| 9 | SDLC Factory |
| 10 | Safety and Governance |
| 11 | Discipline-Specific Agents |
| 12 | Capstone |

### Dependency Summary

- Assignment 05 requires the connector, skills and memory from Assignments 02–04.
- Assignment 06 builds on the foundations and runtime from Assignments 01–05.
- Assignment 07 requires the graph and locked execution plan from Assignment 06.
- Assignment 08 requires appraisal candidates, verified records and the approved rubric.
- Assignment 09 tests the output of the appraisal pipeline against the locked specification.
- Assignment 10 formalises the human approval and governed release process.
- Assignment 11 plugs domain specialists into the generation workflow.
- Assignment 12 integrates all previous deliverables.

## 3. Mandatory System Guardrails

The following requirements apply across all 12 assignments:

1. Agents may prepare, analyse and flag appraisal information, but a designated human must approve consequential decisions.
2. Appraisal calculations must use approved institutional or applicable policy weightages.
3. Every score must have a traceable calculation method and supporting evidence.
4. Missing or unverified activities must not be silently treated as zero.
5. Raw self-reported activity must remain separate from validated appraisal records.
6. Faculty appraisal information must remain confidential and access-controlled.
7. Evidence validation must be completed before score calculation.
8. No final appraisal report may be published without the required human approval.
9. Every consequential action must be recorded in the audit trail.
10. Approved appraisal reports must be versioned and reversible.

## 4. Final Project Workflow

```text
Faculty Profile and Consent
↓
Research Data Collection Agent
Teaching-Learning Data Collection Agent
Administrative Data Collection Agent
↓
Evidence Validation Agent
↓
API Calculation Agent
↓
Report Generation Agent
↓
HoD / Dean / IQAC Review
↓
Human Approval
↓
Governed Publishing, Dashboard and Audit Trail
```

**Final result:** An evidence-validated, transparent and human-approved Faculty Appraisal Management System.

---

**Note:** The revised 12-lab structure consolidates the original Chapter 8 14-lab method. The merged assignments retain the capabilities, deliverables and acceptance requirements of their respective original labs. This document does not define or invent official appraisal scoring weightages.
