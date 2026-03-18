import re
from typing import Dict, Any

try:
    import pdfplumber
except ImportError:
    pdfplumber = None
try:
    import docx
except ImportError:
    docx = None

RESPONSE_SCHEMA = {
    "professional_summary": ["..."],
    "skills": ["..."],
    "education": ["..."],
    "experience": ["..."],
    "projects": ["..."],
    "certifications": ["..."],
    "achievements": ["..."],
}

CLEANING_OUTPUT_SCHEMA = {
    "professional_summary_seed": "...",
    "skills": ["..."],
    "education": ["Degree | Institution | Duration | Location | Details"],
    "experience": [
        {
            "role": "...",
            "company": "...",
            "duration": "...",
            "location": "...",
            "highlights": ["..."],
        }
    ],
    "projects": [
        {
            "name": "...",
            "technologies": "...",
            "year": "...",
            "highlights": ["..."],
        }
    ],
    "certifications": ["..."],
    "achievements": ["..."],
    "job_description_keywords": ["..."],
}

def extract_text_from_pdf(file_path: str) -> str:
    if not pdfplumber:
        raise ImportError("pdfplumber is not installed.")
    with pdfplumber.open(file_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)

def extract_text_from_docx(file_path: str) -> str:
    if not docx:
        raise ImportError("python-docx is not installed.")
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

def parse_resume_text(text: str) -> Dict[str, Any]:
    # Simple regex-based section extraction (can be improved)
    sections = {
        "professional_summary": [],
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "achievements": [],
    }
    current_section = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        lline = line.lower()
        if "summary" in lline:
            current_section = "professional_summary"
        elif "skill" in lline:
            current_section = "skills"
        elif "education" in lline:
            current_section = "education"
        elif "experience" in lline:
            current_section = "experience"
        elif "project" in lline:
            current_section = "projects"
        elif "certification" in lline:
            current_section = "certifications"
        elif "achievement" in lline:
            current_section = "achievements"
        elif current_section:
            sections[current_section].append(line)
    return sections

def parse_resume_file(file_path: str) -> Dict[str, Any]:
    if file_path.lower().endswith(".pdf"):
        text = extract_text_from_pdf(file_path)
    elif file_path.lower().endswith(".docx"):
        text = extract_text_from_docx(file_path)
    else:
        raise ValueError("Unsupported file type")
    return parse_resume_text(text)
