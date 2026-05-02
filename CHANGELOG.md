## [0.7.0](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.6.0...v0.7.0) (2026-05-02)

### 🚀 Features

* **cleanup-manager:** added scheduled cleanup sidecar service ([f30b5fa](https://github.com/bauer-group/CI-GitHubRunner/commit/f30b5fad04163ef4103e46a590b8cffd2914f9f0))
* **workflows:** added scheduled cleanup-runners workflow ([361924b](https://github.com/bauer-group/CI-GitHubRunner/commit/361924b0f215a43d462a67c79cc9a21b000f50ae))

### 🐛 Bug Fixes

* **compose:** increased stop_grace_period for graceful deregister ([645f007](https://github.com/bauer-group/CI-GitHubRunner/commit/645f0079a4991cd03989bff99d4697b58a80882b))

### ⏪ Reverts

* removed scheduled cleanup-runners workflow ([bbba1e3](https://github.com/bauer-group/CI-GitHubRunner/commit/bbba1e313005f59f571bb6514fc026a10228ce00))

## [0.6.0](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.5.0...v0.6.0) (2026-05-02)

### 🚀 Features

* **cleanup-runners:** adaptive pacing from X-RateLimit headers ([bcfd895](https://github.com/bauer-group/CI-GitHubRunner/commit/bcfd8957191c27122353cf48b0ec29c8001fdb09))

## [0.5.0](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.4.2...v0.5.0) (2026-05-02)

### 🚀 Features

* **scripts:** added cleanup-runners.py for mass offline-runner removal ([d10d1e1](https://github.com/bauer-group/CI-GitHubRunner/commit/d10d1e159aa9d6c947dbbbd37e1e1c007d25e051))

## [0.4.2](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.4.1...v0.4.2) (2026-05-02)

### 🐛 Bug Fixes

* **cleanup:** replaced host-wide image/builder prune with stack-scoped down ([1a07d70](https://github.com/bauer-group/CI-GitHubRunner/commit/1a07d70d9504e9a71eff891d4f59176809db33ad))

## [0.4.1](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.4.0...v0.4.1) (2026-05-02)

### 🐛 Bug Fixes

* **cleanup:** scoped volume removal strictly to this compose project ([b00a95f](https://github.com/bauer-group/CI-GitHubRunner/commit/b00a95fefaf5301d719da765ab80dc83191cd1cf))

### ♻️ Refactoring

* **compose:** renamed watchtower profile to auto-update ([ddc27d3](https://github.com/bauer-group/CI-GitHubRunner/commit/ddc27d3e8f997782a158f7e26b8d20ba1ce9060e))

## [0.4.0](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.3.11...v0.4.0) (2026-05-02)

### 🚀 Features

* **compose:** added optional watchtower auto-update profile ([e3a2ada](https://github.com/bauer-group/CI-GitHubRunner/commit/e3a2adae40be24dea91516a7e36b8a13bef79e8c))

## [0.3.11](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.3.10...v0.3.11) (2026-01-14)


### Bug Fixes

* Aktualisiere Container-Namen im Docker-Compose und korrigiere GitHub-URL in Skripten ([da53158](https://github.com/bauer-group/CI-GitHubRunner/commit/da531580f5a97fc26e9d75a2b600f388ca69321e))

## [0.3.10](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.3.9...v0.3.10) (2026-01-14)


### Bug Fixes

* Aktualisiere Umgebungsvariablen und Hinweise zur GitHub App Authentifizierung in .env, README und Docker-Compose-Dateien ([6e1554e](https://github.com/bauer-group/CI-GitHubRunner/commit/6e1554ec1b9dc430d23fb353b58788e1d7455142))

## [0.3.9](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.3.8...v0.3.9) (2026-01-14)


### Bug Fixes

* Aktualisiere den Pfad zur APP_PRIVATE_KEY in der Konfiguration und verbessere die Dokumentation ([ae2e249](https://github.com/bauer-group/CI-GitHubRunner/commit/ae2e249dab55b5e49344281689f0ccefd68994f9))
* Füge Warnmeldungen hinzu, wenn die PEM-Datei für APP_ID nicht gefunden wird und wechsle zu ACCESS_TOKEN-Authentifizierung ([93c5e1d](https://github.com/bauer-group/CI-GitHubRunner/commit/93c5e1d0d6cedec8487316f71511faec6670cd3f))

## [0.3.8](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.3.7...v0.3.8) (2026-01-14)


### Bug Fixes

* Aktualisiere die Handhabung des APP_PRIVATE_KEY in der Konfiguration und verbessere die Dokumentation ([4752d8a](https://github.com/bauer-group/CI-GitHubRunner/commit/4752d8abfccae24e596074a598890cd4bb73e77c))
* Implement GitHub App authentication support and update configuration files ([bb63db0](https://github.com/bauer-group/CI-GitHubRunner/commit/bb63db0628f0e168c085a985c7a2bb5be825ebda))

## [0.3.7](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.3.6...v0.3.7) (2026-01-14)


### Bug Fixes

* Aktualisiere den App-Namen und die Beschreibung für die GitHub App-Generierung ([82c1e41](https://github.com/bauer-group/CI-GitHubRunner/commit/82c1e41edd1ca2bf439b89100cbf5c2f4102c6c7))
* Aktualisiere die URL des GitHub-Repositories in der Konfiguration und verbessere die App-Beschreibung ([ca0f7db](https://github.com/bauer-group/CI-GitHubRunner/commit/ca0f7db9d4e3a94cf1f2caac9907c271a10f6e49))

## [0.3.6](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.3.5...v0.3.6) (2026-01-14)


### Bug Fixes

* Aktualisiere die Generierung des Redirect-HTML zur sicheren Einbettung des Manifests ([3893c8c](https://github.com/bauer-group/CI-GitHubRunner/commit/3893c8cad9d88c0cc31b776e09aee61d2aab7f23))

## [0.3.5](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.3.4...v0.3.5) (2026-01-14)


### Bug Fixes

* Aktualisiere das Styling und die Manifest-Generierung im GitHub App-Setup ([95524d6](https://github.com/bauer-group/CI-GitHubRunner/commit/95524d66733e2984490ed363b1277b91f03966a8))

## [0.3.4](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.3.3...v0.3.4) (2026-01-14)


### Bug Fixes

* Entferne die Speicherung und Bereinigung der URL-Datei im GitHub App-Setup ([3ea2705](https://github.com/bauer-group/CI-GitHubRunner/commit/3ea27050aa91eeae8838072abfa3c37ebfd1cbda))

## [0.3.3](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.3.2...v0.3.3) (2026-01-14)


### Bug Fixes

* Aktualisiere das Styling der GitHub App-Bestätigungsseite und verbessere die HTML-Sicherheit ([be85384](https://github.com/bauer-group/CI-GitHubRunner/commit/be8538428379841d32990b75b71d3dce02cc28fc))
* Füge automatische Umleitung zur GitHub-App-Erstellung hinzu ([c2e0c29](https://github.com/bauer-group/CI-GitHubRunner/commit/c2e0c291bd69288e71b9a5981571af896462237d))

## [0.3.2](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.3.1...v0.3.2) (2026-01-14)


### Bug Fixes

* Füge Unterstützung für GitHub App-URL-Speicherung und SSH-Port-Forwarding hinzu ([60d6aa2](https://github.com/bauer-group/CI-GitHubRunner/commit/60d6aa2ce6478ae95eba537736d4e04797de635b))

## [0.3.1](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.3.0...v0.3.1) (2026-01-14)


### Bug Fixes

* Aktualisiere Ressourcengrenzen für DinD und entferne überflüssige Limits für Runner-Agenten ([214c940](https://github.com/bauer-group/CI-GitHubRunner/commit/214c9405fe7d62acbe08ad5478c1b4d2b98652d4))

# [0.3.0](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.2.0...v0.3.0) (2026-01-14)


### Bug Fixes

* Entferne veraltete Skripte zur Verwaltung des GitHub Runners ([09f57ca](https://github.com/bauer-group/CI-GitHubRunner/commit/09f57ca6ed6670d14861bc3c50a3b02ed962e2ab))


### Features

* Introduce unified runner management script and enhance setup process ([31b3b5e](https://github.com/bauer-group/CI-GitHubRunner/commit/31b3b5e67c5bf2103649ed5fc345c343212210ae))

# [0.2.0](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.1.3...v0.2.0) (2026-01-13)


### Features

* Add create-github-app.sh script and update documentation for GitHub App setup ([080fc60](https://github.com/bauer-group/CI-GitHubRunner/commit/080fc609e0de2c689aab2d75f0b8217fdcdd4c37))

## [0.1.3](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.1.2...v0.1.3) (2026-01-13)


### Bug Fixes

* Add deployment script and update documentation for setup ([205fe0a](https://github.com/bauer-group/CI-GitHubRunner/commit/205fe0a24758a87abc781a9683b360367b9e417e))

## [0.1.2](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.1.1...v0.1.2) (2026-01-13)


### Bug Fixes

* Update configuration for organization and repository runners ([34e50e0](https://github.com/bauer-group/CI-GitHubRunner/commit/34e50e08ed689f467060e239a912cdd31f2ce080))

## [0.1.1](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.1.0...v0.1.1) (2026-01-13)


### Bug Fixes

* Updated Repo URL's ([e4a0583](https://github.com/bauer-group/CI-GitHubRunner/commit/e4a05836bb7a306af69770ba34840e45f14d6ed7))

# [0.1.0](https://github.com/bauer-group/CI-GitHubRunner/compare/v0.0.0...v0.1.0) (2026-01-13)


### Features

* Initial Commit ([91ecafe](https://github.com/bauer-group/CI-GitHubRunner/commit/91ecafeedc6c875f982e4894f5b38b540d18d0e1))
