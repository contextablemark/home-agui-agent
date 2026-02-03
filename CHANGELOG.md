# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2025-02-03

### Added

- Bearer token authentication support for AG-UI endpoints
  - New optional "Bearer Token" field in configuration UI (masked as password)
  - Token is included as `Authorization: Bearer <token>` header in all outbound requests
  - Token is validated during endpoint connectivity test

## [0.1.0] - 2025-01-15

### Added

- Initial release
- AG-UI Protocol client for communicating with remote agents via SSE
- Home Assistant conversation entity integration
- Frontend tool execution (tools run locally in Home Assistant)
- Support for AG-UI event types: RUN_STARTED, TEXT_MESSAGE_*, TOOL_CALL_*, RUN_FINISHED, RUN_ERROR
- Configuration flow with endpoint URL and timeout settings
- Tool translation from Home Assistant LLM tools to AG-UI Tool format

[Unreleased]: https://github.com/contextablemark/home-agui-agent/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/contextablemark/home-agui-agent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/contextablemark/home-agui-agent/releases/tag/v0.1.0
