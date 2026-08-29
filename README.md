# AI Work Order System

**Natural-language maintenance ticket triage, built on an LLM plus a rule engine.**

> **In short:** A property-management repairs desk receives tickets as free text
> ("the bathroom ceiling is leaking and it knocked out the power"). This system
> turns that into a categorised, addressed, worker-assigned work order in about
> **20 seconds** instead of the **~10 minutes** a human dispatcher took, while
> lifting classification accuracy from **92% to 96.6%**.

The interesting part is not that it calls an LLM. It is that a pure-LLM
approach was not accurate enough to ship, so the LLM is constrained by a rule
engine at every step — and that hybrid is what produced the numbers.

---

## Why LLM + rules, instead of just an LLM

A first pass that asked the model to classify each ticket end-to-end was
unusable. Three failure modes kept showing up:

1. **Compound problems.** *"The bathroom ceiling is leaking and it knocked out
   the power"* — the model would classify this as an electrical fault. The root
   cause is the leak; the power loss is downstream. Dispatching an electrician
   sends the wrong person.
2. **Severity confusion.** A dripping tap and a burst pipe are both "water",
   but only one is an emergency.
3. **Address drift.** The model would normalise or hallucinate addresses rather
   than extracting them verbatim.

So the model is never asked to do the whole job. It is given a narrow subtask,
and a rule engine validates and constrains the output:

- **Two-step classification** — the model first narrows to two candidate
  subcategories, then matches against a curated `problem` + `trigger_keyword`
  table. Step 2 is the part that fixed the compound-problem failure: the prompt
  explicitly instructs the model to pick candidates around the *root cause*,
  not the visible symptom.
- **Rule-based validation** — unrecognised categories are rejected rather than
  guessed at, and fall through to human handling.
- **Deterministic address resolution** — a 9-tier priority matcher resolves
  community names from the address string, with an administrative-prefix
  stripper and a POI blocklist. The model extracts; the rules verify.
- **Worker assignment** — matches on skill, current workload and the
  community-to-maintenance-unit mapping.

The practical consequence: when the taxonomy changes, you edit a JSON rule
file, not a prompt — and you can test it.

---

## Results

Measured against ~1,000 held-out historical tickets at the site where this was
deployed:

| | Before (human) | After (system) |
|---|---|---|
| Handling time per ticket | ~10 min | **~20 s** |
| Classification accuracy | ~92% | **96.6%** |

The accuracy figure is worth being precise about: **96.6% is not 100%**, and
the remaining ~3% matters when a misclassification sends someone to the wrong
address. That is why the system ships with a human-in-the-loop path —
dispatchers can correct a classification, and `feedback/` records the
correction so the rule tables can be revised.

---

## Pipeline

```
free-text ticket
      │
      ▼
 input_processor ──► session state, clarification prompts
      │
      ▼
   LLM (step 1) ───► 2 candidate subcategories  ─┐
      │                                          ├─► rule_engine validates
   LLM (step 2) ───► problem + trigger keyword  ─┘
      │
      ├────────────► address_handler ──► community / street / unit
      │
      ▼
  work_order ──────► assigned worker + priority, persisted to MySQL
      │
      ▼
   feedback ───────► human corrections feed back into the rule tables
```

| Module | Responsibility |
|---|---|
| `input_processor/` | Multi-turn session handling; decides when to ask the user for clarification instead of guessing |
| `rule_engine/` | Loads the category / subcategory / keyword tables and validates model output against them |
| `address_handler/` | 9-tier community-name extraction, administrative-prefix stripping, POI blocklist |
| `work_order/` | Work order construction, priority, worker assignment |
| `feedback/` | Records dispatcher corrections |
| `db/` | MySQL schema and access |

**Stack:** FastAPI · Vue 3 + Vite (resident and worker front ends) · MySQL ·
any OpenAI-compatible LLM endpoint.

---

## Quickstart

```bash
# Backend
pip install -r requirements.txt

export LLM_API_KEY=...          # any OpenAI-compatible endpoint
export LLM_BASE_URL=...
export MYSQL_HOST=localhost
export MYSQL_USER=...
export MYSQL_PASSWORD=...
export MYSQL_DB=workorder

python -m uvicorn api:app --reload --port 8000

# Resident front end
cd frontend && npm install && npm run dev

# Worker front end (separate app)
cd worker-frontend && npm install && npm run dev
```

Every credential is read from the environment. There are no hardcoded keys.

```bash
curl localhost:8000/api/v1/health
```

---

## API

Interactive docs are served at `/docs` once the backend is running. The main
entry point is the conversational endpoint:

```bash
curl -X POST localhost:8000/api/v1/converse \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u001","text":"卫生间顶上漏水严重，地址是示例区示例小区1号101室"}'
```

The remaining routes under `/api/v1/admin/` expose the rule tables
(categories, subcategories, keywords, locations, prompts, workers) so the
taxonomy can be edited without redeploying.

---

## Sample data

`data/test_data/` contains **18 tickets** — a small but representative slice
spanning seven service categories (electrical, drain cleaning, plumbing,
appliance repair, appliance cleaning, toilet fitting, doors and windows) and
all three intake channels. That is enough to exercise the classification
pipeline and run the matching tests without shipping a full operational
dataset.

**It has been fully anonymised.** Every field that could identify a resident or
a worker was replaced:

| Field | Treatment |
|---|---|
| Address | Replaced with synthetic addresses (`示例路41弄12号603室` etc.) |
| Street / district | Replaced with synthetic place names |
| Phone numbers | Replaced with reserved-range numbers (`1380000xxxx`) |
| Worker names | Replaced with `师傅A`–`师傅L` |

Two details are worth calling out, because both are easy to miss:

- **Addresses also appear inside free-text fields.** Residents type them
  straight into the problem description ("…浴霸坏…东方路3344弄24号502"). Masking
  only the `地址` column leaves those exposed, so addresses inside descriptions
  are rewritten too.
- **`工单详情_detail.json` was derived from this sample**, not copied from
  production. The pipeline reads both files; shipping one without the other
  means a fresh clone crashes on first run.

Ticket IDs and free-text problem descriptions are preserved, because they are
what the classifier actually consumes — but with addresses and phone numbers
stripped, no ticket can be traced back to an individual. Complaints and billing
disputes were excluded entirely: they are internal operations material, not
portfolio material. **No real personal data is included in this repository.**

---

## Limitations

- The taxonomy (`data/rules/`) is tuned for one property-management operator.
  Reusing this elsewhere means rewriting those tables; the pipeline is what
  transfers, not the rules.
- Accuracy was measured at a single site. There is no cross-site evaluation.
- The worker-assignment logic is a matching heuristic, not an optimisation —
  it does no route or schedule planning.
- The 96.6% figure comes from one deployment's historical tickets, not a
  controlled benchmark.

---

## Author

**袁承烨 (Chengye Yuan)** — M.Sc. in AI and Entrepreneurship, HKUST (2026–2028).
B.Sc. in Computer Science, East China University of Science and Technology, 2026.

Built during an industry internship.
