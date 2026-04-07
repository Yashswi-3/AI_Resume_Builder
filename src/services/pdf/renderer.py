import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

from fpdf import FPDF

from src.domain.models import EducationItem, ExperienceItem, PersonalInfo, ProjectItem, ResumeInput, ResumeOutput
from src.utils.text_utils import clean_text_for_pdf

HEADING_COLOR = (15, 69, 57)
BODY_COLOR = (68, 68, 68)
LINK_COLOR = (15, 69, 57)

PT_TO_MM = 0.352778
LATEX_SECTION_SPACING_MM = 6 * PT_TO_MM
LATEX_LIST_ITEM_SPACING_MM = 2 * PT_TO_MM
LATEX_HEADER_NAME_CONTACT_GAP_MM = 6 * PT_TO_MM
LATEX_HEADER_LINK_GAP_MM = 4 * PT_TO_MM
LATEX_HEADER_AFTER_GAP_MM = 8 * PT_TO_MM
LATEX_HEADER_TOP_OFFSET_MM = -1 * PT_TO_MM

DEFAULT_FONT_FAMILY = "Helvetica"
LATEX_FONT_FAMILY = "LatinModern"
LATEX_SMALL_CAPS_FONT_FAMILY = "LatinModernCaps"
LATEX_FONT_FILES: Dict[str, List[str]] = {
    "": [
        "lmroman10-regular.otf",
        "lmroman12-regular.otf",
        "LatinModernRoman-Regular.ttf",
        "cmunrm.ttf",
        "CMUSerif-Roman.ttf",
    ],
    "B": [
        "lmroman10-bold.otf",
        "lmroman12-bold.otf",
        "LatinModernRoman-Bold.ttf",
        "cmunbx.ttf",
        "CMUSerif-Bold.ttf",
    ],
    "I": [
        "lmroman10-italic.otf",
        "lmroman12-italic.otf",
        "LatinModernRoman-Italic.ttf",
        "cmunti.ttf",
        "CMUSerif-Italic.ttf",
    ],
    "BI": [
        "lmroman10-bolditalic.otf",
        "lmroman12-bolditalic.otf",
        "LatinModernRoman-BoldItalic.ttf",
        "cmunbi.ttf",
        "CMUSerif-BoldItalic.ttf",
    ],
}
LATEX_SMALL_CAPS_FONT_FILES = [
    "lmromancaps10-regular.otf",
    "LatinModernRomanCaps-Regular.ttf",
    "CMUSerifSC-Regular.ttf",
]

NAME_FONT_SIZE = 24
HEADER_LINK_FONT_SIZE = 10
HEADER_CONTACT_FONT_SIZE = 10
SECTION_TITLE_FONT_SIZE = 13
SUBHEADING_LEFT_FONT_SIZE = 11
SUBHEADING_RIGHT_FONT_SIZE = 10
SUBHEADING_META_FONT_SIZE = 10
BODY_FONT_SIZE = 9.6
BULLET_LINE_HEIGHT = 4.3
SECTION_TITLE_LINE_HEIGHT = 6
SUBHEADING_LINE_HEIGHT = 5.0
SUBHEADING_META_LINE_HEIGHT = 4.5
SUBHEADING_AFTER_GAP_MM = LATEX_LIST_ITEM_SPACING_MM
HEADER_CONTACT_LINE_HEIGHT = 4.8
HEADER_LINK_LINE_HEIGHT = (HEADER_LINK_FONT_SIZE * PT_TO_MM) + LATEX_HEADER_LINK_GAP_MM

SECTION_NOISE = {
    "skills",
    "skill",
    "education",
    "work experience",
    "experience",
    "projects",
    "project",
    "certifications",
    "certification",
    "achievements",
    "achievement",
    "hievements",
}


@dataclass
class _ExperienceBlock:
    role: str = ""
    company: str = ""
    duration: str = ""
    location: str = ""
    bullets: List[str] = field(default_factory=list)


@dataclass
class _ProjectBlock:
    name: str = ""
    technologies: str = ""
    year: str = ""
    bullets: List[str] = field(default_factory=list)


