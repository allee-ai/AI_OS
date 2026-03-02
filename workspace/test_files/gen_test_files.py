"""Generate test.pdf and test.docx for workspace rendering tests."""
import zipfile, io, os

HERE = os.path.dirname(os.path.abspath(__file__))

# ── PDF ──────────────────────────────────────────────────────────
pdf = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 24 Tf 100 700 Td (Test PDF File) Tj ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000282 00000 n 
0000000376 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
447
%%EOF
"""

with open(os.path.join(HERE, "test.pdf"), "wb") as f:
    f.write(pdf)
print(f"test.pdf  → {len(pdf)} bytes")

# ── DOCX ─────────────────────────────────────────────────────────
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(
        "[Content_Types].xml",
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '  <Default Extension="xml" ContentType="application/xml"/>'
        '  <Override PartName="/word/document.xml"'
        '    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>",
    )
    zf.writestr(
        "_rels/.rels",
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '  <Relationship Id="rId1"'
        '    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
        '    Target="word/document.xml"/>'
        "</Relationships>",
    )
    zf.writestr(
        "word/_rels/document.xml.rels",
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        "</Relationships>",
    )
    zf.writestr(
        "word/document.xml",
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "  <w:body>"
        "    <w:p>"
        '      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
        "      <w:r><w:t>Test DOCX File</w:t></w:r>"
        "    </w:p>"
        "    <w:p>"
        "      <w:r><w:t>This is a test Word document for verifying workspace file rendering.</w:t></w:r>"
        "    </w:p>"
        "    <w:p>"
        "      <w:r><w:rPr><w:b/></w:rPr><w:t>Bold text</w:t></w:r>"
        '      <w:r><w:t xml:space="preserve"> and </w:t></w:r>'
        "      <w:r><w:rPr><w:i/></w:rPr><w:t>italic text</w:t></w:r>"
        '      <w:r><w:t xml:space="preserve"> in the same paragraph.</w:t></w:r>'
        "    </w:p>"
        "  </w:body>"
        "</w:document>",
    )

with open(os.path.join(HERE, "test.docx"), "wb") as f:
    f.write(buf.getvalue())
print(f"test.docx → {len(buf.getvalue())} bytes")
