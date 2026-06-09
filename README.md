<div align="center">
  <img src="app/static/brand/logos/mark.png" alt="InfusionFox" width="120">

  # InfusionFox

  **Cited. Calculated. Confirmed.**

  Open-source veterinary CRI calculator and clinical reference for licensed veterinary professionals.

  [infusionfox.com](https://infusionfox.com) · [Disclaimer](https://infusionfox.com/disclaimer) · [Install on phone](https://infusionfox.com/install) · [support@infusionfox.com](mailto:support@infusionfox.com)
</div>

---

## What it is

InfusionFox is a focused clinical reference tool that helps veterinarians and credentialed veterinary technicians prepare and titrate continuous-rate infusions, interpret blood gases and electrolyte derangements, and apply published scoring systems at the point of care. Every dose, rate, and recommendation traces back to a primary source, typically Plumb's, Silverstein & Hopper *Small Animal Critical Care Medicine*, Lumb & Jones, DiBartola, or peer-reviewed primary literature.

The tool is free for clinical use. It does not collect personal data, run analytics, or display advertising.

## Who it is for

Licensed veterinarians, registered veterinary technicians, and veterinary students working under licensed supervision. The calculators assume the user knows their patient, has access to current formularies, and will verify every dose before administration. InfusionFox is educational; it does not replace clinical judgment, licensure, or current standard of care.

If you are not a licensed veterinary professional, this tool is not for you.

## What's inside

Currently 50+ calculators and clinical reference tools across the following categories:

- **Emergency hubs**: anaphylaxis, DKA, heatstroke, hyperkalemia emergency, hypoglycemia, shock, status epilepticus
- **Analgesia**: fentanyl, hydromorphone, lidocaine, ketamine, methadone, MLK, Kitty Magic
- **Anesthesia & sedation**: propofol, alfaxalone, anesthesia worksheet, Cornell oncology KL infusion
- **Vasopressors & inotropes**: norepinephrine, epinephrine, dobutamine, dopamine, phenylephrine, vasopressin, nitroprusside
- **Antiarrhythmics**: lidocaine antiarrhythmic, esmolol, diltiazem
- **Electrolytes & fluids**: fluid therapy, hypernatremia, hypokalemia, hypomagnesemia, hypophosphatemia, mannitol osmotherapy, calcium gluconate, insulin + dextrose
- **Acid-base & blood gas**: basic blood gas interpretation, Stewart strong-ion approach, osmolar gap, P:F ratio + A-a gradient
- **Endocrine & metabolic**: Addison's pretest, Cushing's score, hypothyroid score, IRIS staging, LDDST, APPLE-fast, APPLE-full
- **Other**: methocarbamol, metoclopramide, furosemide CRI, intravenous lipid emulsion (ILE), tube feeding, energy requirements, transfusion volume

All clinical content is cited. See [`SOURCES.md`](SOURCES.md).

## Live deployment

The canonical hosted version runs at [infusionfox.com](https://infusionfox.com). It is mobile-friendly and installable as a Progressive Web App on iOS and Android (see [/install](https://infusionfox.com/install)).

## Reporting clinical concerns

If you find an incorrect dose, a missing or wrong citation, or content you believe is unsafe, please report it. There are three channels:

1. **Feedback button** on any page of infusionfox.com
2. **Email** [support@infusionfox.com](mailto:support@infusionfox.com)
3. **GitHub issue** using the Dose correction template

Clinical concerns are triaged first. We try to acknowledge within 24 hours and ship a fix within 72 hours when the issue is clear-cut.

## Self-hosting

InfusionFox is a Python web application built on FastAPI, Jinja2, HTMX, and SQLite. It is designed to run as a single process behind a reverse proxy (Caddy, nginx, Cloudflare Tunnel). Self-hosting is supported under the AGPL-3.0 license; if you run a modified version, you must publish your modifications.

### Quick start (development)

Requires Python 3.12+.

```bash
git clone https://github.com/infusionfox/infusionfox.git
cd infusionfox
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

The app will be available at [http://localhost:8000](http://localhost:8000). The feedback widget and admin disclaimer-acceptances tracker require database tables created by Alembic migrations, so `alembic upgrade head` is required for those features to work.

### Production

Production-tested deployment uses Cloudflare Tunnel in front of the FastAPI app running under a systemd-managed uvicorn process. Uptime Kuma handles monitoring. Versioning is calendar-based and manual: tagged GitHub releases are cut by hand, with no automatic update mechanism by design (clinical software should not silently update).

## Contributing

Corrections, new calculators, and improvements are welcome. [`CONTRIBUTING.md`](CONTRIBUTING.md) covers:

- How to file a dose correction (the most important kind of contribution)
- How to propose a new calculator
- Code style, testing requirements, and the citation rule
- Pull request workflow

Code contributions require all tests to pass (`pytest`) and lint to be clean (`ruff check`). Clinical content contributions require at least one primary source citation per claim.

## Security

To report a security vulnerability, email [support@infusionfox.com](mailto:support@infusionfox.com) with the subject line "Security disclosure". See [`SECURITY.md`](SECURITY.md) for the coordinated disclosure policy and response timeline.

Please do NOT report security issues via public GitHub issues.

## License

Licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0). See [`LICENSE`](LICENSE) for the full text.

This means: you may use, modify, and redistribute InfusionFox. If you run a modified version on a server accessible to others (a SaaS deployment, a hospital intranet, etc.), you must make your modifications available to the users of that service. Copyleft applies to network use.

## Acknowledgments

InfusionFox stands on decades of veterinary critical care scholarship. Particular acknowledgment to the authors and editors of Plumb's Veterinary Drugs, Silverstein & Hopper's *Small Animal Critical Care Medicine*, Lumb & Jones' *Veterinary Anesthesia and Analgesia*, DiBartola's *Fluid, Electrolyte, and Acid-Base Disorders*, and the RECOVER initiative. The tool is a synthesis of their work, made queryable at the point of care.

Built and maintained by Timothy Curran, DVM. Single author, single maintainer, accountable to every veterinarian who uses it.
