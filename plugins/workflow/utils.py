import os
import re

def validate_file_or_folder_name(filename: str) -> str:
    """
    Validate filename: letters, digits, hyphen, underscore, dot.
    Returns "valid" or "invalid".
    """
    if not filename:
        return "invalid"
    if not re.match(r'^[a-zA-Z0-9_.-]+$', filename):
        return "invalid"
    if filename.startswith('.') or '..' in filename:
        return "invalid"
    return "valid"


def safe_path(base_dir: str, folder: str, filename: str) -> str:
    """
    Safely build a file path inside base_dir.
    Returns the resolved path or empty string if unsafe.
    """
    if validate_file_or_folder_name(folder) != "valid":
        return ""
    if validate_file_or_folder_name(filename) != "valid":
        return ""

    base = os.path.realpath(base_dir)
    target = os.path.realpath(os.path.join(base, folder, filename))

    # Ensure target is inside base directory (prevents path traversal via symlinks)
    if not (target == base or target.startswith(base + os.sep)):
        return ""

    return target
