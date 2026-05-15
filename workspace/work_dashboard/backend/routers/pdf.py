"""PDF generation router — Chrome headless, same approach as original dashboard.py."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import os
import subprocess
import tempfile
import shutil
from datetime import date

from backend.database import get_db

router = APIRouter(tags=["pdf"])

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend")


def _get_dashboard_html() -> str:
    path = os.path.join(FRONTEND_DIR, "dashboard.html")
    with open(path) as f:
        return f.read()


def _get_data_json() -> str:
    """Build the legacy JSON shape from SQLite for baking into HTML."""
    db = get_db()
    result: dict[str, list] = {"completed": [], "scheduled": [], "pending": [], "payments": []}

    for status in ("completed", "scheduled", "pending"):
        rows = db.execute(
            """SELECT p.address, j.description, j.cost
               FROM jobs j JOIN properties p ON j.property_id = p.id
               WHERE j.status = ? ORDER BY j.id""",
            (status,),
        ).fetchall()
        result[status] = [[r["address"], r["description"], str(int(r["cost"]))] for r in rows]

    payments = db.execute("SELECT date, amount, note FROM payments ORDER BY id").fetchall()
    result["payments"] = [[r["date"], str(int(r["amount"])), r["note"] or ""] for r in payments]

    db.close()
    import json
    return json.dumps(result)


@router.post("/save-pdf")
def save_pdf():
    browsers = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    browser = None
    for b in browsers:
        if os.path.exists(b):
            browser = b
            break
    if not browser:
        return JSONResponse(status_code=500, content={"error": "No Chromium browser found"})

    stamp = date.today().isoformat()
    output = os.path.expanduser(f"~/Desktop/Update_{stamp}.pdf")

    tmpdir = tempfile.mkdtemp(prefix="chrome_pdf_")
    try:
        html = _get_dashboard_html()
        data_json = _get_data_json()

        # Bake data into HTML so Chrome renders from file://
        inject = (
            f"\nvar _bakedData = {data_json};\n"
            "if (_bakedData && (_bakedData.completed || _bakedData.scheduled || _bakedData.pending)) {\n"
            "  populateFromData(_bakedData); recalc();\n"
            "}\n"
        )
        html = html.replace("</script>", inject + "</script>", 1)
        html = html.replace("<title>Jake \u2014 Project Dashboard</title>", "<title>Project Overview</title>")
        html = html.replace(
            "</style>",
            "@page { margin: 0; size: letter; }\nbody { padding: 15mm 10mm !important; }\n</style>",
        )

        tmphtml = os.path.join(tmpdir, "invoice.html")
        with open(tmphtml, "w") as f:
            f.write(html)

        subprocess.run(
            [
                browser,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                f"--print-to-pdf={output}",
                "--print-to-pdf-no-header",
                "--virtual-time-budget=5000",
                f"file://{tmphtml}?invoice=1",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )

        if os.path.exists(output):
            return {"path": output}
        return JSONResponse(status_code=500, content={"error": "PDF was not created"})

    except subprocess.TimeoutExpired:
        return JSONResponse(status_code=500, content={"error": "Timed out generating PDF"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
