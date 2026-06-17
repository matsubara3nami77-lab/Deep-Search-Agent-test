import asyncio
from datetime import datetime
from pathlib import Path


async def save_report(content: str) -> str:
    """Save a markdown report to the local filesystem and return the file path."""

    def _save() -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        reports_dir = Path("data/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        filepath = reports_dir / f"report_{timestamp}.md"
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    return await asyncio.to_thread(_save)
