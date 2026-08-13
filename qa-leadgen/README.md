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
Includes a **registry of 165 job platforms** (100 remote boards + 65 overseas software sites across 36 countries):

```bash
python main.py platforms
python main.py platforms -g overseas_software
python main.py platforms --fetchable-only
```

- General remote, freelance/gig, tech-focused, startup, regional boards
- **Overseas software job boards** — USA, UK, Germany, France, India, Australia, Brazil, UAE, Japan, and more
- Employer-of-record platforms, large aggregators

**20+ platforms** have automated public feed/API adapters. Others are catalogued in the `Overseas Job Boards` Excel sheet — add career page URLs under `custom_career_pages` to fetch from them.

```bash
# List all 100 platforms and which are enabled
python main.py platforms

# Show only platforms with automated feeds
python main.py platforms --fetchable-only

# Filter by category
python main.py platforms -g freelance_gig
```

| Source | Method | API Key Required |
|--------|--------|-----------------|
| RemoteOK | Public API | No |
| We Work Remotely | RSS feed | No |
| Remotive | Public API | No |
| Himalayas.app | Public API | No |
| Working Nomads | Public API | No |
| EU Remote Jobs | RSS feed | No |
| Landing.jobs | Public API | No |
| Arbeitnow | Public API | No |
| Indeed | Publisher API | Yes (`INDEED_PUBLISHER_ID`) |
| Upwork | GraphQL API | Yes (OAuth token) |
| Wellfound | Public listings | No |
| LinkedIn Jobs | Public search (postings only) | No |
| Custom career pages | User-configured URLs | No |

Extracts: company, role, JD text, location, seniority, **employment type**, posting date, application link, and any public contact email in the posting. Deduplicates across sources.

### 2. Excel Export — Job Requirements Tracker
Columns: Company, Role, JD Summary, Location, Experience Level, **Employment Type**, Source, Contact Email, Posting Link, Date Found, Status.

**Workbook sheets:**
| Sheet | Contents |
|-------|----------|
| `All Jobs` | Master list (all unique jobs, deduplicated) |
| `YYYY-MM-DD` | One sheet per day with that day's scan results |
| `Daily Summary` | Date, jobs found, freelance count, top sources |
| `Overseas Job Boards` | 165 job platforms by country (reference directory) |
| `Company Directory` | Enriched company contacts (after `enrich` command) |

### 3. Company Contact Enrichment
For companies without a public contact in the posting, looks up publicly listed business info (Contact Us pages, mailto links). Does **not** scrape personal LinkedIn profiles.

When the company's website isn't known from the posting itself, it's guessed from the company name — so every guessed contact is cross-checked against the fetched page content (title/text must actually mention the company) before it's trusted. Guesses that can't be confirmed are still recorded in the Company Directory for manual review, marked `Verified: No`, and are **never** auto-used for outreach (see below).

### 4. Excel Export — Company Directory
Columns: Company, Website, Industry, Size, General Contact Email, **Verified**, Location, Enrichment Source.

`Verified: No` means the contact is a guess (unconfirmed domain, or an inferred `careers@domain`-style address) — check it manually before reaching out; the outreach command won't auto-select it.

### 5. Outreach Module
- Personalized email templates referencing the specific JD
- Interactive review/edit before each send — `send` / `edit` / `skip` / `block` / `quit`
- Only uses enrichment contacts that were confirmed to belong to the company (`Verified: Yes` in the Company Directory); unverified guesses are skipped automatically
- Persistent suppression (opt-out) list — `block` during review, or `python main.py suppress add`, permanently excludes a company/email from all future outreach, independent of which job posting it comes from
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
# Fetch QA jobs from all enabled sources (freelance/contract only by default)
python main.py fetch

# Include full-time QA roles too
python main.py fetch --all-qa

# List all 100 registered job platforms
python main.py platforms

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

# Suppression (opt-out) list — permanently excluded from outreach
python main.py suppress add --email jane@acme.com --reason "replied unsubscribe"
python main.py suppress add --company "Acme Inc"
python main.py suppress list
python main.py suppress remove --email jane@acme.com
```

### Telegram Reports (every 12 hours)

Send the Excel tracker to your Telegram chat automatically.

**Setup:**
1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the bot token
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot)
3. Add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```
4. Enable in `config.yaml`:
```yaml
telegram:
  enabled: true
  interval_hours: 12

automation:
  enabled: true
  scanning_on_boot: true    # auto-start 12h scanning when daemon starts
  run_on_boot: true         # fetch + send Excel immediately on start
```

**Commands:**
```bash
# Verify Telegram setup
python main.py telegram test

# Send Excel files now
python main.py telegram send

# Fetch fresh data, then send
python main.py telegram send --fetch-first

# Run continuously: fetch + send every 12 hours
python main.py telegram run

# Interactive bot — control scanning from Telegram chat
python main.py telegram bot

# Full automation (recommended) — runs everything in background
python main.py automate start     # Start daemon (bot + auto scanning + boot job)
python main.py automate status    # Check if running
python main.py automate stop      # Stop daemon
python main.py automate restart   # Restart daemon

# Or use helper scripts
./scripts/start_automation.sh
./scripts/stop_automation.sh
```

On boot the daemon will automatically:
1. Run an initial job scan + send Excel (if `automation.run_on_boot: true`)
2. Enable 12-hour scanning (if `automation.scanning_on_boot: true`)
3. Listen for Telegram commands (`/start`, `/stop`, `/scan`, etc.)

**GitHub Actions** (cloud automation without a server): add secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` — workflow runs every 12 hours.

**systemd** (Linux server): see `scripts/qa-leadgen.service`

**Telegram bot commands** (send these to your bot in chat):

| Command | Action |
|---------|--------|
| `/start` | Start automatic scanning every 12h + Excel delivery |
| `/stop` | Stop automatic scanning |
| `/scan` | Run a one-time job scan now |
| `/report` | Send current Excel files |
| `/scanreport` | Scan now, then send Excel |
| `/status` | Show scanning status and job counts |
| `/help` | List all commands |

**Cron alternative** (if you prefer system cron over a long-running process):
```cron
0 */12 * * * cd /path/to/qa-leadgen && python main.py telegram send --fetch-first
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
  linkedin_jobs: false   # set true to include LinkedIn public job search

platform_registry:
  auto_enable_feeds: true   # enable all platforms with public feeds/APIs
  groups: []                # or enable by category, e.g. [general_remote, freelance_gig]
  include: []               # explicitly enable platform IDs
  exclude: [flexjobs, fiverr, problogger, dribbble]

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
