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

The initial application is a provider-neutral, in-memory generation path. It requires Python 3.11 or newer and has no runtime dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
fantasy-card "Ember Sentinel" "A knight made of living flame"
```

The command prints a completed job record with correlation, idempotency, generator provenance, and artifact metadata. The in-memory generator creates a text demonstration artifact; no image provider or Azure service has been selected.

Run the tests with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
