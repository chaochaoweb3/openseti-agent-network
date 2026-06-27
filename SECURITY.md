# Security Policy

## Supported Versions

This project is an early prototype. Security fixes apply to the `main` branch.

## Credential Boundary

OpenSETI Agent Network does not collect, proxy, or broker volunteer credentials.

- API keys must stay on the volunteer's machine or volunteer-owned deployment.
- Do not submit OAuth tokens, cookies, session IDs, authorization headers, or
  browser profile data.
- Do not automate web subscriptions as a remote shared proxy.

## Reporting A Vulnerability

Please open a private security advisory on GitHub if available. If not, open a
minimal public issue that describes the affected component without including
secrets or exploit details.

## Known Prototype Limits

The local coordinator is suitable for demo and trusted deployments. Public
production deployments should add authentication, HTTPS termination, rate
limiting, audit logging, and abuse monitoring.
