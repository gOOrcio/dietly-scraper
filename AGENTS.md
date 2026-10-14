# AGENTS.md — dietly-scraper

Daily one-shot Python script: for each configured user it logs into **Dietly.pl** (catering app), reads today's menu for the purchased diet, and pushes the meals + nutrition into the user's **Fitatu** diary. No browser automation — plain `httpx` against both sites' private web APIs (the README's Playwright mentions are stale).

## Where things run

- **Everything lives on Gitea** `gooral/dietly-scraper` (`git@gitea-ssh.mati-lab.online`). PRs are opened and merged there (`tea ... --repo gooral/dietly-scraper --login gitea.mati-lab.online`).
- `.gitea/workflows/ci.yml` runs the shared quality workflows from `gooral/ci-workflows`: ruff, then mypy, then pytest, plus yaml, duplication and secrets checks.
- `.gitea/workflows/daily-sync.yml` is the **production sync**. It runs on the homelab runner at cron `0 2 * * *` UTC, or on demand:
  `tea actions workflows dispatch daily-sync.yml --repo gooral/dietly-scraper --login gitea.mati-lab.online --ref <branch>`.
  - Secrets: `USERS_YAML` (required), `NTFY_TOKEN` (alerts go to `homelab-alerts`), `KUMA_PUSH_URL` (dead-man heartbeat). <!-- pragma: allowlist secret -->
  - Site URLs are built-in defaults in `SitesConfiguration`.
  - A failed run (exit 1 = some users failed, exit 2 = all failed) triggers an ntfy alert. A successful run pings Kuma.
  - There is no workflow-level retry: the script already retries transient errors per user.
  - Requests leave from the home IP. Dietly answers repeated failed logins with 429, so don't loop manual runs.
- **GitHub `gOOrcio/dietly-scraper` is only a push mirror.** It used to run the sync until 2026-10-14. Actions are disabled there and `.github/` was deleted. Don't use `gh` for this project.
- A green run can still mean nobody's menu synced ("No active plan" counts as success). Read the per-user lines (JSON objects with a `status` key) and the `Summary` step.

## Layout

```
main.py                      # orchestration: per-user sync, retries, JSON-ish logging, exit codes
src/clients/base_client.py   # shared httpx AsyncClient, retry/backoff (5xx only), safe JSON decode
src/clients/dietly_client.py # login → active orders → order details → delivery for date → menu
src/clients/fitatu_client.py # login (JWT) → search/create products → read/update/publish diet plan
src/models/                  # pydantic models (config, Dietly order/menu, Fitatu product)
src/utils/constants.py       # endpoints, headers (UA, Fitatu APP-* headers), meal mapping, retry config
config/*.yaml.example        # templates; real users.yaml / sites.yaml are gitignored
```

Flow per user: Dietly `POST /api/auth/login` (form-encoded) → `GET /api/profile/profile-order/active-ids` → `GET /api/company/customer/order/{id}` → find the delivery for today → `GET /api/company/general/menus/delivery/{deliveryId}/new` → map meals (`MEAL_MAPPING`: Śniadanie, II śniadanie, Obiad, Podwieczorek, Kolacja) → Fitatu: find or create each product, add it to the day's diet plan, publish.

Exit codes: `0` all users OK · `1` partial · `2` all failed. "No active plan" counts as **success**.

## Dev workflow

```bash
uv sync
cp config/users.yaml.example config/users.yaml   # fill in locally, never commit
cp config/sites.yaml.example config/sites.yaml
uv run python main.py
pre-commit run --all-files                       # ruff, ruff-format, gitleaks, detect-secrets
uv run --extra dev pytest                        # unit tests (pure logic only)
uvx mypy . --ignore-missing-imports              # Gitea CI runs this; keep it clean
```

- Python 3.12, `uv`, `httpx`, `pydantic` v2. `tests/` covers only the pure logic (name cleaning, payload mapping, error categories, exit codes, log format). Anything touching the HTTP flow still has to be verified against the real APIs (dispatch `daily-sync.yml` on your branch, see above) or by replaying a JSON response captured from a run log.
- Gitea CI (`gooral/ci-workflows` python-quality) runs ruff, then mypy, then pytest, and pytest only runs if mypy passes.
- Logging is configured once, in `main.py`. Don't add `logging.basicConfig` to modules. `log_json()` writes compact single-line JSON, and the workflow's summary step greps it.
- Pydantic models should strictly validate **only the fields we consume**. Dietly regularly sends nulls or new shapes in fields we ignore (see PRs #8–#10).
- Note: the `login_url` in `sites.yaml.example` (`/login`) is stale. Production uses `https://dietly.pl/api/auth/login`.

## Users and known quirks

- Two users in production: **Kamil Piotrowski** (the main one to keep working) and **Mateusz Góral**.
- Mateusz Góral's Dietly order (`order/9184`, caterer GRAMATURA) intermittently returns **HTTP 500** from Dietly. That's on Dietly's side; the script then logs "No active meal plan".
- GRAMATURA appends `ALERGENY … SKŁADNIKI …` to every dish name. Fitatu rejects product names over about 255 chars with a bare **400** on `POST /api/products`, so `clean_meal_name()` (`src/models/add_product_model.py`) strips that tail and caps the length. If 400s on product creation come back, check name length first.
- Dietly sits behind **Cloudflare + Spring Security**. Since 2026-10-13, login needs a **CSRF double-submit token**. `DietlyClient._fetch_xsrf_token()` makes a GET first to receive the `XSRF-TOKEN` cookie, and the token is sent back in the `X-XSRF-TOKEN` header on the POST. Without the token, login returns **403** even with valid credentials. A 403 on login means Dietly's auth flow changed again, not that the credentials are wrong; a wrong password gives 401 `Bad credentials`.
- The retry layers stack: in-process `RETRY_MAX_ATTEMPTS` × per-user transient retry × 3 workflow attempts. When login fails, that's about 18 login POSTs in a few seconds, and Dietly answers with **429**. Don't add more retries on 4xx.
- `categorize_error` puts any message containing "connection", "timeout" or a 5xx code into the `transient` category, and `transient` errors get retried. Keep that wording out of auth/4xx error messages so they land in `auth` instead and aren't retried.

## Rules

- **Never commit secrets.** That covers `config/users.yaml`, real emails/passwords, Fitatu `api_secret`, JWTs, and cookies. Production credentials live only in the Gitea repo secret `USERS_YAML` (and in the password manager).
- Branch → PR → user merges (squash). Never force-push.
- Avoid hammering Dietly/Fitatu from local debugging loops. Repeated logins trigger 429s that also hit the scheduled run.
