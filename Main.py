import streamlit as st
from fpdf import FPDF
import requests
import unicodedata
import re
import hashlib

def clean_text_for_pdf(text):
    """Cleans and normalizes text for PDF output."""
    if not text:
        return ""
    # Replace em dashes and special characters
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace(""", '"').replace(""", '"').replace("'", "'").replace("'", "'")
    text = text.replace("€", "e").replace("*", "").replace("()", "").replace("[", "").replace("]", "")
    # Replace bullet characters with regular hyphens
    text = text.replace("•", "-").replace("◦", "-").replace("▪", "-")
    # Remove backslashes and LaTeX commands
    text = text.replace("\\", "").replace("%", "")
    # Remove other problematic characters
    text = re.sub(r'[^\x00-\x7F]+', '', text)  # Remove non-ASCII
    # Normalize and encode safely
    return unicodedata.normalize('NFKD', text).encode('latin-1', 'ignore').decode('latin-1')

def parse_ai_resume(md_text):
    """Parses AI-generated Markdown resume into a dictionary."""
    sections = {}
    current = None
    for line in md_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Detect section headers
        if re.match(r"^#+\s", line):
            current = re.sub(r"^#+\s*", "", line).strip().lower()
            sections[current] = []
        elif re.match(r"^\*\*.*\*\*$", line) and len(line) < 40:
            current = line.strip("*").strip().lower()
            sections[current] = []
        elif current:
            sections[current].append(line)
    
    # Remove empty sections and clean content
    cleaned_sections = {}
    for k, v in sections.items():
        if v and any(line.strip() for line in v):
            cleaned_sections[k] = [clean_text_for_pdf(line) for line in v if line.strip()]
    
    return cleaned_sections

def merge_resume_content(original_resume, modified_content, modification_type="ai"):
    """Merges modified content with original resume while preserving existing information."""
    if not original_resume:
        return modified_content
    
    # Parse both original and modified content
    original_sections = parse_ai_resume(original_resume)
    
    if modification_type == "ai":
        # For AI modifications, intelligently merge content
        modified_sections = parse_ai_resume(modified_content)
        
        # Create merged resume
        merged_sections = original_sections.copy()
        
        # Update sections that were modified by AI
        for section, content in modified_sections.items():
            if section in merged_sections:
                # Merge content intelligently
                if section == "projects":
                    # For projects, append new projects or update existing ones
                    merged_sections[section] = content
                elif section == "skills":
                    # For skills, merge and deduplicate
                    existing_skills = " ".join(merged_sections[section])
                    new_skills = " ".join(content)
                    all_skills = existing_skills + " " + new_skills
                    merged_sections[section] = [all_skills]
                else:
                    # For other sections, use the AI-improved version
                    merged_sections[section] = content
            else:
                # Add new sections created by AI
                merged_sections[section] = content
        
        # Reconstruct the resume from merged sections
        return reconstruct_resume_from_sections(merged_sections)
    
    else:
        # For information modifications, use the updated user data
        return generate_resume_from_user_data()

def reconstruct_resume_from_sections(sections):
    """Reconstructs a complete resume from parsed sections."""
    resume_parts = []
    
    # Get name from session state
    name = st.session_state.resume_data.get('name', '').strip()
    if name:
        resume_parts.append(name)
        resume_parts.append("")
    
    # Add sections in order
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

def generate_resume_from_user_data():
    """Generates a fresh resume from current user data."""
    user_info = ""
    questions = [
        ("name", "Full Name"),
        ("location", "Location (City, State)"),
        ("phone", "Phone Number"),
        ("email", "Email Address"),
        ("portfolio", "Portfolio URL"),
        ("linkedin", "LinkedIn URL"),
        ("github", "GitHub URL"),
        ("skills", "Technical Skills (comma separated)"),
        ("experience", "Experience (format: Role, Org, Dates, Location, Description; separate multiple with '||')"),
        ("education", "Education (format: Degree, College, Dates, Location, Details)"),
        ("projects", "Projects (format: Title | Technologies | Year; separate multiple with '||')"),
        ("certifications", "Certifications (comma separated)")
    ]
    
    for k, label in questions:
        val = st.session_state.resume_data[k].strip()
        if val:
            user_info += f"{label}: {val}\n"
    
    return user_info

def ensure_url(url):
    """Ensures URL has HTTP/HTTPS prefix."""
    url = url.strip()
    if url and not url.startswith(("http://", "https://")):
        return "https://" + url
    return url

