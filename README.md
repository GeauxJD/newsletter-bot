# Newsletter Bot

Fetches meeting notes (public Google Docs) and release notes (GitHub repos),
then drafts a community newsletter with Claude. Runs on a weekly schedule
via GitHub Actions and opens a PR with the draft for human review.

## Setup

1. **Add sources** — edit `sources.yml` with your Google Doc IDs and GitHub
   repos. No code changes needed.

2. **Enable Actions** if this is a fresh repo (Settings → Actions → General →
   allow all actions).

3. **Test it manually** before waiting for the schedule: go to the Actions
   tab → "Fetch Newsletter Source Data" → Run workflow.

## How it works

- `fetch.py` — pulls raw content from every source in `sources.yml`,
  retries flaky requests, and fails loudly (rather than silently) if a
  source can't be fetched or comes back suspiciously empty.
- The workflow runs on a schedule (weekly by default), fetches everything,
  and opens a PR containing the resulting `aggregate.json` for review.
  Merge the PR to accept the run's data, or close it to discard.

## Generating the newsletter itself

This repo currently stops at producing `aggregate.json` — a clean, structured
dump of this cycle's meeting notes and release content. Turning that into an
actual newsletter draft is a separate step, done however you prefer:

- `generate.py` is included as a starting point — it calls the Claude API
  with a system prompt defining the newsletter's structure/tone. To use it,
  add an `ANTHROPIC_API_KEY` repo secret and either run it locally against
  a downloaded `aggregate.json`, or wire it into a second scheduled
  workflow that runs after the fetch PR is merged.
- Alternatively, just paste `aggregate.json`'s contents into a chat with
  Claude (or any model) and ask it to draft the newsletter — no automation
  required.

## Notes on Google Docs

Only works for docs shared as "Anyone with the link can view." The export
endpoint has occasionally been observed to be flaky for some networks/ISPs
(returns empty on the first try) — `fetch.py` retries automatically and
rejects suspiciously short responses rather than treating them as success.
Running this in GitHub Actions (rather than a home network) avoids that
class of problem entirely, since it runs from GitHub's own infrastructure.
