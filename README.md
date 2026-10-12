<div align="center">

# 🎓 Akew Tutor Bot

### Tutoring operations, coordinated entirely through Telegram.

A role-based tutoring management platform for the Ethiopian market — from tutor vetting and student payments to scheduling, Zoom sessions, recording review, and tutor payouts.

<br />

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?style=for-the-badge)
![APScheduler](https://img.shields.io/badge/APScheduler-Background%20Jobs-444444?style=for-the-badge)

**Built for Ethiopia** · ETB pricing · Local payment workflows · `Africa/Addis_Ababa`

</div>

---

## ✨ At a glance

Akew Tutor Bot brings the day-to-day work of a tutoring business into one Telegram experience. Students, tutors, and administrators get dedicated workflows without needing a separate web application.

| 👨‍🎓 Students | 🧑‍🏫 Tutors | 🛠️ Administrators |
|---|---|---|
| Register and pay monthly fees | Apply and submit verification materials | Vet and approve tutors |
| View schedules and session details | Share Zoom links and confirm sessions | Match tutors with students |
| Receive reminders and Zoom links | Upload session recordings | Verify payments and manage payouts |
| Confirm attendance and report issues | Track earnings | Handle emergencies and audit activity |

## 🚀 Core capabilities

<details open>
<summary><strong>Identity, onboarding & trust</strong></summary>

- Mandatory Telegram channel membership gate.
- Separate student and tutor registration flows.
- Timestamped acceptance of Terms & Conditions, Privacy Policy, and Tutor Rules.
- Multi-stage tutor vetting: CV and ID review, followed by a 30–50 minute teaching-video review.
- Admin approval or rejection at each vetting stage.
- Telegram-ID blacklisting to prevent rejected, blacklisted tutors from registering again.
- Environment-based bootstrap admins and a CLI command to create the first master admin.

</details>

<details open>
<summary><strong>💳 Payments & tutor earnings</strong></summary>

- Monthly student invoices calculated from grade rate × days per week × four weeks, with per-student overrides.
- Payment workflows for Telebirr, Commercial Bank of Ethiopia (CBE), and Awash Bank.
- Students submit payment screenshots directly in Telegram.
- Claim / confirm / reject review flow prevents two admins from reviewing the same payment simultaneously.
- Rolling payment deadlines, automated reminders, and scheduling lockout for overdue students.
- Monthly tutor payout generation, platform-commission tracking, and paid-status management.

</details>

<details open>
<summary><strong>🗓️ Scheduling & live sessions</strong></summary>

- Recurring weekly schedules configured by an admin.
- Automatic session generation seven days ahead for students whose payments are up to date.
- Tutor capacity tracking through `max_teaching_hours`.
- Subject-based matching, including primary and secondary subjects.
- Zoom-link requests 24 hours before each session, with link validation and forwarding to students.
- Urgent admin alerts when a Zoom link is still missing one hour before a session.
- Start and end confirmations from both tutor and student.
- Automatic flagging of absences and missed sessions.

</details>

<details open>
<summary><strong>🎥 Recording compliance & support</strong></summary>

- Mandatory session-recording uploads, stored as Telegram `file_id` values.
- Recording reminders and admin review; approval is required for payout eligibility.
- Emergency and issue reporting with admin claim / resolve workflows.
- Alerts can also be posted to an administrator group chat.
- Admin messaging supports text, approve / disapprove, acknowledgement, multiple choice, and file upload.
- Logged admin messages and audit trails.
- Dashboards and management actions for students, tutors, admins, invoices, payouts, and overall system status.

</details>

<details open>
<summary><strong>🛡️ Reliability & operations</strong></summary>

- IPv4-only DNS resolution to avoid intermittent IPv6 routing issues with Telegram polling.
- SQLAlchemy connection pooling, `pool_pre_ping`, connection recycling, and connection / statement timeouts.
- A watchdog job that monitors confirmed Telegram connectivity.
- HTTP health endpoint that reports actual bot health based on the freshness of Telegram contact.
- Message-send retry helper and global error handling.
- Logs written to `logs/bot.log` and the console.

</details>

## 🔄 How the workflow fits together

```mermaid
flowchart TD
    A[Student registers] --> B[Student pays monthly fee]
    B --> C[Admin verifies payment]
    C --> D[Student can access scheduling]
    E[Tutor applies] --> F[Documents reviewed]
    F --> G[Teaching video reviewed]
    G --> H[Admin approves and assigns tutor]
    D --> I[Admin creates weekly schedule]
    H --> I
    I --> J[Sessions generated 7 days ahead]
    J --> K[Zoom link requested 24 hours before]
    K --> L[Start and end confirmations]
    L --> M[Recording uploaded]
    M --> N[Admin reviews recording]
    N --> O[Session becomes payout-eligible]
    O --> P[Monthly tutor payout]
```

### Session timeline

| When | Automated or manual action |
|---|---|
| **24 hours before** | Tutor is asked to provide a Zoom link |
| **1 hour before** | Admin is alerted if the link is missing |
| **Shortly before start** | Tutor and student are prompted to confirm the start |
| **At session end** | Both parties are prompted to confirm completion |
| **Within 24 hours after** | Tutor recording upload is due |
| **Before payout** | Admin reviews and approves the recording |

## 🏗️ Architecture

The project separates Telegram interaction, business rules, and data access into layers.

```text
Telegram updates
      │
      ▼
  handlers/       Conversation flows, commands, and button callbacks
      │
      ▼
  services/       Business logic: payments, scheduling, notifications, audits
      │
      ▼
 repositories/    Database access
      │
      ▼
   models/        SQLAlchemy ORM entities
      │
      ▼
 PostgreSQL
```

Supporting modules:

- `ui/` — keyboards, message templates, payment page, and subject picker
- `data/` — subjects by grade, rates, legal text, and tutor rules
- `utils/` — validators, retry helpers, and error handling
- `config/` — settings and database engine configuration

**Core entities:** `User`, `Student`, `Tutor`, `Blacklist`, `Schedule`, `Session`, `Payment`, `TutorPayout`, `Emergency`, and `MessageLog`.

**Human-readable IDs:** `STU-0001`, `TUT-0001`, `ADM-0001`, `SCH-0001`, `SES-0001`, and `EMG-0001`, alongside generated transaction IDs.

## 📁 Project structure

```text
tutoring-bot/
├── main.py                  # Bot entry point, scheduler, health server, watchdog
├── add_admin.py             # Create the first master admin
├── init_remote_db.py        # Initialize tables on a remote database
├── run_job.py               # Manually trigger a scheduled job
├── migrations.sql           # Incremental SQL migrations
├── migrations 2.sql         # Additional tutor-table migrations
├── Procfile                 # PaaS process definition
├── runtime.txt              # Python runtime for hosting
├── requirements.txt         # Python dependencies
├── .env.example              # Environment-variable template
├── config/                  # Settings and SQLAlchemy engine
├── data/                    # Subjects, rates, and policy content
├── models/                  # ORM models
├── repositories/             # Data-access layer
├── services/                # Business logic and scheduled jobs
├── handlers/                # Student, tutor, admin, registration, Zoom flows
├── ui/                      # Keyboards and message templates
└── utils/                   # Validators, retry, and helper functions
```

## ⚡ Getting started

### Requirements

- Python **3.11**
- PostgreSQL **13+**
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A Telegram channel for the membership gate
- Optionally, an admin group chat that the bot has joined

### 1. Clone and install

```bash
git clone <your-repo-url>
cd tutoring-bot

python3.11 -m venv venv
source venv/bin/activate
# Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

Update `.env` with your environment values before starting the bot.

### 2. Create the database

Create a PostgreSQL database, for example:

```bash
createdb tutoring_bot
```

For a database that already exists and was created by an earlier version, apply migrations in order:

```bash
psql -U postgres -d tutoring_bot -f migrations.sql
psql -U postgres -d tutoring_bot -f "migrations 2.sql"
```

For a remote or hosted database configured through `DATABASE_URL`:

```bash
python init_remote_db.py
```

### 3. Create the first administrator

```bash
python add_admin.py <telegram_id> "<Full Name>" "<phone>"
```

Example:

```bash
python add_admin.py 123456789 "Jane Doe" "0912345678"
```

This command creates the tables and registers the first **master admin**. Add the same Telegram ID to `ADMIN_TELEGRAM_IDS` in `.env`.

> **Tip:** Send `/myid` to the bot to find your Telegram ID.

### 4. Configure environment variables

All settings are loaded from environment variables using `python-dotenv`.

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `BOT_TOKEN` | Yes | — | Telegram bot token |
| `DATABASE_URL` | Yes | — | PostgreSQL connection URL, e.g. `postgresql://user:pass@host:5432/tutoring_bot` |
| `ADMIN_TELEGRAM_IDS` | Yes | Empty | Comma-separated Telegram IDs of bootstrap admins |
| `ADMIN_GROUP_CHAT_ID` | No | None | Admin group chat ID for alerts (typically a negative ID) |
| `REQUIRED_CHANNEL` | Yes | `@AkewTutor` | Telegram channel users must join |
| `SESSION_RATE_ETB` | No | `300`* | Default hourly student rate in ETB |
| `PLATFORM_COMMISSION_ETB` | No | `100` | Platform commission per completed session |
| `TUTOR_NET_RATE_ETB` | No | `200`* | Tutor net pay per completed session |
| `TIMEZONE` | No | `Africa/Addis_Ababa` | Application timezone |
| `RECORDINGS_PATH` | No | `./recordings` | Local recordings directory |
| `MAX_RECORDING_AGE_DAYS` | No | `30` | Recording retention window |
| `MAX_RECORDING_SIZE_MB` | No | `2000` | Maximum accepted recording size |
| `ALLOWED_VIDEO_EXTENSIONS` | No | `.mp4,.mkv,.avi` | Accepted recording formats |
| `PAYMENT_TEST_MODE` | No | `false` | Enables payment test mode |
| `PORT` | No | `8080` | Health-check HTTP server port |

> **Important — set rates explicitly:** The `.env.example` file uses `SESSION_RATE_ETB=350` and `TUTOR_NET_RATE_ETB=250` (250 tutor + 100 platform commission). These differ from the in-code fallback defaults marked with `*`. Set both values explicitly in your environment.

Timing constants in `config/config.py` include the Zoom-link request (24 hours before), missing-link deadline (1 hour before), and session reminder (1 hour before).

## 🗄️ Database notes

- Tables are created through SQLAlchemy `create_all`, invoked by `add_admin.py` and `init_remote_db.py`.
- Apply existing-database SQL migrations in the order shown above.
- Connection pool: 10 connections plus 20 overflow.
- Connection recycling: 30 minutes.
- Connect timeout: 10 seconds.
- Statement timeout: 15 seconds.

## ▶️ Run the bot

```bash
python main.py
```

On startup, the application:

1. Registers handlers and starts Telegram long polling.
2. Starts the scheduler and watchdog.
3. Starts a lightweight HTTP health server on `$PORT`.
4. Writes logs to `logs/bot.log` and the console.

### Run a scheduled job manually

Useful for testing or operations:

```bash
python run_job.py <job_name>
```

Available jobs:

`reminders`, `sessions`, `zoom`, `missed`, `zoom_deadline`, `start_confirm`, `tutor_response`, `end_confirm`, `recording_reminder`

## ⏱️ Background jobs

Jobs run with `AsyncIOScheduler` in the `Africa/Addis_Ababa` timezone.

| Job | Frequency | Purpose |
|---|---|---|
| Session generation | Daily at 00:05 | Generate the next seven days of sessions for paid students |
| Zoom-link requests | Hourly | Request links 24 hours before sessions |
| Zoom deadline check | Every 15 minutes | Alert admins when a link is missing one hour before a session |
| Session start confirmation | Every 5 minutes | Prompt both parties around session start |
| Tutor start-response check | Every 15 minutes | Flag sessions without tutor confirmation |
| Session end confirmation | Every 5 minutes | Prompt both parties at session end |
| Recording reminder | Every 6 hours | Remind tutors to upload recordings |
| Missed-session detection | Hourly | Mark past sessions that never started as missed |
| Payment reminders | Daily at 08:00 | Notify students approaching or past their payment deadline |
| Watchdog | Every 2 minutes | Check Telegram connectivity and update health state |

## 📏 Business rules

- **Session length:** one hour.
- **Monthly fee:** `days_per_week × 4 × hourly_rate`, using grade defaults unless an admin overrides the student's rate.
- **Session payout:** platform commission and tutor net rate are multiplied by eligible completed sessions.
- **Overdue access:** overdue students cannot use scheduling features. Payments, Help, Report, and Emergency remain available.
- **Supported grades:** Grades 1–12. Grades 11–12 support Natural and Social streams.
- **Subjects:** configured per grade in `data/subjects.py`.
- **Recording limits:** `.mp4`, `.mkv`, and `.avi`, up to 2,000 MB by default.
- **Payout eligibility:** sessions must be confirmed by both parties and have a recording approved by an admin.

## ☁️ Deployment

The repository includes configuration for PaaS hosting such as Render or Heroku:

- `Procfile` — `web: python main.py`
- `runtime.txt` — `python-3.11.9`
- HTTP health endpoint — responds on `$PORT` and reports unhealthy status when recent Telegram contact is missing, allowing a hosting platform to restart a hung process.

### Deployment checklist

- [ ] Provision PostgreSQL and configure `DATABASE_URL`.
- [ ] Set all required environment variables in the hosting platform.
- [ ] Run `python init_remote_db.py` once.
- [ ] Create the first admin with `python add_admin.py ...`.
- [ ] Deploy and inspect application logs.

> **Important:** Run only **one active instance per bot token**. Telegram long polling does not support multiple concurrent pollers using the same token.

## 🧰 Troubleshooting

| Symptom | Likely cause | What to check |
|---|---|---|
| `Conflict: terminated by other getUpdates request` | Another process is polling with the same token | Stop the duplicate instance |
| Users see “Join Our Channel First” | Channel configuration or permissions are incorrect | Verify `REQUIRED_CHANNEL` and make the bot a channel admin |
| Admin alerts are missing | Admin group configuration is incorrect | Verify `ADMIN_GROUP_CHAT_ID` and bot membership in the group |
| Sessions are not appearing | Payment is unconfirmed or session generation has not run | Check payment status; try `python run_job.py sessions` |
| Bot appears frozen | Database connectivity or another runtime issue | Inspect logs; check database access, timeouts, and watchdog health |

## 🧭 Roadmap

Potential future improvements:

- [ ] Integrate payment-provider APIs or webhooks to replace screenshot verification.
- [ ] Add an automated test suite and CI pipeline.
- [ ] Adopt Alembic for structured database migrations.
- [ ] Evaluate Telegram webhook mode as an alternative to long polling.
- [ ] Add Amharic and English language support.
- [ ] Export finance and attendance reports as CSV or PDF.

## 📄 License

No license file is currently included. Add a license (for example, MIT) before distributing or open-sourcing this project.

---

<div align="center">

**Akew Tutor Bot** · Making tutoring operations easier to coordinate, one Telegram workflow at a time.

</div>
