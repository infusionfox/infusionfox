# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in InfusionFox, please report it privately. Do NOT file a public GitHub issue, post on social media, or discuss the issue in public forums until we've had a chance to address it.

**Email: [support@infusionfox.com](mailto:support@infusionfox.com)**
**Subject line: "Security disclosure"**

Include:

- A description of the vulnerability
- Steps to reproduce, if applicable
- Affected version(s): calendar date or git commit hash works
- Impact assessment (what could an attacker do with this?)
- Any proof-of-concept code, screenshots, or logs

If the vulnerability involves user data or could affect clinical decision-making (e.g., a way to manipulate displayed doses, inject content into the disclaimer, or bypass safety warnings), say so prominently. We treat those with the highest priority.

## What to expect

| Step | Timeline |
|---|---|
| Acknowledgment of your report | Within 48 hours, usually within 24 |
| Initial assessment and severity rating | Within 5 business days |
| Patch development | Depends on severity; critical issues within 7 days |
| Coordinated disclosure | After a fix is deployed, mutually agreed timeline |
| Public credit (if you want it) | In the changelog and a CVE/GHSA if applicable |

## Scope

In scope for security disclosure:

- The hosted application at infusionfox.com
- The code in this repository
- The DNS/email configuration for infusionfox.com
- Any official InfusionFox subdomain or service

Out of scope:

- Self-hosted forks or modifications by third parties (those are the responsibility of whoever runs them, per the AGPL-3.0)
- Vulnerabilities in dependencies that don't affect InfusionFox in practice (we still want to know about them, but please file them with the upstream maintainer)
- Theoretical issues without practical exploitation paths
- Social engineering, physical access to the maintainer's hardware, or DoS-via-resource-exhaustion against a single FastAPI process

## Disclosure philosophy

We follow coordinated disclosure: we work with you on a reasonable timeline to fix the issue before it becomes public. Once a patch is deployed, we credit the reporter (with their permission) and publish a brief advisory describing what was fixed and what the impact was. The advisory does not include exploitation details until enough time has passed for downstream self-hosted instances to update.

We will not pursue legal action against good-faith security researchers who follow this policy. If you believe you found something and you're not sure whether to report it, err on the side of reporting.

## A note on clinical impact

InfusionFox is used to support clinical decision-making in veterinary patients. A vulnerability that could cause incorrect doses to be displayed, that could let an attacker modify drug content shown to users, or that could undermine the audit trail in the disclaimer acceptance log is treated as a **critical** issue regardless of its technical novelty. If you find something in that category, mention "clinical safety impact" in your initial email and we will prioritize accordingly.

Thank you for helping keep InfusionFox safe.
