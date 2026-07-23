# squad-workshop

This repository includes a development container that prepares the core workshop tools for the [Squad workshop prerequisites and setup](https://github.com/tamirdresher/squad-skills/tree/main/workshop#1-prerequisites--setup) and [Squad CLI installation](https://github.com/tamirdresher/squad-skills/tree/main/workshop#2-install-squad-cli).

## Included in the devcontainer

- Node.js 22
- GitHub CLI (`gh`)
- Git
- GitHub Copilot CLI support via `gh copilot` (built-in on recent `gh` releases, legacy extension installed only when needed)
- `@bradygaster/squad-cli` installed globally as `squad`
- VS Code recommendations for Copilot and Copilot Chat

## Use the devcontainer

1. Open this repository in VS Code.
2. Choose **Reopen in Container** when prompted.
3. Wait for the post-create step to finish verifying `gh copilot` support.
4. Authenticate GitHub CLI:

   ```bash
   gh auth login
   gh auth status
   ```

5. Verify the workshop tools:

   ```bash
   git --version
   gh --version
   gh copilot --help
   node --version
   squad --help
   ```

6. Initialize Squad in the repository when you are ready:

   ```bash
   squad init
   squad status
   ```

## Notes

- The devcontainer installs the required CLI tools, but you still need a GitHub account with GitHub Copilot access.
- The optional workshop tools such as PowerShell and MCP servers are not installed by default.

## Run the Python application locally

The application requires Python 3.11 or newer. It uses the offline, in-memory image generator by default, so local runs do not need Azure credentials or network access.

```bash
uv sync
uv run fantasy-card "Ember Sentinel" "A knight made of living flame"
```

The command prints a completed job record with correlation, idempotency, generator provenance, and artifact metadata. The in-memory generator creates a text demonstration artifact.

Generated files are written to the `artifacts/` directory by default. Each filename contains the artifact UUID and uses an allowlisted extension based on its media type (`.png` for `image/png`, `.txt` for `text/plain`, and `.bin` otherwise). Set `FANTASY_CARD_OUTPUT_DIR` to write artifacts elsewhere:

```bash
export FANTASY_CARD_OUTPUT_DIR="/path/to/generated-cards"
```

The job JSON includes the persisted file location in `artifact.file_path`.

### Use an existing Microsoft Foundry deployment

Foundry image generation is opt-in and uses Microsoft Entra authentication. Configure an existing GPT-image deployment at runtime:

```bash
azd env get-values > .env
printf '\nFANTASY_CARD_IMAGE_GENERATOR=foundry\n' >> .env
azd auth login
uv run fantasy-card "Ember Sentinel" "A knight made of living flame"
```

The CLI loads `.env` with `python-dotenv`. Existing shell variables take precedence, and `.env` is generated local state excluded from Git. Regenerate it after provisioning changes the `azd` outputs.

`FANTASY_CARD_IMAGE_TIMEOUT_SECONDS` is optional and must be between 1 and 120 seconds. The client does not automatically retry image generation because a retry can duplicate provider charges.

Set `AZURE_OPENAI_ENDPOINT` to the exact inference endpoint for the resource that owns the named deployment. The application accepts valid `*.services.ai.azure.com/openai/v1` and `*.openai.azure.com/openai/v1` endpoint families, but it does not translate one hostname family into the other. An endpoint and deployment from different resources can produce `500 Unable to get resource information` from the service.

The runtime identity needs the **Cognitive Services OpenAI User** role on the Azure OpenAI resource. Local development can use an authenticated Azure CLI session. In Azure, `DefaultAzureCredential` automatically uses managed identity; set `AZURE_CLIENT_ID` when selecting a user-assigned managed identity. Endpoints, deployment names, and credentials remain runtime configuration and must not be committed.

Run the tests with:

```bash
uv run python -m unittest discover -s tests -v
```

## Validate changes locally

Run the same validation gates as CI from the repository root, in this order:

```bash
test -z "$(find . -path './.git' -prune -o -path './.venv' -prune -o -type d -name '*.egg-info' -print -quit)"
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
uv lock --check
git diff --check
```

The generated-package residue check runs before environment synchronization so it inspects the checked-out repository rather than build output created by tooling.
