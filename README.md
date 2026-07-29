# Cron_Decode ⏰

**Parse, validate, and explain cron expressions in plain English.** Zero dependencies, pure Python stdlib.

> Part of the DevOps & Automation suite — makes cron schedules readable by humans and agents alike.

## One tool, many domains

| Domain | What Cron_Decode does for you |
|---|---|
| 🖥️ **DevOps / SRE** | Validate cron schedules in CI pipelines before deployment |
| 🤖 **AI Agents** | Translate opaque cron strings into parseable JSON for scheduling decisions |
| 📚 **Documentation** | Generate human-readable descriptions of cron-based automation |
| 🧪 **Testing** | Verify cron expressions fire at expected times |
| 👨‍🎓 **Learning** | Understand what any cron expression actually means |

## Install

```bash
git clone git@github.com:realMNohgee/Cron_Decode.git
cd Cron_Decode
python3 cron_decode.py --help
```

## Quick start

```bash
# Explain a cron expression
python3 cron_decode.py explain "0 */6 * * 1-5"
# → "At minute 0, every 6th hour, on Monday through Friday."

# Validate
python3 cron_decode.py validate "0 0 * * 0"

# List upcoming execution times
python3 cron_decode.py list "30 9 * * 1-5" -n 5

# JSON output for pipelines
python3 cron_decode.py explain "*/15 * * * *" --format json
```

## Supported syntax

| Feature | Example | Meaning |
|---|---|---|
| Wildcard | `*` | Every value |
| Step values | `*/15` | Every 15 units |
| Ranges | `1-5` | Values 1 through 5 |
| Lists | `1,3,5` | Specific values |
| Named days | `mon-fri` | Monday through Friday |

## Subcommands

- **`explain`** — Translate a cron expression into plain English
- **`validate`** — Check if a cron expression is syntactically valid
- **`list`** — Show upcoming execution times (next N occurrences)

All subcommands support `--format text|json`.

## License

MIT — see [LICENSE](LICENSE).

---

🧰 **[Tool on Hermtica Marketplace](https://hermtica.com/marketplace)** — the open, agent-agnostic marketplace for AI agent tools.
