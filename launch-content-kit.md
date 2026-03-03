# NetPicker CLI — Launch Content Kit
## `netpicker audit report` feature launch

> Repo: https://github.com/netpicker/netpicker-cli
> Install: `pip install netpicker-cli`
> Docs: https://netpicker.io

---

## LINKEDIN POST 1 — The Hook (text post)

**I used to spend 45 minutes every Monday morning building a "network health" spreadsheet for my manager.**

Device inventory. Compliance posture. Backup freshness. Policy status.

Four different tools. Five browser tabs. One copy-paste nightmare.

Now I run one command:

```
netpicker audit report --tag production --format json
```

And I get everything — inventory, compliance, backup staleness, policy status — in one report. Table, JSON, CSV, or YAML. Your choice.

The kicker? It runs all four checks in parallel. Sub-second on most networks.

We just shipped this in netpicker-cli (open source, MIT licensed).

If you're a network engineer tired of duct-taping scripts together for Monday morning status updates — try it:

```
pip install netpicker-cli
netpicker audit report
```

That's it. No YAML files. No playbooks. No 200-line Python scripts.

One command. Full picture.

→ Star the repo if this saves you time: https://github.com/netpicker/netpicker-cli
→ Full docs in the README

#NetworkAutomation #NetDevOps #Python #OpenSource #NetworkEngineering

---

## LINKEDIN POST 2 — The Comparison (text post)

**Ansible playbook to check network health: ~80 lines of YAML + Jinja templates.**
**Nornir script: ~60 lines of Python + custom tasks.**
**Netmiko approach: 5 scripts + your own reporting glue.**

Or:

```
netpicker audit report
```

One line. Zero config files.

Here's what it gives you:
• Device inventory with platform breakdown
• Compliance pass/fail posture
• Backup freshness — flags anything stale (default: 7 days)
• Policy status — enabled vs disabled

Want stricter freshness? `--stale-days 3`
Want just production? `--tag production`
Want to pipe it into CI? `--format json`

I'm not bashing those other tools — I use them daily. But for the "give me the status of my network RIGHT NOW" use case, nothing should take more than one command.

We built netpicker-cli to be the tool you reach for *first* every morning.

Try it: `pip install netpicker-cli`
Star it: https://github.com/netpicker/netpicker-cli

#NetworkEngineering #Automation #CLI #Python #NetDevOps

---

## LINKEDIN POST 3 — The Carousel Thread (multi-slide)

### Slide 1 (Cover)
**"I audited 200 network devices in 3 seconds."**
Here's the one command that replaced my Monday morning spreadsheet.

### Slide 2
**The Problem**
Every Monday:
→ Log into 3 dashboards
→ Export device inventory
→ Check compliance reports
→ Verify backup freshness
→ Copy-paste into a spreadsheet
→ Email the manager

Total time: 30-45 minutes.
Morale cost: immeasurable.

### Slide 3
**The Fix**
```
pip install netpicker-cli
netpicker audit report --tag production
```
That's it. Two commands.
First one is a one-time install.

### Slide 4
**What You Get**
```
[OK]   INVENTORY    — 47 devices, 3 platforms
[WARN] COMPLIANCE   — 42 passed, 5 failed
[WARN] BACKUPS      — 44 fresh, 2 stale, 1 errored
[OK]   POLICIES     — 3 enabled, 1 disabled
```
Color-coded. Human-readable. Instant.

### Slide 5
**Need Machine-Readable Output?**
```
netpicker audit report --format json --output report.json
netpicker audit report --format csv --output audit.csv
```
Pipe it into CI/CD. Feed it to Grafana. Email it as an attachment.
Table, JSON, CSV, YAML — your call.

### Slide 6
**Extensible by Design**
```python
from netpicker_cli.commands.audit import register_section

@register_section
def check_firmware(cli, settings, options):
    # your custom logic
    return AuditSection(name="firmware", ...)
```
Add your own audit checks. No forks. No PRs required.

### Slide 7 (CTA)
**Try it in 60 seconds:**
```
pip install netpicker-cli
netpicker auth login --base-url <URL> --tenant <TENANT> --token <TOKEN>
netpicker audit report
```

→ Star the repo: github.com/netpicker/netpicker-cli
→ MIT licensed. Free forever.

#NetworkAutomation #Python #OpenSource #NetDevOps

---

## LINKEDIN POST 4 — The "Tired Engineer" Post (text post)

**Things network engineers shouldn't have to do in 2026:**

✗ SSH into 4 devices to check if backups ran
✗ Open a browser to check compliance dashboards
✗ Manually count which configs are older than 7 days
✗ Build a spreadsheet to prove the network is healthy

