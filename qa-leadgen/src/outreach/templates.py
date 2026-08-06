"""Email template generation for personalized outreach."""

from __future__ import annotations

from pathlib import Path

DEFAULT_TEMPLATE = """Subject: Experienced QA Engineer — Interest in {{role}} at {{company}}

Hi {{company}} Team,

I came across your {{role}} opening and was impressed by the focus on quality in your job description. With hands-on experience in manual and automated testing, API validation, and CI/CD integration, I believe I could contribute meaningfully to your QA efforts.

A few highlights relevant to your posting:
{{jd_highlights}}

I'd welcome the chance to discuss how my background aligns with your team's needs. I've attached my resume for your review, and I'm happy to share work samples or complete a technical assessment at your convenience.

Best regards,
{{user_name}}
{{user_email}}
{{user_phone}}
{{user_website}}

---
You are receiving this email because your company posted a public job listing. If you prefer not to receive future messages, reply with "unsubscribe" and I will remove you from my list immediately.
"""


def load_template(template_path: Path | None = None) -> str:
    if template_path and template_path.exists():
        return template_path.read_text(encoding="utf-8")
    default_path = Path(__file__).parent.parent.parent / "templates" / "outreach_email.txt"
    if default_path.exists():
        return default_path.read_text(encoding="utf-8")
    return DEFAULT_TEMPLATE


def _extract_highlights(jd_text: str, max_bullets: int = 3) -> str:
    sentences = [s.strip() for s in jd_text.replace("\n", " ").split(".") if len(s.strip()) > 20]
    bullets = sentences[:max_bullets]
    if not bullets:
        return "• Strong background in software quality assurance and test automation"
    return "\n".join(f"• {b}" for b in bullets)


def render_email(
    *,
    company: str,
    role: str,
    jd_text: str,
    user_config: dict,
    template: str | None = None,
) -> tuple[str, str]:
    tpl = template or DEFAULT_TEMPLATE

    # Split subject line if present in template
    subject = f"Experienced QA Engineer — Interest in {role} at {company}"
    body = tpl
    if tpl.startswith("Subject:"):
        lines = tpl.split("\n", 1)
        subject_line = lines[0].replace("Subject:", "").strip()
        body = lines[1] if len(lines) > 1 else ""
        subject = _replace_vars(subject_line, company, role, jd_text, user_config)

    body = _replace_vars(body, company, role, jd_text, user_config)
    return subject, body.strip()


def _replace_vars(
    text: str, company: str, role: str, jd_text: str, user_config: dict
) -> str:
    highlights = _extract_highlights(jd_text)
    replacements = {
        "{{company}}": company,
        "{{role}}": role,
        "{{jd_highlights}}": highlights,
        "{{user_name}}": user_config.get("name", ""),
        "{{user_email}}": user_config.get("email", ""),
        "{{user_phone}}": user_config.get("phone", ""),
        "{{user_website}}": user_config.get("website", ""),
    }
    for key, val in replacements.items():
        text = text.replace(key, val)
    return text