class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            # Name
            self.set_font("Arial", "B", 18)
            self.set_text_color(30, 30, 30)
            name = st.session_state.resume_data.get('name', '').strip()
            if name:
                self.cell(0, 12, clean_text_for_pdf(name), ln=True, align="C")
            self.ln(2)
            
            # Contact Info
            self.set_font("Arial", "", 10)
            contact_line = []
            for field in ['location', 'phone', 'email']:
                value = st.session_state.resume_data.get(field, '').strip()
                if value:
                    contact_line.append(clean_text_for_pdf(value))
            
            if contact_line:
                self.set_text_color(80, 80, 80)
                self.cell(0, 7, " | ".join(contact_line), ln=True, align="C")
            
            # Links
            links = []
            for label, field in [("LinkedIn", "linkedin"), ("GitHub", "github"), ("Portfolio", "portfolio")]:
                url = st.session_state.resume_data.get(field, '').strip()
                if url:
                    links.append((label, ensure_url(url)))
            
            if links:
                self.set_font("Arial", "U", 10)
                self.set_text_color(0, 102, 204)
                link_line = " | ".join(label for label, _ in links)
                self.set_x((210 - self.get_string_width(link_line)) / 2)
                for i, (label, url) in enumerate(links):
                    if i > 0:
                        self.write(7, " | ")
                    self.write(7, label, url)
            
            self.set_text_color(0, 0, 0)
            self.set_font("Arial", "", 11)
            self.ln(8)

    def section_title(self, title):
        self.set_font("Arial", "B", 12)
        self.set_text_color(0, 102, 204)
        self.cell(0, 8, title.upper(), ln=True)
        self.set_text_color(0, 0, 0)
        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.5)
        y = self.get_y()
        self.line(10, y, 200, y)
        self.ln(4)

    def add_bullets(self, lines):
        self.set_font("Arial", "", 11)
        for line in lines:
            if line.strip():
                self.cell(8)  # Indent
                self.multi_cell(0, 5, f"- {line.strip('- ')}")
        self.ln(2)

    def add_simple(self, text):
        self.set_font("Arial", "", 11)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def add_project(self, title, description, technologies, year):
        # Only project title in bold
        self.set_font("Arial", "B", 11)
        project_title = clean_text_for_pdf(title) if title else ""
        
        # Create the full header line with title, technologies, and year
        tech_year_parts = []
        if technologies:
            tech_year_parts.append(clean_text_for_pdf(technologies))
        if year:
            tech_year_parts.append(clean_text_for_pdf(year))
        
        if tech_year_parts:
            # Add title in bold, then switch to regular for tech/year
            self.cell(0, 6, project_title, ln=False)
            self.set_font("Arial", "", 11)
            self.cell(0, 6, f" | {' | '.join(tech_year_parts)}", ln=True)
        else:
            # Just title if no tech/year info
            self.cell(0, 6, project_title, ln=True)
        
        # Add small spacing after header
        self.ln(1)
        
        # Description bullets in regular font with proper indentation
        if description:
            bullets = re.split(r';|\n', description)
            self.set_font("Arial", "", 11)
            for bullet in bullets:
                bullet = bullet.strip()
                if bullet:
                    # Remove existing bullet points and dashes
                    bullet = bullet.lstrip('- •—◦▪').strip()
                    if bullet:
                        # Add consistent indentation and regular hyphen bullet
                        self.cell(8)  # Increased indent for better alignment
                        self.multi_cell(0, 5, f"- {clean_text_for_pdf(bullet)}")
        
        # Add spacing between projects
        self.ln(4)

    def body(self, sections, raw_md=None):
        """Main method to generate the resume body content."""
        order = [
            ("summary", "Summary"),
            ("skills", "Skills"),
            ("experience", "Experience"),
            ("education", "Education"),
            ("projects", "Projects"),
            ("certifications", "Certifications"),
            ("achievements", "Achievements"),
        ]
        
        for key, title in order:
            if key in sections and sections[key]:
                self.section_title(title)
                
                if key == "projects":
                    # Handle projects specially
                    project_text = "\n".join(sections[key])
                    projects = project_text.split("||") if "||" in project_text else [project_text]
                    
                    for project in projects:
                        project = project.strip()
                        if not project:
                            continue
                        
                        lines = project.split('\n')
                        title_line = lines[0] if lines else ""
                        
                        # Parse title, tech, year from first line
                        if '|' in title_line:
                            parts = [p.strip() for p in title_line.split('|')]
                            proj_title = parts[0] if parts else ""
                            proj_tech = parts[1] if len(parts) > 1 else ""
                            proj_year = parts[2] if len(parts) > 2 else ""
                        else:
                            # Fallback parsing for different formats
                            proj_title = title_line
                            proj_tech = ""
                            proj_year = ""
                        
                        # Get description from remaining lines
                        description_lines = lines[1:] if len(lines) > 1 else []
                        proj_desc = "\n".join(description_lines).strip()
                        
                        if proj_title or proj_desc:
                            self.add_project(proj_title, proj_desc, proj_tech, proj_year)
                
                elif all(l.startswith("- ") for l in sections[key] if l.strip()):
                    self.add_bullets(sections[key])
                else:
                    content = "\n".join(sections[key])
                    if content.strip():
                        self.add_simple(content)
                
                # Add section separator
                self.set_draw_color(200, 200, 200)
                self.set_line_width(0.3)
                y = self.get_y()
                if y < 280:  # Only add line if not near bottom
                    self.line(10, y, 200, y)
                self.ln(2)

