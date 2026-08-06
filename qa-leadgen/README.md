# QA Staffing Lead-Gen & Outreach Tool

A compliant Python tool for QA staffing lead generation and personalized outreach. It aggregates QA/testing job postings from public job boards and APIs, exports trackers to Excel, enriches company contact info from public business sources, and supports review-before-send email outreach with CAN-SPAM/GDPR compliance features.

## Compliance Notes

- **No LinkedIn profile scraping** — only public job postings where available
- **Public data sources only** — job board APIs, RSS feeds, and user-specified career pages
- **Review before send** — every email is shown for your approval; no blind mass-send
- **Opt-out language** included in every template
- **Rate limiting** — configurable daily send cap (default 45/day)

## Features

### 1. Job Requirement Aggregator
Pulls QA/testing jobs from:
| Source | Method | API Key Required |
|--------|--------|-----------------|
| RemoteOK | Public API | No |
| We Work Remotely | RSS feed | No |
| Remotive | Public API | No |
| Indeed | Publisher API | Yes (`INDEED_PUBLISHER_ID`) |
| Upwork | GraphQL API | Yes (OAuth token) |
| Wellfound | Public listings | No |
| LinkedIn Jobs | Public search (postings only) | No |
| Custom career pages | User-configured URLs | No |

Extracts: company, role, JD text, location, seniority, posting date, application link, and any public contact email in the posting. Deduplicates across sources.

### 2. Excel Export — Job Requirements Tracker
Columns: Company, Role, JD Summary, Location, Experience Level, Source, Contact Email, Posting Link, Date Found, Status (New/Contacted/Responded/Closed).

### 3. Company Contact Enrichment
For companies without a public contact in the posting, looks up publicly listed business info (Contact Us pages, mailto links). Does **not** scrape personal LinkedIn profiles.

### 4. Excel Export — Company Directory
Columns: Company, Website, Industry, Size, General Contact Email, Location.

### 5. Outreach Module
- Personalized email templates referencing the specific JD
- Interactive review/edit before each send
- Unsubscribe/opt-out line and your real contact info
- Tracks sent status back to the Excel tracker
- Rate-limited sending (configurable, default 45/day)
- Supports SMTP, SendGrid, and Mailgun

## Quick Start

```bash
cd qa-leadgen
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp config.example.yaml config.yaml
cp .env.example .env
# Edit config.yaml with your name, email, and preferences
```

### Commands

```bash
# Fetch QA jobs from all enabled sources
python main.py fetch

# Enrich company contacts for jobs missing email
python main.py enrich

# Review and send outreach emails (interactive)
python main.py outreach

# Dry-run outreach (preview without sending)
python main.py outreach --dry-run

# Show stats
python main.py stats

# Full pipeline: fetch → enrich → outreach
python main.py run-all
```

## Configuration

Edit `config.yaml`:

```yaml
user:
  name: "Jane Doe"
  email: "jane@example.com"
  phone: "+1-555-0100"
  website: "https://janedoe.dev"

sources:
  remoteok: true
  weworkremotely: true
  remotive: true
  indeed: false          # set INDEED_PUBLISHER_ID in .env
  custom_career_pages:
    - "https://careers.your-target-company.com"

email:
  provider: "smtp"       # smtp | sendgrid | mailgun
  daily_limit: 45
```

## Output Files

All outputs go to `./data/`:
- `job_requirements_tracker.xlsx` — main job tracker
- `company_directory.xlsx` — enriched company contacts
- `outreach_tracker.json` — send log
- `send_rate.json` — daily rate limit state

## Tech Stack

- Python 3.10+
- requests + BeautifulSoup (permitted public sources)
- pandas + openpyxl (Excel export)
- smtplib / SendGrid / Mailgun (email sending)
- click + rich (CLI and interactive review)

## License

MIT
