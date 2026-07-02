# Publishing

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