def generate_pdf_safely(resume_content):
    """Safely generate PDF with enhanced error handling."""
    try:
        parsed = parse_ai_resume(resume_content)
        pdf = PDF()
        pdf.add_page()
        pdf.body(parsed, raw_md=resume_content)
        return pdf.output(dest='S').encode('latin1', 'ignore')
    except UnicodeEncodeError as e:
        st.error(f"Unicode encoding error: {e}")
        # Try with more aggressive character replacement
        try:
            # Clean the resume content more aggressively
            cleaned_content = clean_text_for_pdf(resume_content)
            parsed = parse_ai_resume(cleaned_content)
            pdf = PDF()
            pdf.add_page()
            pdf.body(parsed, raw_md=cleaned_content)
            return pdf.output(dest='S').encode('latin1', 'ignore')
        except Exception as fallback_error:
            st.error(f"PDF generation failed even with fallback: {fallback_error}")
            return None
    except Exception as e:
        st.error(f"PDF generation failed: {e}")
        return None

# Streamlit App Configuration
st.set_page_config(
    page_title="AI Resume Builder",
    page_icon="📝",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.title("📝 AI Resume Builder")
st.caption("Build your resume in minutes. Just answer the questions, let AI do the work, and download your ATS-friendly PDF.")

questions = [
    ("name", "Full Name"),
    ("location", "Location (City, State)"),
    ("phone", "Phone Number"),
    ("email", "Email Address"),
    ("portfolio", "Portfolio URL"),
    ("linkedin", "LinkedIn URL"),
    ("github", "GitHub URL"),
    ("skills", "Technical Skills (comma separated)"),
    ("experience", "Experience (format: Role, Org, Dates, Location, Description; separate multiple with '||')"),
    ("education", "Education (format: Degree, College, Dates, Location, Details)"),
    ("projects", "Projects (format: Title | Technologies | Year; separate multiple with '||')"),
    ("certifications", "Certifications (comma separated)")
]

# Initialize session state
for key in ["resume_data", "step", "ai_resume", "ai_resume_pdf", "modify_instruction", "content_hash", "original_resume_backup"]:
    if key not in st.session_state:
        if key == "resume_data":
            st.session_state.resume_data = {k: "" for k, _ in questions}
        elif key == "step":
            st.session_state.step = 0
        else:
            st.session_state[key] = "" if key != "ai_resume_pdf" else b""

# Q&A Form
if st.session_state.step < len(questions):
    key, label = questions[st.session_state.step]
    st.progress((st.session_state.step+1)/len(questions), text=f"Step {st.session_state.step+1} of {len(questions)}")
    st.header(f"Step {st.session_state.step+1}: {label}")
    
    with st.form("resume_form", clear_on_submit=False):
        value = st.text_area(label, st.session_state.resume_data[key], height=100)
        col1, col2 = st.columns([1, 1])
        submit = col1.form_submit_button("Next")
        back = col2.form_submit_button("Back") if st.session_state.step > 0 else None
        
        if submit:
            st.session_state.resume_data[key] = value
            st.session_state.step += 1
            st.rerun()
        if back:
            st.session_state.step -= 1
            st.rerun()

else:
    # Compile user information
    user_info = ""
    for k, label in questions:
        val = st.session_state.resume_data[k].strip()
        if val:
            user_info += f"{label}: {val}\n"

    st.divider()
    st.header("Your Information")
    st.code(user_info, language="markdown")

    # AI Resume Generation
    if not st.session_state.ai_resume:
        with st.spinner("AI is generating your resume..."):
            headers = {
                "Authorization": f"Bearer {st.secrets['PERPLEXITY_API_KEY']}",
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
                resume = response.json()["choices"][0]["message"]["content"].strip()
                st.session_state.ai_resume = resume
                # Store original backup
                st.session_state.original_resume_backup = resume
                # Generate content hash for validation
                st.session_state.content_hash = hashlib.md5(resume.encode()).hexdigest()
            except Exception as e:
                st.error(f"AI Error: {e}")

    # Resume Preview and Actions
    if st.session_state.ai_resume:
        st.divider()
        st.header("Resume Preview")
        st.markdown(st.session_state.ai_resume.replace('\n', '  \n'))

        st.divider()
        st.subheader("Modify with AI")
        st.session_state.modify_instruction = st.text_input(
            "How should AI improve your resume? (e.g., 'Make it more concise', 'Add more technical skills')",
            value=st.session_state.modify_instruction
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Modify Resume with AI"):
                with st.spinner("AI is modifying your resume..."):
                    headers = {
                        "Authorization": f"Bearer {st.secrets['PERPLEXITY_API_KEY']}",
                        "Content-Type": "application/json"
                    }
                    # Enhanced prompt for incremental modifications
                    modify_prompt = (
                        f"Here is a professional resume in Markdown:\n\n{st.session_state.ai_resume}\n\n"
                        f"IMPORTANT: Please improve this resume based on the following instruction while preserving ALL existing content and information. "
                        f"Only enhance, refine, or add to the existing content - do not remove or replace existing achievements, projects, or experience. "
                        f"Instruction: {st.session_state.modify_instruction if st.session_state.modify_instruction else 'Optimize the resume for clarity, conciseness, and ATS-friendliness while keeping all existing information.'}\n\n"
                        f"Output the complete improved resume in Markdown format, ensuring all original content is preserved and enhanced."
                    )
                    payload = {
                        "model": "sonar-pro",
                        "messages": [
                            {"role": "system", "content": "You are an expert resume writer. Always preserve existing content while making improvements."},
                            {"role": "user", "content": modify_prompt}
                        ],
                        "max_tokens": 1000,
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
                        improved_resume = response.json()["choices"][0]["message"]["content"].strip()
                        
                        # Merge with existing content instead of replacing
                        merged_resume = merge_resume_content(st.session_state.ai_resume, improved_resume, "ai")
                        st.session_state.ai_resume = merged_resume
                        
                        st.session_state.content_hash = hashlib.md5(merged_resume.encode()).hexdigest()
                        st.session_state.ai_resume_pdf = b""  # Clear cached PDF
                        st.success("Resume updated with AI while preserving all existing content!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"AI Error: {e}")

        with col2:
            if st.button("Modify Information"):
                # Store current resume as backup before modification
                st.session_state.original_resume_backup = st.session_state.ai_resume
                st.session_state.step = 0
                st.session_state.ai_resume = ""
                st.session_state.ai_resume_pdf = b""
                st.session_state.modify_instruction = ""
                st.session_state.content_hash = ""
                st.rerun()

        # Generate PDF with validation
        current_hash = hashlib.md5(st.session_state.ai_resume.encode()).hexdigest()
        if not st.session_state.ai_resume_pdf or st.session_state.content_hash != current_hash:
            with st.spinner("Generating PDF..."):
                pdf_bytes = generate_pdf_safely(st.session_state.ai_resume)
                if pdf_bytes:
                    st.session_state.ai_resume_pdf = pdf_bytes
                    st.session_state.content_hash = current_hash

        # Download button
        if st.session_state.ai_resume_pdf:
            st.download_button(
                label="📄 Download Resume as PDF",
                data=st.session_state.ai_resume_pdf,
                file_name="resume.pdf",
                mime="application/pdf"
            )
        else:
            st.error("PDF generation failed. Please try again or modify your content.")

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Start Over"):
                for key in st.session_state.keys():
                    del st.session_state[key]
                st.rerun()
        
        with col2:
            if st.button("↩️ Restore Original"):
                if st.session_state.original_resume_backup:
                    st.session_state.ai_resume = st.session_state.original_resume_backup
                    st.session_state.ai_resume_pdf = b""
                    st.success("Resume restored to original version!")
                    st.rerun()