**Things network engineers SHOULD do:**

✓ `netpicker audit report`
✓ Done.

We just shipped a one-command network health audit in netpicker-cli.

It pulls inventory, compliance, backup freshness, and policy status — in parallel — and gives you a report. Table for humans. JSON for machines. CSV for spreadsheets.

If you've ever thought "there has to be a faster way to prove the network is fine" — this is it.

`pip install netpicker-cli`

https://github.com/netpicker/netpicker-cli

#NetworkEngineering #Automation #NetDevOps #Python

---

## LINKEDIN POST 5 — The Technical Deep Dive (text post)

**How we built `netpicker audit report` — architecture notes for the curious:**

The audit command is pure orchestration. It doesn't add a single new API endpoint. It calls four existing ones in parallel:

1. `GET /devices/{tenant}` → inventory + platform breakdown
2. `GET /compliance/{tenant}/overview` → pass/fail posture
3. `GET /devices/{tenant}/recent-configs/` → backup freshness
4. `GET /policy/{tenant}` → enabled/disabled policies

Each one runs in its own thread via `asyncio.to_thread()` and returns an `AuditSection` dataclass. If one fails, the others still complete — graceful degradation.

The plugin system uses a simple registry pattern:

```python
@register_section
def my_check(cli, settings, options):
    return AuditSection(name="custom", summary={...})
```

Registered functions get called alongside the built-ins. No monkey-patching. No subclassing.

Output goes through the existing `OutputFormatter` — table, JSON, CSV, YAML — with zero new dependencies added.

Exit code 0 = all green. Exit code 2 = at least one section errored. CI-friendly.

Total new code: ~550 lines (command) + ~480 lines (tests). 29/29 tests passing.

The whole thing was designed so a network engineer with intermediate Python can read it, extend it, and contribute back.

Star and check the source: https://github.com/netpicker/netpicker-cli

#Python #OpenSource #SoftwareArchitecture #NetworkAutomation

---
---

## REDDIT r/networking LAUNCH POST

**Title:** We built a one-command network audit report — open source, free, MIT licensed

**Body:**

Hey r/networking —

I'm working on **netpicker-cli**, an open-source CLI for the Netpicker platform. We just shipped a feature I've personally wanted for years: a single command that gives you a full network health snapshot.

```
pip install netpicker-cli
netpicker audit report
```

**What it does:**

- **Inventory** — total device count + platform breakdown (Cisco IOS, Arista EOS, FortiOS, etc.)
- **Compliance** — pass/fail posture across all policies
- **Backup freshness** — flags any device whose last config backup is older than N days (default 7, configurable with `--stale-days`)
- **Policy status** — which compliance policies are enabled vs disabled

It fetches all four in parallel, handles errors gracefully per-section, and outputs table (human), JSON (CI/CD), CSV (spreadsheet), or YAML.

**Sample output:**

```
  NetPicker Audit Report — tenant: production
  Overall status: [WARN]

  [OK]   INVENTORY
      total_devices: 47
      platforms:
        cisco_ios: 28
        arista_eos: 12
        fortios: 7

  [WARN] COMPLIANCE
      devices: passed: 42, failed: 5

  [WARN] BACKUPS
      fresh: 44, stale: 2, errored: 1

  [OK]   POLICIES
      total: 4, enabled: 3, disabled: 1
```

**Why I built this:** I was spending 30+ minutes every Monday morning copy-pasting between dashboards to build a health report. Four tools, five browser tabs, one spreadsheet. Now it's one command.

**What it's NOT:** This isn't a replacement for Nornir/Ansible/Netmiko. Those are execution frameworks. This is a reporting layer on top of your existing Netpicker deployment. If you use Netpicker, this CLI talks to its API.

**Tech details for the curious:**
- Python 3.10+, Typer framework, httpx for HTTP
- Async parallel fetching via `asyncio.to_thread()`
- Plugin system — `@register_section` to add custom audit checks
- 29 unit tests, MIT licensed, zero new dependencies over the base CLI

**Links:**
- GitHub: https://github.com/netpicker/netpicker-cli
- Install: `pip install netpicker-cli`
- Docs: Check the README, it's comprehensive

If this looks useful, a **GitHub star** helps us a ton with visibility. Happy to answer any questions about the implementation or take feature requests.

---
---

## LOOM VIDEO SCRIPT — "Network Audit in 60 Seconds"

**Total runtime: ~2:30**

---

**[0:00–0:15] HOOK**

"If you spend more than 5 minutes checking your network's health every morning, this video is for you. I'm going to show you one command that replaces your Monday morning dashboard crawl."

---

**[0:15–0:35] THE PROBLEM**

