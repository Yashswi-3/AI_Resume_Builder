import unicodedata
import re

def clean_text_for_pdf(text: str) -> str:
    if not text:
        return ""
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace(""", '"').replace(""", '"').replace("'", "'").replace("'", "'")
    text = text.replace("€", "e").replace("*", "").replace("()", "").replace("[", "").replace("]", "")
    text = text.replace("•", "-").replace("◦", "-").replace("▪", "-")
    text = text.replace("\\", "").replace("%", "")
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    return unicodedata.normalize('NFKD', text).encode('latin-1', 'ignore').decode('latin-1')

def parse_ai_resume(md_text: str) -> dict:
    sections = {}
    current = None
    for line in md_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if re.match(r"^#+\s", line):
            current = re.sub(r"^#+\s*", "", line).strip().lower()
            sections[current] = []
        elif re.match(r"^\*\*.*\*\*$", line) and len(line) < 40:
            current = line.strip("*").strip().lower()
            sections[current] = []
        elif current:
            sections[current].append(line)
    cleaned_sections = {}
    for k, v in sections.items():
        if v and any(line.strip() for line in v):
            cleaned_sections[k] = [clean_text_for_pdf(line) for line in v if line.strip()]
    return cleaned_sections

def reconstruct_resume_from_sections(sections: dict) -> str:
    resume_parts = []
    section_order = [
        ("summary", "Summary"),
        ("skills", "Skills"),
        ("experience", "Experience"),
        ("education", "Education"),
        ("projects", "Projects"),
        ("certifications", "Certifications"),
        ("achievements", "Achievements"),
    ]
    for key, title in section_order:
        if key in sections and sections[key]:
            resume_parts.append(f"## {title}")
            resume_parts.append("")
            for line in sections[key]:
                resume_parts.append(line)
            resume_parts.append("")
    return "\n".join(resume_parts)
