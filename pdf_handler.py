from fpdf import FPDF
import traceback
from utils import clean_text_for_pdf, parse_ai_resume

class PDF(FPDF):
    def __init__(self, header_fields):
        super().__init__()
        self.header_fields = header_fields

    def header(self):
        if self.page_no() == 1:
            self.set_font("Helvetica", "B", 18)
            self.set_text_color(30, 30, 30)
            name = self.header_fields.get('name', '').strip()
            if name:
                self.cell(0, 12, clean_text_for_pdf(name), ln=True, align="C")
            self.ln(2)
            self.set_font("Helvetica", "", 10)
            contact_line = []
            for field in ['location', 'phone', 'email']:
                value = self.header_fields.get(field, '').strip()
                if value:
                    contact_line.append(clean_text_for_pdf(value))
            if contact_line:
                self.set_text_color(80, 80, 80)
                self.cell(0, 7, " | ".join(contact_line), ln=True, align="C")
            links = []
            for label, field in [("LinkedIn", "linkedin"), ("GitHub", "github"), ("Portfolio", "portfolio")]:
                url = self.header_fields.get(field, '').strip()
                if url:
                    links.append((label, url if url.startswith("http") else "https://" + url))
            if links:
                self.set_font("Helvetica", "U", 10)
                self.set_text_color(0, 102, 204)
                link_line = " | ".join(label for label, _ in links)
                self.set_x((210 - self.get_string_width(link_line)) / 2)
                for i, (label, url) in enumerate(links):
                    if i > 0:
                        self.write(7, " | ")
                    self.write(7, label, url)
                self.set_text_color(0, 0, 0)
                self.set_font("Helvetica", "", 11)
                self.ln(8)

    def section_title(self, title):
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(0, 102, 204)
        self.cell(0, 8, title.upper(), ln=True)
        self.set_text_color(0, 0, 0)
        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.5)
        y = self.get_y()
        self.line(10, y, 200, y)
        self.ln(4)

    def add_bullets(self, lines):
        self.set_font("Helvetica", "", 11)
        for line in lines:
            if line.strip():
                self.cell(8)
                self.multi_cell(0, 5, f"- {line.strip('- ')}")
                self.ln(2)

    def add_simple(self, text):
        self.set_font("Helvetica", "", 11)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def add_project(self, title, description, technologies, year):
        self.set_font("Helvetica", "B", 11)
        project_title = clean_text_for_pdf(title) if title else ""
        tech_year_parts = []
        if technologies:
            tech_year_parts.append(clean_text_for_pdf(technologies))
        if year:
            tech_year_parts.append(clean_text_for_pdf(year))
        if tech_year_parts:
            self.cell(0, 6, project_title, ln=False)
            self.set_font("Helvetica", "", 11)
            self.cell(0, 6, f" | {' | '.join(tech_year_parts)}", ln=True)
        else:
            self.cell(0, 6, project_title, ln=True)
        self.ln(1)
        if description:
            bullets = description.split(';')
            self.set_font("Helvetica", "", 11)
            for bullet in bullets:
                bullet = bullet.strip().lstrip('- •—◦▪').strip()
                if bullet:
                    self.cell(8)
                    self.multi_cell(0, 5, f"- {clean_text_for_pdf(bullet)}")
            self.ln(4)

    def body(self, sections):
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
                    project_text = "\n".join(sections[key])
                    projects = project_text.split("||") if "||" in project_text else [project_text]
                    for project in projects:
                        project = project.strip()
                        if not project:
                            continue
                        lines = project.split('\n')
                        title_line = lines[0] if lines else ""
                        if '|' in title_line:
                            parts = [p.strip() for p in title_line.split('|')]
                            proj_title = parts[0] if parts else ""
                            proj_tech = parts[1] if len(parts) > 1 else ""
                            proj_year = parts[2] if len(parts) > 2 else ""
                        else:
                            proj_title = title_line
                            proj_tech = ""
                            proj_year = ""
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
                self.set_draw_color(200, 200, 200)
                self.set_line_width(0.3)
                y = self.get_y()
                if y < 280:
                    self.line(10, y, 200, y)
                self.ln(2)

def generate_pdf(resume_content: str, header_fields: dict) -> bytes:
    try:
        parsed = parse_ai_resume(resume_content)
        pdf = PDF(header_fields)
        pdf.add_page()
        pdf.body(parsed)
        return pdf.output(dest='S').encode('latin1', 'ignore')
    except Exception as e:
        print("PDF generation error:", e)
        traceback.print_exc()
        return None
