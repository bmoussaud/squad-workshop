# Application Development Standard

Python is the primary language for application development. Use `uv` where
applicable to manage the Python version and environment, project dependencies and
lockfile, and execution of application, test, and project-tool commands.

Use TOML for Python project and tool configuration, with `pyproject.toml` as the
canonical project configuration file. This standard does not require runtime
secrets or environment-specific deployment settings to be stored in TOML; use
environment variables, secret stores, and deployment-specific configuration when
those mechanisms are appropriate.

## CLI Environment Configuration

All CLI applications must load local environment configuration from `.env` at
their composition-root entry point with `python-dotenv`'s `load_dotenv()` before
reading environment-backed settings. Existing process environment variables keep
precedence over values loaded from the file.

For an `azd` environment, refresh local configuration from the repository root:

```bash
azd env get-values > .env
```

Treat `.env` as generated local runtime state: ignore it in Git, never read or
log its contents in automation, and regenerate it after Azure outputs change.