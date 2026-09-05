# White Studio implementation plan

Goal: rebuild Axiom Street as a restrained, light research workspace while preserving real research workflows and existing uncommitted work.

Architecture: Next.js route entries compose feature components; shared visual primitives own appearance; domain API modules share one HTTP transport and type contract. A runtime same-origin gateway connects FastAPI, including event streams and downloads. Python domain boundaries stay intact.

User direction: white/light palette, Apple-like refinement, selective glass, autonomous execution, conserve quota. This supersedes the previous dark-theme/small-radius design rules.

- [x] Transport: test error handling, proxy verbs/status/body/query/streams; split the API by domain with a compatible barrel; configure Docker runtime origin.
- [x] Design foundation: tokens, original vector monogram, responsive shell, navigation, command/search, shared controls and feedback states.
- [x] Workspace: rebuild overview, strategy and backtest collections; preserve functional editor, validation and data flows; move route-level business views into features.
- [x] Quality: frontend tests/typecheck/lint/build, backend regression tests, browser verification at desktop and mobile sizes, real API integration against an isolated local database.
- [x] Documentation: current directory map, design system, startup instructions and API integration contract; record verified limits.

Validation: existing Vitest suite plus focused HTTP/gateway regression tests; Python unit suite; production build; browser screenshots and core navigation/create/edit flows. Never seed invented financial results for presentation.
