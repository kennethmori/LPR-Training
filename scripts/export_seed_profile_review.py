from __future__ import annotations

import json
import shutil
import sqlite3
from html import escape
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "outputs" / "app_data" / "plate_events.db"
EXPORT_DIR = BASE_DIR / "seed_profile_review"


CATEGORY_STYLES = {
    "student": {"bg": "#d8ecff", "fg": "#123b63", "accent": "#1f6db3"},
    "staff": {"bg": "#e6f7ef", "fg": "#145539", "accent": "#1e8a57"},
    "faculty": {"bg": "#fff0d8", "fg": "#6b4306", "accent": "#c77707"},
    "contractor": {"bg": "#e8ecf8", "fg": "#26345d", "accent": "#4b61a1"},
    "alumni": {"bg": "#fde7ea", "fg": "#6a2230", "accent": "#b6435f"},
}


def ensure_export_dirs() -> dict[str, Path]:
    asset_dirs = {
        "root": EXPORT_DIR,
        "profile": EXPORT_DIR / "profile_photos",
        "crop": EXPORT_DIR / "plate_crops",
        "frame": EXPORT_DIR / "annotated_frames",
    }
    for path in asset_dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return asset_dirs


def initials(name: str) -> str:
    parts = [part for part in str(name or "").strip().split() if part][:2]
    if not parts:
        return "--"
    return "".join(part[0].upper() for part in parts)


def write_profile_svg(target: Path, owner_name: str, category: str, plate_number: str) -> None:
    style = CATEGORY_STYLES.get(str(category or "").lower(), {"bg": "#edf2f8", "fg": "#21344f", "accent": "#597393"})
    avatar_initials = initials(owner_name)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="720" viewBox="0 0 640 720">
<rect width="640" height="720" rx="36" fill="{style['bg']}"/>
<circle cx="320" cy="252" r="118" fill="{style['accent']}" opacity="0.18"/>
<circle cx="320" cy="230" r="74" fill="{style['accent']}" opacity="0.9"/>
<path d="M196 450c24-76 88-120 124-120s100 44 124 120v94H196z" fill="{style['accent']}" opacity="0.9"/>
<circle cx="320" cy="250" r="92" fill="{style['accent']}" opacity="0.18"/>
<text x="320" y="610" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="54" font-weight="700" fill="{style['fg']}">{escape(avatar_initials)}</text>
<text x="320" y="655" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="26" fill="{style['fg']}">{escape(str(owner_name or 'Sample Profile'))}</text>
<text x="320" y="688" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="20" fill="{style['accent']}">{escape(str(plate_number or 'NO-PLATE'))}</text>
</svg>
"""
    target.write_text(svg, encoding="utf-8")


def safe_copy(source_value: str | None, target_dir: Path, target_name: str) -> str | None:
    source_text = str(source_value or "").strip()
    if not source_text:
        return None
    source = Path(source_text)
    if not source.is_file():
        return None
    destination = target_dir / target_name
    shutil.copy2(source, destination)
    return destination.name


def fetch_seed_rows() -> list[dict[str, object]]:
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        vehicles = conn.execute(
            """
            SELECT
                vehicle_id,
                plate_number,
                owner_name,
                user_category,
                owner_affiliation,
                owner_reference,
                vehicle_type,
                vehicle_brand,
                vehicle_model,
                vehicle_color,
                registration_status,
                approval_date,
                expiry_date,
                status_notes,
                record_source
            FROM registered_vehicles
            WHERE record_source = 'dummy_seed'
            ORDER BY vehicle_id
            """
        ).fetchall()

        export_rows: list[dict[str, object]] = []
        for vehicle in vehicles:
            vehicle_id = int(vehicle["vehicle_id"])
            documents = conn.execute(
                """
                SELECT
                    document_type,
                    document_reference,
                    verification_status,
                    verified_at,
                    expires_at,
                    notes
                FROM vehicle_documents
                WHERE vehicle_id = ?
                ORDER BY document_id
                """,
                (vehicle_id,),
            ).fetchall()
            latest_event = conn.execute(
                """
                SELECT
                    id,
                    timestamp,
                    crop_path,
                    annotated_frame_path,
                    camera_role,
                    source_name,
                    detector_confidence,
                    ocr_confidence
                FROM recognition_events
                WHERE plate_number = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (vehicle["plate_number"],),
            ).fetchone()
            event_count_row = conn.execute(
                "SELECT COUNT(*) AS total FROM recognition_events WHERE plate_number = ?",
                (vehicle["plate_number"],),
            ).fetchone()

            export_rows.append(
                {
                    "vehicle": dict(vehicle),
                    "documents": [dict(row) for row in documents],
                    "latest_event": dict(latest_event) if latest_event else None,
                    "event_count": int(event_count_row["total"] if event_count_row else 0),
                }
            )
        return export_rows
    finally:
        conn.close()


