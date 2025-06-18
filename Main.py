import streamlit as st
from ai_handler import generate_resume, modify_resume_section
from pdf_handler import generate_pdf
from utils import parse_ai_resume, reconstruct_resume_from_sections

QUESTIONS = [
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

CONTACT_FIELDS = ["name", "location", "phone", "email", "portfolio", "linkedin", "github"]
SECTION_MAP = {
    "skills": "skills",
    "experience": "experience",
    "education": "education",
    "projects": "projects",
    "certifications": "certifications"
}

# --- Session state initialization ---
if "resume_data" not in st.session_state:
    st.session_state.resume_data = {k: "" for k, _ in QUESTIONS}
if "step" not in st.session_state:
    st.session_state.step = 0
if "original_resume_dict" not in st.session_state:
    st.session_state.original_resume_dict = None
if "current_resume_dict" not in st.session_state:
    st.session_state.current_resume_dict = None
if "ai_resume_pdf" not in st.session_state:
    st.session_state.ai_resume_pdf = b""
if "modify_instruction" not in st.session_state:
    st.session_state.modify_instruction = ""
if "modify_section" not in st.session_state:
    st.session_state.modify_section = ""

st.set_page_config(page_title="AI Resume Builder", page_icon="📝", layout="centered", initial_sidebar_state="collapsed")
st.title("📝 AI Resume Builder")
st.caption("Build your resume in minutes. Just answer the questions, let AI do the work, and download your ATS-friendly PDF.")

if st.session_state.step < len(QUESTIONS):
    key, label = QUESTIONS[st.session_state.step]
    st.progress((st.session_state.step+1)/len(QUESTIONS), text=f"Step {st.session_state.step+1} of {len(QUESTIONS)}")
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
    user_info = ""
    for k, label in QUESTIONS:
        val = st.session_state.resume_data[k].strip()
        if val:
            user_info += f"{label}: {val}\n"
    st.divider()
    st.header("Your Information")
    st.code(user_info, language="markdown")

    # --- AI Resume Generation (FIRST TIME ONLY) ---
    if st.session_state.original_resume_dict is None:
        with st.spinner("AI is generating your resume..."):
            ai_resume_md = generate_resume(user_info)
            parsed_resume = parse_ai_resume(ai_resume_md)
            header_fields = {k: st.session_state.resume_data[k].strip() for k in CONTACT_FIELDS}
            st.session_state.original_resume_dict = {
                "header_fields": header_fields,
                **parsed_resume
            }
            st.session_state.current_resume_dict = st.session_state.original_resume_dict.copy()
            st.session_state.ai_resume_pdf = b""

    if st.session_state.current_resume_dict:
        st.divider()
        st.header("Resume Preview")
        resume_md = reconstruct_resume_from_sections(st.session_state.current_resume_dict)
        st.markdown(resume_md.replace('\n', ' \n'))
        st.divider()

        # --- Modify Info ---
        st.subheader("Modify Information")
        with st.expander("Edit Your Information"):
            edit_data = {}
            for k, label in QUESTIONS:
                edit_data[k] = st.text_area(label, st.session_state.resume_data[k], key=f"edit_{k}")
            update_btn = st.button("Update Information")
            if update_btn:
                updated = False
                # Update contact fields directly in header_fields
                for k in edit_data:
                    if edit_data[k].strip() != st.session_state.resume_data[k].strip():
                        st.session_state.resume_data[k] = edit_data[k].strip()
                        if k in CONTACT_FIELDS:
                            if "header_fields" not in st.session_state.original_resume_dict:
                                st.session_state.original_resume_dict["header_fields"] = {}
                            st.session_state.original_resume_dict["header_fields"][k] = edit_data[k].strip()
                            updated = True
                        elif k in SECTION_MAP:
                            section = SECTION_MAP[k]
                            label = dict(QUESTIONS)[k]
                            with st.spinner(f"Updating {section.title()}..."):
                                new_section_md = generate_resume(f"{label}: {edit_data[k]}")
                                parsed = parse_ai_resume(new_section_md)
                                if section in parsed:
                                    st.session_state.original_resume_dict[section] = parsed[section]
                                    updated = True
                if updated:
                    st.session_state.current_resume_dict = st.session_state.original_resume_dict.copy()
                    st.session_state.ai_resume_pdf = b""
                    st.success("Information updated! Only the changed fields or sections were updated.")
                    st.rerun()
                else:
                    st.warning("No changes detected. Please edit a field and try again.")

        # --- Modify with AI ---
        st.subheader("Modify with AI")
        st.session_state.modify_section = st.selectbox(
            "Which section do you want AI to improve?",
            options=["summary", "skills", "experience", "education", "projects", "certifications"],
            index=0
        )
        st.session_state.modify_instruction = st.text_input(
            "How should AI improve this section? (e.g., 'Make it more concise', 'Add more technical skills')",
            value=st.session_state.modify_instruction,
        )
        if st.button("Modify Section with AI"):
            section = st.session_state.modify_section
            instruction = st.session_state.modify_instruction
            with st.spinner(f"AI is modifying {section.title()}..."):
                new_section_content = modify_resume_section(
                    st.session_state.original_resume_dict,
                    section,
                    instruction
                )
                if new_section_content:
                    st.session_state.original_resume_dict[section] = new_section_content
                    st.session_state.current_resume_dict = st.session_state.original_resume_dict.copy()
                    st.session_state.ai_resume_pdf = b""
                    st.success(f"{section.title()} updated by AI!")
                    st.rerun()
                else:
                    st.error("AI failed to update the section.")

        # --- Generate PDF ---
        if not st.session_state.ai_resume_pdf:
            with st.spinner("Generating PDF..."):
                pdf_bytes = generate_pdf(
                    reconstruct_resume_from_sections(st.session_state.current_resume_dict),
                    st.session_state.current_resume_dict.get("header_fields", {})
                )
                if pdf_bytes:
                    st.session_state.ai_resume_pdf = pdf_bytes
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
                if st.session_state.original_resume_dict:
                    st.session_state.current_resume_dict = st.session_state.original_resume_dict.copy()
                    st.session_state.ai_resume_pdf = b""
                    st.success("Resume restored to original version!")
                    st.rerun()
