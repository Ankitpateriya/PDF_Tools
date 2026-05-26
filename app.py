from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from PIL import Image
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_LIMIT_MB = int(os.environ.get("UPLOAD_LIMIT_MB", "50"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = UPLOAD_LIMIT_MB * 1024 * 1024
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-before-production")


def uploaded_files(field_name: str = "files"):
    return [file for file in request.files.getlist(field_name) if file and file.filename]


def pdf_response(buffer: io.BytesIO, filename: str):
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


def zip_response(buffer: io.BytesIO, filename: str):
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


@app.get("/")
def index():
    tools = [
        {
            "id": "merge",
            "title": "Merge PDF",
            "description": "Combine multiple PDF files in the order you upload them.",
            "accept": ".pdf",
            "multiple": True,
        },
        {
            "id": "split",
            "title": "Split PDF",
            "description": "Download every page of one PDF as a separate PDF inside a ZIP.",
            "accept": ".pdf",
            "multiple": False,
        },
        {
            "id": "compress",
            "title": "Compress PDF",
            "description": "Shrink scanned/image PDFs by rebuilding pages as optimized JPEG images.",
            "accept": ".pdf",
            "multiple": False,
        },
        {
            "id": "rotate",
            "title": "Rotate PDF",
            "description": "Rotate all pages by 90, 180, or 270 degrees.",
            "accept": ".pdf",
            "multiple": False,
        },
        {
            "id": "images-to-pdf",
            "title": "Images to PDF",
            "description": "Convert JPG, PNG, and WebP images into a single PDF.",
            "accept": ".jpg,.jpeg,.png,.webp",
            "multiple": True,
        },
        {
            "id": "extract-text",
            "title": "Extract Text",
            "description": "Extract selectable text from a PDF into a TXT file.",
            "accept": ".pdf",
            "multiple": False,
        },
        {
            "id": "watermark",
            "title": "Add Watermark",
            "description": "Stamp text across every page of a PDF.",
            "accept": ".pdf",
            "multiple": False,
        },
        {
            "id": "protect",
            "title": "Protect PDF",
            "description": "Add a password to a PDF file.",
            "accept": ".pdf",
            "multiple": False,
        },
    ]
    return render_template("index.html", tools=tools)


@app.post("/tool/<tool_id>")
def run_tool(tool_id: str):
    files = uploaded_files()
    if not files:
        flash("Please choose at least one file.")
        return redirect(url_for("index"))

    try:
        if tool_id == "merge":
            return merge_pdfs(files)
        if tool_id == "split":
            return split_pdf(files[0])
        if tool_id == "compress":
            quality = int(request.form.get("quality", "55"))
            dpi = int(request.form.get("dpi", "120"))
            return compress_pdf(files[0], quality=quality, dpi=dpi)
        if tool_id == "rotate":
            angle = int(request.form.get("angle", "90"))
            return rotate_pdf(files[0], angle)
        if tool_id == "images-to-pdf":
            return images_to_pdf(files)
        if tool_id == "extract-text":
            return extract_text(files[0])
        if tool_id == "watermark":
            text = request.form.get("watermark_text", "ankitji.com")
            return add_watermark(files[0], text)
        if tool_id == "protect":
            password = request.form.get("password", "")
            if not password:
                flash("Please enter a password.")
                return redirect(url_for("index"))
            return protect_pdf(files[0], password)
    except Exception as exc:
        flash(f"Could not process that file: {exc}")
        return redirect(url_for("index"))

    flash("Unknown tool.")
    return redirect(url_for("index"))


def merge_pdfs(files):
    writer = PdfWriter()
    for file in files:
        reader = PdfReader(file.stream)
        for page in reader.pages:
            writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return pdf_response(output, "ankitji-merged.pdf")


def split_pdf(file):
    reader = PdfReader(file.stream)
    output = io.BytesIO()
    original_name = Path(secure_filename(file.filename)).stem or "document"

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, page in enumerate(reader.pages, start=1):
            writer = PdfWriter()
            writer.add_page(page)
            page_buffer = io.BytesIO()
            writer.write(page_buffer)
            archive.writestr(f"{original_name}-page-{index}.pdf", page_buffer.getvalue())

    return zip_response(output, "ankitji-split-pages.zip")


def compress_pdf(file, quality: int = 55, dpi: int = 120):
    quality = max(20, min(quality, 95))
    dpi = max(72, min(dpi, 200))
    document = pdfium.PdfDocument(file.read())
    images = []

    try:
        scale = dpi / 72
        for page_index in range(len(document)):
            page = document[page_index]
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil().convert("RGB")
            images.append(image.copy())
            image.close()
            page.close()

        if not images:
            raise ValueError("No pages found in the PDF.")

        output = io.BytesIO()
        first, rest = images[0], images[1:]
        first.save(
            output,
            format="PDF",
            save_all=True,
            append_images=rest,
            resolution=dpi,
            quality=quality,
            optimize=True,
        )
        return pdf_response(output, "ankitji-compressed.pdf")
    finally:
        document.close()
        for image in images:
            image.close()


def rotate_pdf(file, angle: int):
    if angle not in {90, 180, 270}:
        angle = 90

    reader = PdfReader(file.stream)
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(angle)
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return pdf_response(output, "ankitji-rotated.pdf")


def images_to_pdf(files):
    images = []
    try:
        for file in files:
            image = Image.open(file.stream).convert("RGB")
            images.append(image.copy())

        if not images:
            raise ValueError("No valid images were uploaded.")

        output = io.BytesIO()
        first, rest = images[0], images[1:]
        first.save(output, format="PDF", save_all=True, append_images=rest)
        return pdf_response(output, "ankitji-images.pdf")
    finally:
        for image in images:
            image.close()


def extract_text(file):
    reader = PdfReader(file.stream)
    parts = []
    for page_index, page in enumerate(reader.pages, start=1):
        parts.append(f"--- Page {page_index} ---\n{page.extract_text() or ''}")

    output = io.BytesIO("\n\n".join(parts).encode("utf-8"))
    output.seek(0)
    return send_file(
        output,
        mimetype="text/plain",
        as_attachment=True,
        download_name="ankitji-extracted-text.txt",
    )


def add_watermark(file, text: str):
    reader = PdfReader(file.stream)
    writer = PdfWriter()

    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        watermark = build_watermark_page(text, width, height)
        page.merge_page(watermark)
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return pdf_response(output, "ankitji-watermarked.pdf")


def build_watermark_page(text: str, width: float, height: float):
    packet = io.BytesIO()
    pdf_canvas = canvas.Canvas(packet, pagesize=(width, height))
    pdf_canvas.saveState()
    pdf_canvas.translate(width / 2, height / 2)
    pdf_canvas.rotate(35)
    pdf_canvas.setFillColor(Color(0.72, 0.12, 0.12, alpha=0.18))
    pdf_canvas.setFont("Helvetica-Bold", 52)
    pdf_canvas.drawCentredString(0, 0, text[:80])
    pdf_canvas.restoreState()
    pdf_canvas.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]


def protect_pdf(file, password: str):
    reader = PdfReader(file.stream)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    writer.encrypt(user_password=password, owner_password=password)
    output = io.BytesIO()
    writer.write(output)
    return pdf_response(output, "ankitji-protected.pdf")


@app.errorhandler(413)
def file_too_large(_error):
    flash(f"Upload is too large. Current limit is {UPLOAD_LIMIT_MB} MB.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
