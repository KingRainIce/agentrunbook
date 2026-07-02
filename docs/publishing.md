# Publishing

AgentRunbook is prepared for PyPI publishing, but a local upload requires PyPI credentials. If you see `Credential not found for API token`, configure a PyPI API token or use Trusted Publishing through GitHub Actions.

Build and verify the package:

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

Manual PyPI upload requires a project-scoped or account API token:

```bash
python -m twine upload dist/*
```

The repository also includes `.github/workflows/publish.yml` for PyPI Trusted Publishing. Configure a PyPI trusted publisher with:

- Owner: `KingRainIce`
- Repository: `agentrunbook`
- Workflow: `publish.yml`
- Environment: leave empty unless you add one to the workflow

Then publish by creating a GitHub release or manually running the Publish workflow.

## Recommended Release Flow

1. Confirm CI is green on `main`.
2. Update the version in `pyproject.toml` and `src/agentrunbook/__init__.py`.
3. Run local checks:

```bash
python -m unittest discover -s tests
python -m build
python -m twine check dist/*
```

4. Commit the version bump.
5. Create a GitHub release, for example `v0.1.0`.
6. Let the Publish workflow upload the package to PyPI.

## Manual Upload

Set a PyPI token:

```bash
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="pypi-..."
python -m twine upload dist/*
```

PowerShell:

```powershell
$env:TWINE_USERNAME="__token__"
$env:TWINE_PASSWORD="pypi-..."
python -m twine upload dist\*
```
