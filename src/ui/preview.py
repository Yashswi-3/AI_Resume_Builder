import streamlit as st


def render_resume_preview(markdown_content: str, pdf_bytes: bytes | None):
    st.divider()
    st.header("Resume Preview")
    st.markdown(markdown_content.replace("\n", "  \n"))

    st.divider()
    if pdf_bytes:
        st.download_button(
            label="Download Resume as PDF",
            data=pdf_bytes,
            file_name="resume.pdf",
            mime="application/pdf",
        )
    else:
        st.error("PDF generation failed. Please update content and try again.")