def export_review_bundle() -> Path:
    dirs = ensure_export_dirs()
    rows = fetch_seed_rows()
    manifest: list[dict[str, object]] = []

    for row in rows:
        vehicle = row["vehicle"]
        latest_event = row["latest_event"] or {}
        plate_number = str(vehicle["plate_number"])
        slug = f"{int(vehicle['vehicle_id']):02d}_{plate_number}"

        profile_photo_name = f"{slug}_profile.svg"
        write_profile_svg(
            dirs["profile"] / profile_photo_name,
            owner_name=str(vehicle["owner_name"]),
            category=str(vehicle["user_category"]),
            plate_number=plate_number,
        )

        crop_name = safe_copy(latest_event.get("crop_path"), dirs["crop"], f"{slug}_plate.jpg")
        frame_name = safe_copy(latest_event.get("annotated_frame_path"), dirs["frame"], f"{slug}_frame.jpg")

        manifest.append(
            {
                "vehicle_id": vehicle["vehicle_id"],
                "plate_number": plate_number,
                "owner_name": vehicle["owner_name"],
                "user_category": vehicle["user_category"],
                "registration_status": vehicle["registration_status"],
                "event_count": row["event_count"],
                "latest_event": latest_event,
                "documents": row["documents"],
                "profile_photo": f"profile_photos/{profile_photo_name}",
                "plate_crop": f"plate_crops/{crop_name}" if crop_name else None,
                "annotated_frame": f"annotated_frames/{frame_name}" if frame_name else None,
            }
        )

    (dirs["root"] / "seed_profiles.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    (dirs["root"] / "README.txt").write_text(
        "\n".join(
            [
                "Seed Profile Review Export",
                "",
                f"Database: {DB_PATH}",
                "Files:",
                "- index.html: browsable review gallery",
                "- seed_profiles.json: exported manifest",
                "- profile_photos/: sample profile portrait placeholders",
                "- plate_crops/: latest saved plate crop per seeded profile",
                "- annotated_frames/: latest annotated frame per seeded profile",
            ]
        ),
        encoding="utf-8",
    )
    (dirs["root"] / "index.html").write_text(build_gallery_html(manifest), encoding="utf-8")
    return dirs["root"]


def document_html(documents: list[dict[str, object]]) -> str:
    if not documents:
        return "<li>No document metadata</li>"
    parts = []
    for doc in documents:
        summary = " - ".join(
            value
            for value in [
                str(doc.get("document_type", "")).upper(),
                str(doc.get("document_reference", "") or "").strip(),
                str(doc.get("verification_status", "") or "").strip(),
            ]
            if value
        )
        parts.append(f"<li>{escape(summary)}</li>")
    return "".join(parts)


def image_block(title: str, relative_path: str | None) -> str:
    if not relative_path:
        return f'<div class="image-block"><h4>{escape(title)}</h4><div class="image-missing">No file exported</div></div>'
    return (
        f'<div class="image-block"><h4>{escape(title)}</h4>'
        f'<img src="{escape(relative_path)}" alt="{escape(title)}"></div>'
    )


