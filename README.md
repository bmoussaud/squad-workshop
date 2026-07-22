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
