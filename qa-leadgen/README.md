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
Includes a **registry of 100 remote/overseas job platforms** (see `platforms/platforms.yaml`), grouped by type:

- General remote job boards (We Work Remotely, RemoteOK, Himalayas, Working Nomads, etc.)
- Freelance/gig marketplaces (Upwork, Fiverr, Freelancer.com, Toptal, etc.)
- Tech-focused (Wellfound, Dice, Turing, Lemon.io, etc.)
- Startup, region-specific, writing, design, customer support, marketing
- Employer-of-record platforms (Deel, Remote.com, Oyster, etc.)
- Large aggregators (LinkedIn, Indeed, Glassdoor, etc.)

**18 platforms** have automated public feed/API adapters. The rest are catalogued for reference — add their career page URLs under `sources.custom_career_pages` to fetch from them.

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
Columns: Company, Role, JD Summary, Location, Experience Level, **Employment Type**, Source, Contact Email, Posting Link, Date Found, Status (New/Contacted/Responded/Closed).

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
```

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
