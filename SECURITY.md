# Security policy

## Scope

This policy covers the CIEL Canvas source tree and the release assets published from this repository.

## Reporting

Do not open a public issue for secrets, personal data, or an exploitable vulnerability. Contact the repository owner privately through the GitHub security advisory mechanism when available, or use the private contact channel configured on the repository profile.

Include the affected file or release asset, reproduction steps, impact, and a minimal proof of concept. Do not include API keys, access tokens, UserData, logs containing personal data, or other credentials.

## Release hygiene

Release archives are GitHub Release assets and must not be committed to Git history. Before publishing, scan source, configuration, archives, and generated output for credentials, local paths, diagnostics, user data, and caches. API keys are user-provided configuration and are never bundled by this project.

