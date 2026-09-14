import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://cdsco.gov.in"

CDSCO_URL = (
    "https://cdsco.gov.in/opencms/opencms/en/Latest-Alerts/"
)

OUTPUT_DIR = Path("data/cdsco/alerts")

METADATA_FILE = OUTPUT_DIR / "metadata.csv"


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36"
    )
})


# ============================================================
# CLEAN FILENAME
# ============================================================

def clean_filename(text):
    """
    Convert a title into a safe Windows filename.
    """

    text = text.strip()

    # Remove characters not allowed in Windows filenames
    text = re.sub(r'[<>:"/\\|?*]', "_", text)

    # Remove excessive spaces
    text = re.sub(r"\s+", " ", text)

    # Remove trailing spaces/dots
    text = text.rstrip(" .")

    # Keep filenames reasonably short
    if len(text) > 150:
        text = text[:150].rstrip()

    return text


# ============================================================
# GET CDSCO PAGE
# ============================================================

def get_page():

    print("Fetching CDSCO Alerts page...")
    print(CDSCO_URL)

    response = session.get(
        CDSCO_URL,
        timeout=30
    )

    response.raise_for_status()

    print(f"HTTP status: {response.status_code}")

    return response.text


# ============================================================
# EXTRACT ALERT ENTRIES
# ============================================================

def extract_entries(html):
    """
    Extract entries from the CDSCO Alerts table.

    Expected columns:

    S.No
    Title
    Release Date
    Download PDF
    PDF Size
    """

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    entries = []

    for table in soup.find_all("table"):

        rows = table.find_all("tr")

        for row in rows:

            cells = row.find_all("td")

            if len(cells) < 4:
                continue

            serial_number = cells[0].get_text(
                " ",
                strip=True
            )

            title = cells[1].get_text(
                " ",
                strip=True
            )

            release_date = cells[2].get_text(
                " ",
                strip=True
            )

            link = cells[3].find("a")

            if not link:
                continue

            href = link.get("href")

            if not href:
                continue

            # Convert relative URL to absolute URL
            pdf_page_url = urljoin(
                BASE_URL,
                href
            )

            pdf_size = ""

            if len(cells) >= 5:

                pdf_size = cells[4].get_text(
                    " ",
                    strip=True
                )

            # Ignore header/non-data rows
            if not serial_number.isdigit():
                continue

            entries.append({
                "serial_number": serial_number,
                "title": title,
                "release_date": release_date,
                "pdf_size": pdf_size,
                "pdf_page_url": pdf_page_url,
            })

    return entries


# ============================================================
# DOWNLOAD ACTUAL PDF
# ============================================================

def download_pdf(jsp_url):
    """
    CDSCO Download PDF links commonly point to a JSP page.

    The JSP page contains an iframe.
    The iframe contains the actual PDF.

    Returns:

        pdf_url
        pdf_data
    """

    try:

        response = session.get(
            jsp_url,
            timeout=30
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        # ----------------------------------------------------
        # CASE 1: URL directly returns PDF
        # ----------------------------------------------------

        if (
            "application/pdf" in content_type
            or response.content[:4] == b"%PDF"
        ):

            return (
                jsp_url,
                response.content
            )

        # ----------------------------------------------------
        # CASE 2: PDF is inside iframe
        # ----------------------------------------------------

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        iframe = soup.find("iframe")

        if iframe and iframe.get("src"):

            iframe_src = iframe["src"]

            pdf_url = urljoin(
                jsp_url,
                iframe_src
            )

            print("    Found PDF:")
            print(f"    {pdf_url}")

            pdf_response = session.get(
                pdf_url,
                timeout=60
            )

            pdf_response.raise_for_status()

            pdf_content_type = (
                pdf_response.headers
                .get("Content-Type", "")
                .lower()
            )

            if (
                "application/pdf" in pdf_content_type
                or pdf_response.content[:4] == b"%PDF"
            ):

                return (
                    pdf_url,
                    pdf_response.content
                )

        # ----------------------------------------------------
        # CASE 3: Search page source for PDF URL
        # ----------------------------------------------------

        pdf_match = re.search(
            r'https?[^"\']+\.pdf',
            response.text,
            re.IGNORECASE
        )

        if pdf_match:

            pdf_url = pdf_match.group(0)

            pdf_response = session.get(
                pdf_url,
                timeout=60
            )

            pdf_response.raise_for_status()

            if pdf_response.content[:4] == b"%PDF":

                return (
                    pdf_url,
                    pdf_response.content
                )

        print("    Could not find PDF.")

        return None, None

    except Exception as e:

        print(f"    Error: {e}")

        return None, None


# ============================================================
# SAVE METADATA
# ============================================================

def save_metadata(metadata):

    if not metadata:
        return

    fieldnames = [
        "id",
        "serial_number",
        "title",
        "release_date",
        "pdf_size",
        "source",
        "source_url",
        "pdf_url",
        "local_file"
    ]

    with open(
        METADATA_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(metadata)

    print()
    print(
        f"Metadata saved to: {METADATA_FILE}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print("CDSCO ALERTS PDF DOWNLOADER")
    print("=" * 60)
    print()

    # Create output directory
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # Fetch webpage
    html = get_page()

    # Extract entries
    entries = extract_entries(html)

    print()
    print(
        f"Alert entries found: {len(entries)}"
    )
    print()

    if not entries:

        print("No entries found.")
        return

    metadata = []

    successful = 0
    failed = 0

    # ========================================================
    # DOWNLOAD EACH ALERT
    # ========================================================

    for index, entry in enumerate(
        entries,
        start=1
    ):

        serial = entry["serial_number"]
        title = entry["title"]

        print(
            f"[{index}/{len(entries)}] "
            f"{title}"
        )

        # Create safe filename
        safe_title = clean_filename(title)

        filename = (
            f"{int(serial):03d}_{safe_title}.pdf"
        )

        output_path = OUTPUT_DIR / filename

        # ----------------------------------------------------
        # Skip existing PDF
        # ----------------------------------------------------

        if (
            output_path.exists()
            and output_path.stat().st_size > 0
        ):

            print("    Already exists. Skipping.")

            metadata.append({
                "id": serial,
                "serial_number": serial,
                "title": title,
                "release_date": entry["release_date"],
                "pdf_size": entry["pdf_size"],
                "source": "CDSCO",
                "source_url": CDSCO_URL,
                "pdf_url": "",
                "local_file": str(output_path),
            })

            successful += 1

            continue

        # ----------------------------------------------------
        # Download PDF
        # ----------------------------------------------------

        pdf_url, pdf_data = download_pdf(
            entry["pdf_page_url"]
        )

        if pdf_data:

            with open(
                output_path,
                "wb"
            ) as file:

                file.write(pdf_data)

            print(
                f"    Saved: {output_path}"
            )

            metadata.append({
                "id": serial,
                "serial_number": serial,
                "title": title,
                "release_date": entry["release_date"],
                "pdf_size": entry["pdf_size"],
                "source": "CDSCO",
                "source_url": CDSCO_URL,
                "pdf_url": pdf_url,
                "local_file": str(output_path),
            })

            successful += 1

        else:

            print("    FAILED")

            failed += 1

        # Small delay between requests
        time.sleep(1.5)

    # ========================================================
    # SAVE METADATA
    # ========================================================

    save_metadata(metadata)

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)

    print(
        f"Entries found:        {len(entries)}"
    )

    print(
        f"Successful downloads: {successful}"
    )

    print(
        f"Failed downloads:     {failed}"
    )

    print(
        f"Output directory:     {OUTPUT_DIR}"
    )

    print()


if __name__ == "__main__":
    main()