def build_gallery_html(manifest: list[dict[str, object]]) -> str:
    cards = []
    for row in manifest:
        latest_event = row.get("latest_event") or {}
        cards.append(
            f"""
            <article class="profile-card">
                <header class="profile-head">
                    <div>
                        <p class="eyebrow">{escape(str(row.get("user_category", "")).title())} • Plate {escape(str(row.get("plate_number", "")))}</p>
                        <h2>{escape(str(row.get("owner_name", "")))}</h2>
                        <p class="meta">Status: {escape(str(row.get("registration_status", "")).title())} • Events: {escape(str(row.get("event_count", 0)))}</p>
                    </div>
                </header>
                <div class="profile-grid">
                    {image_block("Sample Profile Photo", str(row.get("profile_photo") or ""))}
                    {image_block("Latest Plate Crop", str(row.get("plate_crop") or ""))}
                    {image_block("Latest Annotated Frame", str(row.get("annotated_frame") or ""))}
                </div>
                <section class="details">
                    <div><strong>Vehicle ID:</strong> {escape(str(row.get("vehicle_id", "")))}</div>
                    <div><strong>Latest Event:</strong> {escape(str(latest_event.get("timestamp", "—")))}</div>
                    <div><strong>Camera Role:</strong> {escape(str(latest_event.get("camera_role", "—")))}</div>
                    <div><strong>Source Name:</strong> {escape(str(latest_event.get("source_name", "—")))}</div>
                </section>
                <section class="documents">
                    <h3>Documents</h3>
                    <ul>{document_html(row.get("documents") or [])}</ul>
                </section>
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Seed Profile Review</title>
  <style>
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: #f4f7fb;
      color: #17304d;
    }}
    main {{
      width: min(1360px, calc(100% - 40px));
      margin: 24px auto 40px;
    }}
    .hero {{
      padding: 20px 24px;
      border-radius: 18px;
      background: linear-gradient(135deg, #0b2f5a 0%, #16406f 100%);
      color: white;
      box-shadow: 0 16px 40px rgba(11, 47, 90, 0.18);
    }}
    .hero h1 {{
      margin: 0 0 8px;
    }}
    .hero p {{
      margin: 0;
      color: #d7e3f2;
    }}
    .cards {{
      display: grid;
      gap: 18px;
      margin-top: 22px;
    }}
    .profile-card {{
      padding: 20px;
      border: 1px solid #d6e1ef;
      border-radius: 18px;
      background: white;
      box-shadow: 0 8px 24px rgba(12, 29, 52, 0.06);
    }}
    .eyebrow {{
      margin: 0 0 6px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #5d7390;
    }}
    .profile-head h2 {{
      margin: 0;
      font-size: 28px;
    }}
    .meta {{
      margin: 8px 0 0;
      color: #526a86;
    }}
    .profile-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}
    .image-block {{
      border: 1px solid #d6e1ef;
      border-radius: 14px;
      padding: 12px;
      background: #fbfdff;
    }}
    .image-block h4 {{
      margin: 0 0 10px;
      font-size: 15px;
    }}
    .image-block img {{
      display: block;
      width: 100%;
      max-height: 260px;
      object-fit: contain;
      border-radius: 10px;
      background: #edf3fa;
    }}
    .image-missing {{
      display: grid;
      place-items: center;
      min-height: 220px;
      border-radius: 10px;
      background: #edf3fa;
      color: #6b8098;
    }}
    .details {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px 18px;
      margin-top: 18px;
      color: #324a66;
    }}
    .documents {{
      margin-top: 18px;
    }}
    .documents h3 {{
      margin: 0 0 10px;
      font-size: 16px;
    }}
    .documents ul {{
      margin: 0;
      padding-left: 18px;
      color: #445d79;
    }}
    @media (max-width: 980px) {{
      .profile-grid,
      .details {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Seed Profile Review</h1>
      <p>Exported demo bundle for the 5 dummy seeded vehicle profiles, including sample profile portraits and the latest linked plate images.</p>
    </section>
    <section class="cards">
      {''.join(cards)}
    </section>
  </main>
</body>
</html>
"""


if __name__ == "__main__":
    output = export_review_bundle()
    print(output)
