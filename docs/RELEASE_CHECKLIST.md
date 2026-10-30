# Source release checklist

- [ ] Confirm the license, project name and ownership of contributed code/assets.
- [ ] Use only this new repository. Never add the original workstation tree or its Git history.
- [ ] Install from an extracted source ZIP in a fresh virtual environment.
- [ ] Run tests, syntax checks and the public-content audit.
- [ ] Verify runtime data, engine HOME, passwords and API keys are created outside the checkout.
- [ ] Confirm local mode does not require an online account and model downloads are explicit.
- [ ] Inspect `PUBLIC_FILES.json` and every archive entry. Review new files before updating the allowlist.
- [ ] Verify no commercial font, real screenshot, profile, transcript, API key, author email or filesystem identity is present.
- [ ] Document which model/engine versions were actually exercised; do not transfer claims from a private development installation to untested defaults.
- [ ] Choose real maintainers, commit CODEOWNERS, require CI and code-owner approval on main, and verify enforcement on GitHub.
- [ ] Enable a private security reporting channel and fork-workflow approval settings.
- [ ] Run `python scripts/build_release.py /path/outside/source/localdesk-source.zip` and retain the checksum.
- [ ] Obtain a maintainer's release review before publishing the alpha tag and assets.

No signed/notarized standalone macOS binary is supplied by this source preview. A locally generated `.app` launcher is tied to its user's installation and must not be uploaded as a portable binary.
