# Validation scope

The public source has its own tests and must be validated independently of any earlier installation.

The automated suite uses temporary databases, synthetic source documents/images, mocked model deletion and authenticated loopback HTTP fixtures. macOS tests check the generated policies, including symlink aliases. No personal model, file or conversation is deleted by tests.

CI runs on macOS with Python 3.12 and Node.js 22. The workflow file is provided; a passing local run does not imply GitHub Actions has already run or that branch protection is active.

Model weights and OpenCode are not downloaded by CI. Actual model inference and task-engine smoke checks require separately installed engines and must be reported with the selected versions. Vision-model availability and parser support do not mean every provider/model combination has been tested.

See SECURITY.md for the known OpenCode permission-metadata compatibility issue and other boundaries. This alpha is not a multi-user service, OS-wide malware defense, training pipeline, or hosted product.

## Local source-preview validation

- Installed the pinned dependencies in a new Python 3.12 virtual environment from the package registry.
- Started UI and task services with a fresh external data directory and unused ports; existing application services were not reused.
- Authenticated HTTP checks confirmed an initially empty conversation database and empty approved memory.
- Local text inference with qwen2.5:7b-instruct returned the requested synthetic response.
- The isolated OpenCode 1.19.4 task engine selected the local model and completed a no-tool synthetic task. Its initial custom agent configuration was empty.
- Text, DOCX, PDF and synthetic image normalization are covered by parser tests. The public default vision model was not downloaded or exercised end-to-end during this preparation.
- Unit/security tests, JavaScript checks and the public source audit must all pass before the archive is built. The packaging check is repeated against the extracted archive.

GitHub CI, real branch protection, repository secret scanning and a public release have not been activated by this local preparation. Those require the chosen repository and authorized maintainers.
