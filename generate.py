"""
Newsletter aggregation - generation stage.

Reads aggregate.json (produced by fetch.py) and asks Claude to draft
a newsletter from it. Writes the result to output/newsletter_draft.md.
"""

import json
import os
from datetime import datetime, timezone

import anthropic

SYSTEM_PROMPT = """\
You are drafting a community newsletter for a group of open source projects.

Structure the newsletter with these sections, skipping any that have no
relevant content this cycle:

## Project Updates
Summarize any meeting notes - key decisions, discussion points, and
action items. Write for someone who didn't attend the meeting.

## Notable Releases
Summarize each release: the project name, version, and the most important
changes (features, security fixes, breaking changes). Group by project.
Call out security fixes prominently.

## Wrap-up
A short (1-2 sentence) closing note.

Tone: clear, factual, and readable by both technical and non-technical
community members. Avoid marketing language. Use markdown formatting.
Do not invent information not present in the source material - if
something is ambiguous, describe it plainly rather than guessing.
"""


def build_user_message(items: list) -> str:
    parts = ["Here is this cycle's raw source material:\n"]
    for item in items:
        parts.append(
            f"--- {item['source_type'].upper()}: {item['source_name']} "
            f"({item['date']}) ---\n{item['content']}\n"
        )
    parts.append("\nDraft the newsletter now.")
    return "\n".join(parts)


def main():
    with open("aggregate.json") as f:
        items = json.load(f)

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_message(items)}],
    )

    draft = "".join(block.text for block in response.content if block.type == "text")

    today = datetime.now(timezone.utc).date().isoformat()
    header = f"# Community Newsletter Draft - {today}\n\n_Auto-generated. Review before sending._\n\n"

    os.makedirs("output", exist_ok=True)
    with open("output/newsletter_draft.md", "w") as f:
        f.write(header + draft)

    print(f"Wrote draft to output/newsletter_draft.md ({len(draft)} chars)")


if __name__ == "__main__":
    main()
