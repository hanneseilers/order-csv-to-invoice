from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

class HTMLRenderer:
    def __init__(self, templates_dir: str):
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render_to_pdf(self, out_pdf: Path, context: dict, template_name: str = "invoice.html"):
        """Render a given template (default: invoice.html) to PDF."""
        template = self.env.get_template(template_name)
        html = template.render(**context)
        HTML(string=html, base_url=str(Path.cwd())).write_pdf(str(out_pdf))