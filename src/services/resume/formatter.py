from typing import List

from src.domain.models import PersonalInfo, ResumeInput, ResumeOutput


class ResumeFormatter:
    def to_markdown(
        self,
        resume_input: ResumeInput,
        resume_output: ResumeOutput,
        template_key: str = "classic",
    ) -> str:
        template = (template_key or "classic").strip().lower()
        if template == "compact":
            return self._to_compact_markdown(resume_input, resume_output)
        if template == "modern":
            return self._to_modern_markdown(resume_input, resume_output)
        return self._to_classic_markdown(resume_input, resume_output)

    def _to_classic_markdown(self, resume_input: ResumeInput, resume_output: ResumeOutput) -> str:
        parts: List[str] = []

        parts.extend(self._header_section(resume_input.personal_info))
        parts.extend(self._section("Professional Summary", resume_output.professional_summary))
        parts.extend(self._section("Skills", resume_output.skills))
        parts.extend(self._section("Education", resume_output.education))
        parts.extend(self._section("Work Experience", resume_output.experience))
        parts.extend(self._section("Projects", resume_output.projects))
        parts.extend(self._section("Certifications", resume_output.certifications))
        parts.extend(self._section("Achievements", resume_output.achievements))

        return "\n".join(parts).strip()

    def _to_compact_markdown(self, resume_input: ResumeInput, resume_output: ResumeOutput) -> str:
        parts: List[str] = []

        parts.extend(self._header_section(resume_input.personal_info))
        parts.extend(self._section("Professional Summary", resume_output.professional_summary))
        parts.extend(self._section("Work Experience", resume_output.experience))
        parts.extend(self._section("Projects", resume_output.projects))
        parts.extend(self._inline_skills_section(resume_output.skills))
        parts.extend(self._section("Education", resume_output.education))
        parts.extend(self._section("Certifications", resume_output.certifications))
        parts.extend(self._section("Achievements", resume_output.achievements))

        return "\n".join(parts).strip()

    def _to_modern_markdown(self, resume_input: ResumeInput, resume_output: ResumeOutput) -> str:
        parts: List[str] = []

        parts.extend(self._header_section(resume_input.personal_info))
        parts.extend(self._section("Professional Summary", resume_output.professional_summary))
        parts.extend(self._inline_skills_section(resume_output.skills))
        parts.extend(self._section("Projects", resume_output.projects))
        parts.extend(self._section("Work Experience", resume_output.experience))
        parts.extend(self._section("Education", resume_output.education))
        parts.extend(self._section("Achievements", resume_output.achievements))
        parts.extend(self._section("Certifications", resume_output.certifications))

        return "\n".join(parts).strip()

    def _header_section(self, personal_info: PersonalInfo) -> List[str]:
        lines: List[str] = []

        name = personal_info.full_name.strip() or "Candidate Name"
        lines.append(f"# {name}")

        contact_parts = [
            personal_info.location.strip(),
            personal_info.phone.strip(),
            personal_info.email.strip(),
        ]
        contact_line = " | ".join(item for item in contact_parts if item)
        if contact_line:
            lines.append(contact_line)

        link_parts = [
            personal_info.linkedin.strip(),
            personal_info.github.strip(),
            personal_info.portfolio.strip(),
        ]
        link_line = " | ".join(item for item in link_parts if item)
        if link_line:
            lines.append(link_line)

        lines.append("")
        return lines

    def _section(self, title: str, values: List[str]) -> List[str]:
        cleaned = [value.strip() for value in values if value and value.strip()]
        if not cleaned:
            return []

        section = [f"## {title}", ""]
        section.extend([f"- {line}" for line in cleaned])
        section.append("")
        return section

    def _inline_skills_section(self, values: List[str]) -> List[str]:
        cleaned = [value.strip() for value in values if value and value.strip()]
        if not cleaned:
            return []

        line = ", ".join(cleaned)
        return ["## Skills", "", line, ""]