@dataclass
class _EducationBlock:
    institution: str = ""
    duration: str = ""
    degree: str = ""
    location: str = ""
    details: str = ""

class _ResumePdf(FPDF):
    def __init__(self, personal_info: PersonalInfo):
        super().__init__(format="Letter")
        self.personal_info = personal_info
        self._font_family = DEFAULT_FONT_FAMILY
        self._font_styles = {"", "B", "I", "BI"}
        self._name_font_family = DEFAULT_FONT_FAMILY
        self._name_font_style = "B"
        self._configure_font_family()
        self.set_margins(11, 10, 11)
        self.set_auto_page_break(auto=True, margin=12)

    def _safe(self, value: str) -> str:
        text = clean_text_for_pdf(value or "")
        text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
        return " ".join(text.strip().split())

    def _compact_link(self, value: str) -> str:
        text = self._safe(value)
        lowered = text.lower()
        if lowered.startswith("https://"):
            text = text[8:]
        elif lowered.startswith("http://"):
            text = text[7:]
        if text.lower().startswith("www."):
            text = text[4:]
        return text.rstrip("/")

    def _configure_font_family(self):
        if self._register_latex_fonts():
            return

        self._font_family = DEFAULT_FONT_FAMILY
        self._font_styles = {"", "B", "I", "BI"}
        self._name_font_family = DEFAULT_FONT_FAMILY
        self._name_font_style = "B"

    def _register_latex_fonts(self) -> bool:
        search_dirs = self._font_search_dirs()
        style_paths = {
            style: self._resolve_font_path(LATEX_FONT_FILES.get(style, []), search_dirs)
            for style in ["", "B", "I", "BI"]
        }
        regular_font = style_paths.get("", "")
        if not regular_font:
            return False

        try:
            self.add_font(LATEX_FONT_FAMILY, "", regular_font)
            self._font_styles = {""}

            for style in ["B", "I", "BI"]:
                style_font = style_paths.get(style, "")
                if not style_font:
                    continue
                self.add_font(LATEX_FONT_FAMILY, style, style_font)
                self._font_styles.add(style)

            self._name_font_family = LATEX_FONT_FAMILY
            self._name_font_style = "B"
            small_caps_font = self._resolve_font_path(LATEX_SMALL_CAPS_FONT_FILES, search_dirs)
            if small_caps_font:
                self.add_font(LATEX_SMALL_CAPS_FONT_FAMILY, "", small_caps_font)
                self._name_font_family = LATEX_SMALL_CAPS_FONT_FAMILY
                self._name_font_style = ""

            self._font_family = LATEX_FONT_FAMILY
            return True
        except Exception:
            self._font_family = DEFAULT_FONT_FAMILY
            self._font_styles = {"", "B", "I", "BI"}
            self._name_font_family = DEFAULT_FONT_FAMILY
            self._name_font_style = "B"
            return False

    def _font_search_dirs(self) -> List[Path]:
        search_dirs: List[Path] = []

        repo_root = Path(__file__).resolve().parents[3]
        local_candidates = [
            repo_root / "assets" / "fonts",
            repo_root / "assets" / "fonts" / "latin-modern",
            repo_root / "assets" / "fonts" / "computer-modern",
            repo_root / "fonts",
            Path("C:/Windows/Fonts"),
            Path("C:/Program Files/MiKTeX/fonts/opentype/public/lm"),
            Path("C:/Program Files/MiKTeX/fonts/truetype/public/lm"),
            Path.home() / "AppData/Local/Programs/MiKTeX/fonts/opentype/public/lm",
            Path.home() / "AppData/Local/Programs/MiKTeX/fonts/truetype/public/lm",
        ]

        texlive_root = Path("C:/texlive")
        if texlive_root.exists():
            for version_dir in texlive_root.iterdir():
                if not version_dir.is_dir():
                    continue
                local_candidates.append(version_dir / "texmf-dist/fonts/opentype/public/lm")
                local_candidates.append(version_dir / "texmf-dist/fonts/truetype/public/lm")

        seen = set()
        for directory in local_candidates:
            normalized = str(directory).lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            if directory.exists() and directory.is_dir():
                search_dirs.append(directory)

        return search_dirs

    def _resolve_font_path(self, file_names: Sequence[str], search_dirs: Sequence[Path]) -> str:
        for directory in search_dirs:
            for file_name in file_names:
                candidate = directory / file_name
                if candidate.exists() and candidate.is_file():
                    return str(candidate)
        return ""

    def _set_resume_font(self, style: str, size: float):
        normalized_style = "".join(char for char in style.upper() if char in {"B", "I"})

        if self._font_family == DEFAULT_FONT_FAMILY:
            self.set_font(self._font_family, normalized_style, size)
            return

        style_fallbacks = {
            "": [""],
            "B": ["B", ""],
            "I": ["I", ""],
            "BI": ["BI", "B", "I", ""],
        }
        for fallback_style in style_fallbacks.get(normalized_style, [""]):
            if fallback_style in self._font_styles:
                self.set_font(self._font_family, fallback_style, size)
                return

        self.set_font(DEFAULT_FONT_FAMILY, normalized_style, size)

    def _set_name_font(self, size: float):
        if self._name_font_family == LATEX_SMALL_CAPS_FONT_FAMILY:
            self.set_font(self._name_font_family, "", size)
            return

        if self._name_font_family == LATEX_FONT_FAMILY and self._name_font_style in self._font_styles:
            self.set_font(self._name_font_family, self._name_font_style, size)
            return

        self._set_resume_font("B", size)

    def header(self):
        if self.page_no() != 1:
            return

        start_y = self.get_y() + LATEX_HEADER_TOP_OFFSET_MM
        total_width = self.content_width()
        left_width = total_width * 0.55
        right_width = total_width * 0.40
        right_x = self.w - self.r_margin - right_width

        name = self._safe(self.personal_info.full_name) or "Candidate Name"
        display_name = name if self._name_font_family == LATEX_SMALL_CAPS_FONT_FAMILY else name.upper()

        self.set_xy(self.l_margin, start_y)
        self._set_name_font(NAME_FONT_SIZE)
        self.set_text_color(*HEADING_COLOR)
        self.multi_cell(left_width, 8.2, display_name)
        left_end_y = self.get_y()

        self._set_resume_font("", HEADER_LINK_FONT_SIZE)
        self.set_text_color(*LINK_COLOR)
        links = [
            self._compact_link(self.personal_info.portfolio.strip()),
            self._compact_link(self.personal_info.linkedin.strip()),
            self._compact_link(self.personal_info.github.strip()),
        ]
        links = [link for link in links if link]

        right_y = start_y
        for link in links:
            self.set_xy(right_x, right_y)
            self.multi_cell(right_width, HEADER_LINK_LINE_HEIGHT, link, align="R")
            right_y = self.get_y()
        right_end_y = right_y if links else start_y

        contact_parts = [
            self.personal_info.phone.strip(),
            self.personal_info.email.strip(),
            self.personal_info.location.strip(),
        ]
        contact_line = " | ".join(self._safe(part) for part in contact_parts if part)
        if contact_line:
            self.set_y(left_end_y + LATEX_HEADER_NAME_CONTACT_GAP_MM)
            self.set_x(self.l_margin)
            self._set_resume_font("", HEADER_CONTACT_FONT_SIZE)
            self.set_text_color(*BODY_COLOR)
            self.multi_cell(total_width, HEADER_CONTACT_LINE_HEIGHT, contact_line)
            left_end_y = self.get_y()

        self.set_text_color(*BODY_COLOR)
        self.set_y(max(left_end_y, right_end_y) + LATEX_HEADER_AFTER_GAP_MM)

    def content_width(self, indent: float = 0) -> float:
        return max(12, self.w - self.l_margin - self.r_margin - indent)

    def ensure_space(self, height_needed: float):
        if self.get_y() + height_needed > self.h - self.b_margin:
            self.add_page()

    def section_title(self, title: str):
        self.ensure_space(LATEX_SECTION_SPACING_MM + 10)
        self.set_y(self.get_y() + LATEX_SECTION_SPACING_MM)
        self._set_resume_font("B", SECTION_TITLE_FONT_SIZE)
        self.set_text_color(*HEADING_COLOR)
        self.set_x(self.l_margin)
        self.cell(0, SECTION_TITLE_LINE_HEIGHT, self._safe(title.upper()), ln=True)

        y = self.get_y()
        self.set_draw_color(*HEADING_COLOR)
        self.set_line_width(0.3)
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(LATEX_SECTION_SPACING_MM)
        self.set_text_color(*BODY_COLOR)

    def subheading(self, title: str, right_title: str, subtitle: str, right_subtitle: str):
        self.ensure_space(12)
        width = self.content_width()
        right_width = min(62, max(42, width * 0.33))
        left_width = width - right_width

        self._set_resume_font("B", SUBHEADING_LEFT_FONT_SIZE)
        self.set_text_color(*BODY_COLOR)
        self.set_x(self.l_margin)
        self.cell(left_width, SUBHEADING_LINE_HEIGHT, self._safe(title), ln=0, align="L")
        self._set_resume_font("B", SUBHEADING_RIGHT_FONT_SIZE)
        self.cell(right_width, SUBHEADING_LINE_HEIGHT, self._safe(right_title), ln=1, align="R")

        if subtitle or right_subtitle:
            self._set_resume_font("I", SUBHEADING_META_FONT_SIZE)
            self.set_x(self.l_margin)
            self.cell(left_width, SUBHEADING_META_LINE_HEIGHT, self._safe(subtitle), ln=0, align="L")
            self.cell(right_width, SUBHEADING_META_LINE_HEIGHT, self._safe(right_subtitle), ln=1, align="R")

        self.ln(SUBHEADING_AFTER_GAP_MM)

    def bullet_list(self, values: Sequence[str]):
        cleaned_values = [self._safe(value) for value in values if self._safe(value)]
        if not cleaned_values:
            return

        self._set_resume_font("", BODY_FONT_SIZE)
        self.set_text_color(*BODY_COLOR)
        indent = 4.5
        width = self.content_width(indent)

        for index, value in enumerate(cleaned_values):
            self.ensure_space(6)
            self.set_x(self.l_margin + indent)
            self.multi_cell(width, BULLET_LINE_HEIGHT, f"- {value}")
            if index < len(cleaned_values) - 1:
                self.ln(LATEX_LIST_ITEM_SPACING_MM)
        self.ln(LATEX_LIST_ITEM_SPACING_MM)


