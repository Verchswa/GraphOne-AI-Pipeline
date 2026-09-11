import csv
import json
import logging
import os
import sqlite3
import sys

logger = logging.getLogger("SheetsExporter")


def export_tabs(db_path: str = "pipeline_intelligence.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    os.makedirs("data_exports", exist_ok=True)

    tabs = {
        "Startups": (
            "SELECT entity_name, employee_count, source_name, source_url,"
            " collected_at FROM startups",
            [
                "Canonical Name",
                "Employee Count",
                "Source Name",
                "Source URL",
                "Collected At (ISO-8601)",
            ],
        ),
        "Products": (
            "SELECT startup_name, pricing_model, source_name, source_url,"
            " collected_at FROM products",
            [
                "Startup Name",
                "Pricing Model",
                "Source Name",
                "Source URL",
                "Collected At (ISO-8601)",
            ],
        ),
        "Research_Papers": (
            "SELECT title, authors, paper_url, github_url, github_stars,"
            " published_date FROM research_papers",
            [
                "Title",
                "Authors",
                "Paper URL",
                "GitHub URL",
                "GitHub Stars",
                "Published Date (ISO-8601)",
            ],
        ),
        "Jobs": (
            "SELECT company, date, is_remote, role_family, source_url FROM"
            " jobs",
            [
                "Canonical Company",
                "Date (ISO-8601)",
                "Is Remote",
                "Role Family",
                "Source URL",
            ],
        ),
        "News": (
            "SELECT title, source_name, source_url, published_date,"
            " collected_at FROM news",
            [
                "Title",
                "Source Name",
                "Source URL",
                "Published Date (ISO-8601)",
                "Collected At",
            ],
        ),
        "Entity_Mapping_Log": (
            "SELECT raw_name, canonical_name, method, confidence, resolved_at"
            " FROM entity_mapping_logs",
            [
                "Raw Input String",
                "Canonical Entity",
                "Resolution Method",
                "Confidence Score",
                "Timestamp",
            ],
        ),
    }

    for tab_name, (query, headers) in tabs.items():
        cursor.execute(query)
        rows = cursor.fetchall()
        csv_file = os.path.join("data_exports", f"{tab_name}.csv")
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        logger.info(f"Exported {tab_name} ({len(rows)} records) -> {csv_file}")

    conn.close()
    logger.info(
        "All 6 tabs successfully exported to data_exports/ (ready to import"
        " into Google Sheets)."
    )


if __name__ == "__main__":
    export_tabs()