# Repository Guidelines

## Project Boundary

This repository contains black-box API scenarios plus one explicitly enabled,
read-only API-to-database check. It does not contain the application source or
white-box unit tests. Review behavior, contracts, isolation, evidence, and test
framework maintainability within that boundary.

`framework_checks/` separately verifies this repository's HTTP/assertion, fixture,
AI reply/history, and runner contracts with synthetic loopback traffic or resource
substitutes. It does not test application internals and is excluded from the
business counts and default `testpaths = tests` selection. Never require live
credentials, business services, databases, or notifications for these checks.

## Required Static Checks

Run these checks for repository changes that do not require a live test system:

```bash
python -m ruff format --check .
python -m ruff check .
python -m compileall -q ev_api tests framework_checks scripts run_api_tests.py
bash -n scripts/check_linux_test_env.sh
python scripts/validate_postman_assets.py
python -m pytest --collect-only -q
python -m pytest --collect-only -q -m "not destructive and not database"
python -m pytest framework_checks -q --junitxml=reports/framework-checks.xml
```

Do not describe collection-only validation as a successful business regression.
Live API, database, destructive, AI-degradation, and Newman execution require
their documented isolated-environment prerequisites.

## Commit Messages

- Use `type: 中文说明`, for example `test: 补充售后服务全流程接口自动化`.
- Allowed types are `feat`, `fix`, `test`, `docs`, `refactor`, `ci`, `chore`,
  `perf`, `build`, `style`, and `revert`; an optional lowercase scope is allowed.
- Keep the subject within 72 characters and start the description with Chinese text.

## Code Review Rules

### P0: environment and data safety

- Reject committed passwords, tokens, webhooks, private keys, personal data, or
  real report artifacts.
- Reject any path that can run `destructive` or `database` scenarios by default.
- Reject production or shared-environment defaults, implicit write access, root
  database use, or database operations beyond the approved SELECT query.
- Reject non-loopback database connections without CA-backed TLS certificate and
  hostname verification, or accounts with `WITH GRANT OPTION`/delegation rights.
- Reject shell diagnostics that print environment-variable values, credentials,
  response bodies, or authenticated request URLs.
- Reject request, response, assertion, or notification evidence that can expose
  credentials, JWTs, personal data, or business identifiers without redaction.

### P1: test correctness

- Do not weaken HTTP or business-code assertions to hide an application defect.
  Known defect `API-AUTHZ-001` must remain a real failing assertion until the
  application is fixed and the same scenario passes unchanged.
- Authenticated clients must be isolated per test because a new login invalidates
  an earlier token. Flag shared mutable sessions or order-dependent scenarios.
- Environment outage, missing required credentials, zero selected tests, skipped
  selected scenarios, and malformed responses must fail the run; they must not
  produce a false green.
- Every state-changing scenario must have the `destructive` marker and explicit
  enable switch. Every database scenario must have the `database` marker and a
  verified SELECT-only account.
- Assertions must verify the relevant business contract or side effect, not only
  HTTP 200, element presence, or a non-empty body.

### P1: architecture and maintainability

- Keep scenario orchestration in `tests/`, endpoint details in `ev_api/apis/`,
  transport/database behavior in adapters, and shared contracts in assertions.
- Do not duplicate login, HTTP setup, redaction, table assertions, or report
  cleanup across test modules.
- Prefer function-scoped fixtures for authenticated or stateful resources. Raise
  fixture scope only when the resource is demonstrably immutable and safe to share.
- Parameterized state-changing cases must use independent records. Do not reuse a
  record after an earlier parameter may have changed its state.
- Register every marker in `pytest.ini`; keep default CI selectors and Jenkins
  selectors equivalent.
- Keep shell diagnostics non-interactive, fail-fast, safe for reruns, and free of
  state-changing commands. Linux preflight must verify transport and business
  status without authenticating or modifying application data.
- When scenario counts, execution scope, or evidence changes, update README,
  coverage matrix, strategy, report, and Postman asset validator together.

### Evidence and review focus

- “Passed” requires a recorded real execution. Otherwise use “not executed” or
  “collection validated”. Never infer business success from compilation or CI
  collection checks.
- Do not request white-box/unit-test coverage for this repository. Recommend a
  focused black-box, contract, or explicitly gated gray-box scenario for the
  application instead. Framework reliability regressions belong in `framework_checks/`.
- Avoid style-only comments already enforced by Ruff. Focus review comments on
  P0/P1 correctness, safety, false-green risk, data isolation, and maintainability.
