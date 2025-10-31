# Changelog

## [0.1.2](https://github.com/Berghmans/yk-daemon/compare/v0.1.1...v0.1.2) (2025-10-31)


### Bug Fixes

* ensure consistent config file loading across all entry points ([#29](https://github.com/Berghmans/yk-daemon/issues/29)) ([7e7e357](https://github.com/Berghmans/yk-daemon/commit/7e7e357109e28fd82602934ea2c04ca3d5f698a4)), closes [#28](https://github.com/Berghmans/yk-daemon/issues/28)

## [0.1.1](https://github.com/Berghmans/yk-daemon/compare/v0.1.0...v0.1.1) (2025-10-30)


### Bug Fixes

* implement flexible account name matching for AWS ARN prefixes ([#26](https://github.com/Berghmans/yk-daemon/issues/26)) ([41a5d39](https://github.com/Berghmans/yk-daemon/commit/41a5d395ac0f5f32c311f5961785f60ec609e8a7))

## 0.1.0 (2025-10-18)


### Features

* add GitHub Actions CI/CD workflows and release automation ([#12](https://github.com/Berghmans/yk-daemon/issues/12)) ([2eba98b](https://github.com/Berghmans/yk-daemon/commit/2eba98b7c2e57703ff3b9b783fddc06ccce351ff))
* add WSL client examples with bash script using curl and netcat ([#20](https://github.com/Berghmans/yk-daemon/issues/20)) ([55449aa](https://github.com/Berghmans/yk-daemon/commit/55449aa5e7114d32ca3d695abacd60704fb9b9c8))
* implement configuration management module ([#15](https://github.com/Berghmans/yk-daemon/issues/15)) ([0e7fa0a](https://github.com/Berghmans/yk-daemon/commit/0e7fa0aad17516b09b36c4983b521e6f99659d96)), closes [#4](https://github.com/Berghmans/yk-daemon/issues/4)
* implement main daemon entry point with orchestration ([#19](https://github.com/Berghmans/yk-daemon/issues/19)) ([366d17a](https://github.com/Berghmans/yk-daemon/commit/366d17a43fbe9ae9fd3cb0017acd65611be6db15))
* implement REST API server ([#16](https://github.com/Berghmans/yk-daemon/issues/16)) ([9362500](https://github.com/Berghmans/yk-daemon/commit/9362500af2a6c842cd911472144b52521d064d2e))
* implement TCP socket server for low-latency TOTP requests ([#18](https://github.com/Berghmans/yk-daemon/issues/18)) ([d31e8f9](https://github.com/Berghmans/yk-daemon/commit/d31e8f96543ac1905ae90d3968061ac21e33615a)), closes [#6](https://github.com/Berghmans/yk-daemon/issues/6)
* implement Windows notifications ([#17](https://github.com/Berghmans/yk-daemon/issues/17)) ([9cca668](https://github.com/Berghmans/yk-daemon/commit/9cca668b9d10e17b24357a110e5032035c7895bb))
* implement Windows service wrapper ([#21](https://github.com/Berghmans/yk-daemon/issues/21)) ([e968ae1](https://github.com/Berghmans/yk-daemon/commit/e968ae19394c7b6c46ba6aa86d12c89f05917107))
* implement YubiKey OATH-TOTP integration ([#14](https://github.com/Berghmans/yk-daemon/issues/14)) ([0013078](https://github.com/Berghmans/yk-daemon/commit/001307894e043ba48086b00c9aac9e9f7f6a52fa))
* setup Poetry configuration and project structure ([f4418c5](https://github.com/Berghmans/yk-daemon/commit/f4418c543d85b49f5eedc2b1d1d5fd623f2a5175))
* setup Poetry configuration and project structure ([3e928fe](https://github.com/Berghmans/yk-daemon/commit/3e928fe684aec21ca6ad2f2517b02a00eb2c4b73)), closes [#2](https://github.com/Berghmans/yk-daemon/issues/2)
* use GitHub App token for release-please workflow ([1b146e4](https://github.com/Berghmans/yk-daemon/commit/1b146e44032b2ed3c625d1e68ba869031535b3f9))


### Bug Fixes

* update default ports from 5000/5001 to 5100/5101 ([#23](https://github.com/Berghmans/yk-daemon/issues/23)) ([7229e9f](https://github.com/Berghmans/yk-daemon/commit/7229e9f9061c902b4964addd1bee94c4902c533e)), closes [#22](https://github.com/Berghmans/yk-daemon/issues/22)
* update release-please to correct action and remove invalid parameter ([46ee50d](https://github.com/Berghmans/yk-daemon/commit/46ee50d8b62e8786af9079577d72002e4ec35944))


### Documentation

* add initial project documentation ([e6bec70](https://github.com/Berghmans/yk-daemon/commit/e6bec70b067c30f0e3ec29c3fd36632d0fd9809b))
