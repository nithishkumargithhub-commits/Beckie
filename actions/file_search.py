import os
import re
import subprocess
import logging
from typing import Tuple, List

logger = logging.getLogger("VoiceAssistant.FileSearch")

SEARCH_ROOTS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Pictures"),
    os.path.expanduser("~/Music"),
    os.path.expanduser("~/Videos")
]

def search_files(query: str, max_results: int = 5) -> Tuple[bool, str]:
    """
    Searches for files matching query across standard user directories.
    Returns (success, message).
    """
    query_clean = query.lower().strip()
    if not query_clean:
        return False, "Please specify a file name or keyword to search for."

    logger.info(f"Searching user directories for files matching: '{query_clean}'")
    matches: List[str] = []

    # Clean filler words
    for prefix in ["search for file ", "search file ", "find file ", "locate file ", "find ", "search "]:
        if query_clean.startswith(prefix):
            query_clean = query_clean[len(prefix):].strip()
            break

    regex_pattern = re.escape(query_clean).replace(r'\*', '.*')

    for root_dir in SEARCH_ROOTS:
        if not os.path.exists(root_dir):
            continue
        try:
            for dirpath, _, filenames in os.walk(root_dir):
                for filename in filenames:
                    if re.search(regex_pattern, filename.lower()):
                        full_path = os.path.join(dirpath, filename)
                        matches.append(full_path)
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break
        except Exception as err:
            logger.warning(f"Error searching directory {root_dir}: {err}")

    if not matches:
        return False, f"No files found matching '{query_clean}' in your user folders."

    first_match = matches[0]
    folder = os.path.dirname(first_match)
    filename = os.path.basename(first_match)

    msg = f"Found {len(matches)} matching file{'s' if len(matches) > 1 else ''}. The top result is '{filename}' located in {os.path.basename(folder)}. Opening folder."
    logger.info(f"Opening folder for file match: {folder}")
    try:
        subprocess.run(["explorer", "/select,", first_match], timeout=5.0)
    except Exception as e:
        logger.error(f"Error opening Explorer: {e}")

    return True, msg
