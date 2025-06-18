import streamlit as st
import requests
from utils import parse_ai_resume

def generate_resume(user_info: str) -> str:
    api_key = st.secrets["api_key"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    prompt = (
        "Using the following information, create a clear, ATS-friendly, one-page professional resume. "
        "Organize it with appropriate sections and bold each section heading (e.g. **Summary**, **Skills**, **Experience**, **Education**, **Projects**, **Certifications**). "
        "Start directly with the candidate's name and a brief Summary, without repeating their name or adding additional copies. "
        "Make sure to use strong action verbs, concise bullet points, and keep it factual and impersonal (without using personal pronouns). "
        "Ensure it fits on a single page while retaining maximum impact and readability. "
        "Do not include a cover letter, additional comments, or explanations — output only the finished resume. "
        "Only include sections for which information is provided. Omit any section if the information is not provided.\n\n"
        f"{user_info}"
    )
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "You are an expert resume writer."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 800,
        "temperature": 0.7
    }
    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        st.error(f"AI Error: {e}")
        return ""

def modify_resume_section(original_resume_dict: dict, section: str, instruction: str) -> list:
    api_key = st.secrets["api_key"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    section_content = "\n".join(original_resume_dict.get(section, []))
    prompt = (
        f"Here is the {section} section of a professional resume in Markdown:\n\n{section_content}\n\n"
        f"IMPORTANT: Please improve this {section} section based on the following instruction while preserving ALL existing content and information in this section. "
        f"Only enhance, refine, or add to the existing content - do not remove or replace existing achievements, projects, or experience. "
        f"Instruction: {instruction if instruction else 'Optimize the section for clarity, conciseness, and ATS-friendliness while keeping all existing information.'}\n\n"
        f"Output only the improved {section} section in Markdown format, ensuring all original content is preserved and enhanced."
    )
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "You are an expert resume writer. Always preserve existing content while making improvements."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 400,
        "temperature": 0.5
    }
    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        ai_section_md = response.json()["choices"][0]["message"]["content"].strip()
        parsed = parse_ai_resume(f"## {section.title()}\n{ai_section_md}")
        return parsed.get(section, [])
    except Exception as e:
        st.error(f"AI Error: {e}")
        return []