"Here's what most network engineers do: log into the device dashboard, check inventory. Open the compliance portal, check pass/fail. Go to backups, check if configs are fresh. Maybe check policy status in another tab. Then copy it into a spreadsheet or Slack message. That's 30 minutes. Every. Single. Monday."

---

**[0:35–0:55] THE INSTALL**

*[Screen: terminal]*

"Let's fix that. First, install:"

```
pip install netpicker-cli
```

"Then authenticate — you only do this once:"

```
netpicker auth login --base-url https://your-netpicker.com --tenant YourTenant --token YOUR_TOKEN
```

"Done. That's the setup."

---

**[0:55–1:25] THE COMMAND**

*[Screen: terminal, typing slowly]*

"Now, the magic:"

```
netpicker audit report
```

*[Hit enter. Output appears.]*

"Boom. Inventory — 47 devices across 3 platforms. Compliance — 42 passed, 5 failed, flagged as a warning. Backups — 44 fresh, 2 stale, 1 errored. The stale devices are listed right there with how many days old they are. Policies — 3 enabled, 1 disabled."

"That's your entire network health picture. In about 2 seconds."

---

**[1:25–1:50] POWER OPTIONS**

*[Screen: terminal]*

"Want just production devices?"

```
netpicker audit report --tag production
```

"Want machine-readable JSON for your CI pipeline?"

```
netpicker audit report --format json --output report.json
```

"Want to flag anything older than 3 days instead of 7?"

```
netpicker audit report --stale-days 3
```

"CSV for your manager's spreadsheet?"

```
netpicker audit report --format csv --output audit.csv
```

---

**[1:50–2:15] EXTENSIBILITY**

*[Screen: code editor showing the register_section example]*

"And if you want custom checks — firmware versions, uptime thresholds, whatever — there's a plugin system. You write a Python function, decorate it with `@register_section`, and it runs alongside the built-in checks. No forking required."

---

**[2:15–2:30] CTA**

*[Screen: GitHub repo page]*

"The whole thing is open source, MIT licensed, on GitHub. Link is in the description. If this saves you time, drop us a star — it helps more network engineers find it."

"Install: `pip install netpicker-cli`. Try `netpicker audit report`. That's it. See you next time."

---
---

## BLOG POST — netpicker.io (400 words)

### One Command to Audit Your Entire Network

Every network engineer knows the Monday morning ritual. Open the device inventory. Check the compliance dashboard. Verify backups ran over the weekend. Confirm policies are still enabled. Copy the results into a spreadsheet. Send it to the manager.

Four tools. Five browser tabs. Thirty minutes of your life you'll never get back.

We built `netpicker audit report` to make that ritual a one-liner.

#### What It Does

A single command gathers four critical data points from your Netpicker deployment:

- **Inventory** — total device count and platform breakdown (Cisco IOS, Arista EOS, FortiOS, and everything else Netpicker manages)
- **Compliance** — aggregated pass/fail posture across all your policies
- **Backup Freshness** — flags any device whose last config backup is older than your threshold (default: 7 days, configurable with `--stale-days`)
- **Policy Status** — which compliance policies are enabled and which are sitting disabled

All four sections run in parallel under the hood, so you get results in seconds, not minutes.

#### Output That Fits Your Workflow

Run `netpicker audit report` for a color-coded terminal table you can screenshot and paste into Slack. Add `--format json` for CI/CD pipelines. Add `--format csv --output audit.csv` for the spreadsheet your manager will actually look at. YAML is there too, because why not.

The exit code is CI-friendly: 0 means everything is green, 2 means at least one section had errors. Wire it into your pipeline and let the build tell you when something drifts.

#### Extend It Without Forking

The audit system has a built-in plugin registry. Write a Python function, decorate it with `@register_section`, and your custom check — firmware versions, uptime thresholds, certificate expiry, anything — runs alongside the built-in sections automatically. No pull request required.

```python
from netpicker_cli.commands.audit import register_section, AuditSection

@register_section
def check_firmware(cli, settings, options):
    # your logic here
    return AuditSection(name="firmware", summary={"outdated": 2})
```

#### Try It Now

```bash
pip install netpicker-cli
netpicker auth login --base-url <URL> --tenant <TENANT> --token <TOKEN>
netpicker audit report
```

Three commands. The first two are one-time setup. The third becomes your new Monday morning.

The entire project is open source under the MIT license. If `netpicker audit report` saves you even 10 minutes a week, consider starring the repo — it helps other engineers discover the tool.

**GitHub:** [github.com/netpicker/netpicker-cli](https://github.com/netpicker/netpicker-cli)

We'd love to hear what custom audit sections you build. Open an issue, start a discussion, or just tell us on LinkedIn. Ship it.