class ResumePdfRenderer:
    def render(
        self,
        resume_input: ResumeInput,
        resume_output: ResumeOutput,
        template_key: str = "classic",
    ) -> bytes | None:
        try:
            pdf = _ResumePdf(resume_input.personal_info)
            pdf.add_page()

            summary_lines = self._summary_lines(resume_input, resume_output)
            experience_blocks = self._experience_blocks(resume_input.experiences, resume_output.experience)
            project_blocks = self._project_blocks(resume_input.projects, resume_output.projects)
            achievements = self._simple_section_lines(resume_output.achievements, resume_input.achievements)
            skill_lines = self._skill_lines(resume_output.skills, resume_input.skills)
            certifications = self._simple_section_lines(resume_output.certifications, resume_input.certifications)
            education_blocks = self._education_blocks(resume_input.education, resume_output.education)

            sections = self._section_sequence(template_key)
            for section in sections:
                if section == "summary" and summary_lines:
                    pdf.section_title("Professional Summary")
                    pdf.bullet_list(summary_lines)

                if section == "experience" and experience_blocks:
                    pdf.section_title("Experience")
                    for block in experience_blocks:
                        title = block.company.strip() or block.role.strip() or "Experience"
                        subtitle = block.role.strip() if block.company.strip() and block.role.strip() else ""
                        pdf.subheading(title, block.duration, subtitle, block.location)
                        pdf.bullet_list(block.bullets)

                if section == "projects" and project_blocks:
                    pdf.section_title("Projects")
                    for block in project_blocks:
                        title = block.name or "Project"
                        pdf.subheading(title, block.year, block.technologies, "")
                        pdf.bullet_list(block.bullets)

                if section == "skills" and skill_lines:
                    pdf.section_title("Technical Skills")
                    pdf.bullet_list(skill_lines)

                if section == "education" and education_blocks:
                    pdf.section_title("Education")
                    for block in education_blocks:
                        subtitle = self._join_non_empty(
                            [block.degree, block.details],
                            " | ",
                        )
                        title = block.institution or "Education"
                        pdf.subheading(title, block.duration, subtitle, block.location)
                        pdf.ln(LATEX_LIST_ITEM_SPACING_MM)

                if section == "certifications" and certifications:
                    pdf.section_title("Certifications")
                    pdf.bullet_list(certifications)

                if section == "achievements" and achievements:
                    pdf.section_title("Achievements")
                    pdf.bullet_list(achievements)

            output = pdf.output(dest="S")
            if isinstance(output, str):
                return output.encode("latin1", "ignore")
            if isinstance(output, (bytes, bytearray)):
                return bytes(output)
            return bytes(output)
        except Exception as error:
            print("PDF generation error:", error)
            traceback.print_exc()
            return None

    def _section_sequence(self, template_key: str) -> List[str]:
        template = (template_key or "classic").strip().lower()
        if template == "compact":
            return [
                "summary",
                "skills",
                "experience",
                "projects",
                "education",
                "certifications",
                "achievements",
            ]
        if template == "modern":
            return [
                "summary",
                "projects",
                "experience",
                "skills",
                "education",
                "achievements",
                "certifications",
            ]

        return [
            "summary",
            "experience",
            "projects",
            "achievements",
            "skills",
            "certifications",
            "education",
        ]

    def _summary_lines(self, resume_input: ResumeInput, resume_output: ResumeOutput) -> List[str]:
        lines = self._clean_lines(resume_output.professional_summary)
        if not lines and resume_input.career_summary.strip():
            lines = [resume_input.career_summary.strip()]
        return lines

    def _experience_blocks(
        self,
        input_items: List[ExperienceItem],
        output_lines: List[str],
    ) -> List[_ExperienceBlock]:
        parsed = self._parse_experience_lines(output_lines)
        if parsed and any(block.bullets for block in parsed):
            return parsed

        blocks: List[_ExperienceBlock] = []
        for item in input_items:
            blocks.append(
                _ExperienceBlock(
                    role=item.role.strip(),
                    company=item.company.strip(),
                    duration=item.duration.strip(),
                    location=item.location.strip(),
                    bullets=self._clean_lines(item.bullet_points),
                )
            )
        return [
            block
            for block in blocks
            if any([block.role, block.company, block.duration, block.location, block.bullets])
        ]

    def _project_blocks(
        self,
        input_items: List[ProjectItem],
        output_lines: List[str],
    ) -> List[_ProjectBlock]:
        parsed = self._parse_project_lines(output_lines)
        if parsed and any(block.bullets for block in parsed):
            return parsed

        blocks: List[_ProjectBlock] = []
        for item in input_items:
            blocks.append(
                _ProjectBlock(
                    name=item.name.strip(),
                    technologies=item.technologies.strip(),
                    year=item.year.strip(),
                    bullets=self._clean_lines(item.bullet_points),
                )
            )
        return [
            block
            for block in blocks
            if any([block.name, block.technologies, block.year, block.bullets])
        ]

    def _education_blocks(
        self,
        input_items: List[EducationItem],
        output_lines: List[str],
    ) -> List[_EducationBlock]:
        parsed = self._parse_education_lines(output_lines)
        if parsed:
            return parsed

        blocks: List[_EducationBlock] = []
        for item in input_items:
            blocks.append(
                _EducationBlock(
                    institution=item.institution.strip(),
                    duration=item.duration.strip(),
                    degree=item.degree.strip(),
                    location=item.location.strip(),
                    details=item.details.strip(),
                )
            )
        return [
            block
            for block in blocks
            if any([block.institution, block.duration, block.degree, block.location, block.details])
        ]

    def _simple_section_lines(self, output_lines: List[str], input_lines: List[str]) -> List[str]:
        cleaned_output = self._clean_lines(output_lines)
        if cleaned_output:
            return cleaned_output
        return self._clean_lines(input_lines)

    def _skill_lines(self, output_skills: List[str], input_skills: List[str]) -> List[str]:
        skills = self._simple_section_lines(output_skills, input_skills)
        if not skills:
            return []

        lines: List[str] = []
        current: List[str] = []
        for skill in skills:
            candidate = ", ".join(current + [skill])
            if len(candidate) > 95 and current:
                lines.append(", ".join(current))
                current = [skill]
            else:
                current.append(skill)

        if current:
            lines.append(", ".join(current))
        return lines

    def _parse_experience_lines(self, lines: List[str]) -> List[_ExperienceBlock]:
        cleaned_lines = self._clean_lines(lines)
        blocks: List[_ExperienceBlock] = []
        current: _ExperienceBlock | None = None

        for line in cleaned_lines:
            parts = [part.strip() for part in line.split("|")]
            if len(parts) >= 4 and parts[0]:
                if current is not None:
                    blocks.append(current)
                current = _ExperienceBlock(
                    role=parts[0],
                    company=parts[1],
                    duration=parts[2],
                    location=parts[3],
                    bullets=[],
                )
                continue

            if current is None:
                current = _ExperienceBlock(bullets=[])
            current.bullets.append(line.lstrip("- ").strip())

        if current is not None:
            blocks.append(current)

        return [
            block
            for block in blocks
            if any([block.role, block.company, block.duration, block.location, block.bullets])
        ]

    def _parse_project_lines(self, lines: List[str]) -> List[_ProjectBlock]:
        cleaned_lines = self._clean_lines(lines)
        blocks: List[_ProjectBlock] = []
        current: _ProjectBlock | None = None

        for line in cleaned_lines:
            parts = [part.strip() for part in line.split("|")]
            if len(parts) >= 3 and parts[0]:
                if current is not None:
                    blocks.append(current)
                current = _ProjectBlock(
                    name=parts[0],
                    technologies=parts[1],
                    year=parts[2],
                    bullets=[],
                )
                continue

            if current is None:
                current = _ProjectBlock(bullets=[])
            current.bullets.append(line.lstrip("- ").strip())

        if current is not None:
            blocks.append(current)

        return [
            block
            for block in blocks
            if any([block.name, block.technologies, block.year, block.bullets])
        ]

    def _parse_education_lines(self, lines: List[str]) -> List[_EducationBlock]:
        blocks: List[_EducationBlock] = []
        for line in self._clean_lines(lines):
            parts = [part.strip() for part in line.split("|")]
            if len(parts) < 2:
                continue

            degree = parts[0]
            institution = parts[1] if len(parts) > 1 else ""
            duration = parts[2] if len(parts) > 2 else ""
            location_field = parts[3] if len(parts) > 3 else ""
            details = " | ".join(parts[4:]).strip() if len(parts) > 4 else ""

            location = location_field
            if " - " in location_field and not details:
                first, second = location_field.split(" - ", 1)
                location = first.strip()
                details = second.strip()

            blocks.append(
                _EducationBlock(
                    institution=institution,
                    duration=duration,
                    degree=degree,
                    location=location,
                    details=details,
                )
            )

        return [
            block
            for block in blocks
            if any([block.institution, block.duration, block.degree, block.location, block.details])
        ]

    def _clean_lines(self, lines: Sequence[str]) -> List[str]:
        cleaned: List[str] = []
        seen = set()

        for raw in lines:
            text = (raw or "").strip()
            if not text:
                continue

            normalized = self._normalize_for_noise(text)
            if not normalized or normalized in SECTION_NOISE:
                continue

            if normalized in seen:
                continue
            seen.add(normalized)

            cleaned.append(text)

        return cleaned

    def _normalize_for_noise(self, text: str) -> str:
        value = text.strip().lower()
        value = value.lstrip("#-*• ").strip()
        value = value.strip(" :.-")
        return value

    def _join_non_empty(self, parts: Sequence[str], separator: str = " | ") -> str:
        values = [part.strip() for part in parts if part and part.strip()]
        return separator.join(values)
