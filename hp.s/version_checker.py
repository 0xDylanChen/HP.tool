import re
import sys
import shutil
import logging
from pathlib import Path
from typing import Dict, Set, Tuple, Optional

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def tokenize(text: str) -> Set[str]:
    """
    Splits text into a set of lowercase alphanumeric tokens.
    Removes 'hp' to avoid common noise.
    """
    if not text:
        return set()
    # Replace non-alphanumeric chars with space
    clean_text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    tokens = set(clean_text.split())
    tokens.discard('hp')  # Ignore common 'hp' prefix/token
    return tokens

def load_target_names(filepath: Path) -> Set[str]:
    """
    Loads target application names from a text file.
    """
    targets = set()
    try:
        if not filepath.exists():
            logger.error(f"Error: Target file {filepath} not found.")
            return targets
            
        with filepath.open('r', encoding='utf-8') as f:
            for line in f:
                name = line.strip()
                if name and not name.startswith('#'):
                    targets.add(name)
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
    return targets

def parse_html_report(filepath: Path) -> Dict[str, str]:
    """
    Parses HTML report to extract Name:Version mapping.
    Uses BeautifulSoup if available.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("BeautifulSoup (bs4) is not installed. Cannot parse HTML.")
        return {}

    data_map = {}
    try:
        with filepath.open('r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
            
            rows = soup.find_all('tr')
            name_idx = -1
            ver_idx = -1
            data_rows = []

            # 1. Scan Header to find column indices
            for row in rows:
                cells = row.find_all(['th', 'td'])
                cell_texts = [c.get_text(strip=True).lower() for c in cells]
                
                if "name" in cell_texts and ("version" in cell_texts or "deliverable version" in cell_texts):
                    for idx, text in enumerate(cell_texts):
                        if text == "name": name_idx = idx
                        if text in ["version", "deliverable version"]: ver_idx = idx
                    continue 
                
                # 2. Collect Data Rows
                if name_idx != -1 and ver_idx != -1:
                    if len(cells) > max(name_idx, ver_idx):
                        data_rows.append(cells)

            # Fallback for headerless tables or failed detection
            if name_idx == -1:
                name_idx, ver_idx = 1, 4
                data_rows = [r.find_all('td') for r in rows if len(r.find_all('td')) > 4]

            # 3. Extract Data
            for cells in data_rows:
                try:
                    name_text = cells[name_idx].get_text(strip=True)
                    ver_text = cells[ver_idx].get_text(strip=True)
                    if len(name_text) > 1:
                        data_map[name_text] = ver_text
                except IndexError:
                    continue

    except Exception as e:
        logger.error(f"HTML Parse Error in {filepath.name}: {e}")
        return {} 
        
    return data_map

def find_loose_match(target: str, data_map: Dict[str, str]) -> Tuple[Optional[str], str]:
    """
    Fuzzy matching logic to find target name in the report data.
    Returns (BestMatchName, Version).
    """
    target_tokens = tokenize(target)
    if not target_tokens:
        return None, "Ignored"

    best_match_name = None
    best_match_ver = "Not Found"
    max_score = 0

    for html_name, version in data_map.items():
        html_tokens = tokenize(html_name)
        common_words = target_tokens & html_tokens
        score = len(common_words)
        
        # Simple heuristic: prioritize more matching words
        if score > 0:
            if score > max_score:
                max_score = score
                best_match_name = html_name
                best_match_ver = version

    return best_match_name, best_match_ver

def main(project_root: Path = None, target_file: Path = None):
    # Default behavior if run directly
    if project_root is None:
        # Use CWD as project root for maximum flexibility
        project_root = Path.cwd()
    
    if target_file is None:
        # Expect version_mapping.txt in hp.s subdirectory relative to usage, OR in current dir
        # Try finding it in ./hp.s/version_mapping.txt first
        target_file = project_root / 'hp.s' / 'version_mapping.txt'
        if not target_file.exists():
             # Fallback to local script dir if running as script
             script_dir = Path(__file__).parent.absolute()
             target_file = script_dir / 'version_mapping.txt'

    # Define crucial paths
    output_dir = project_root / 'hp.v'
    archive_dir = project_root / 'bin'
    
    # Ensure directories exist
    output_dir.mkdir(exist_ok=True)
    archive_dir.mkdir(exist_ok=True)

    if not target_file.exists():
        logger.error(f"Error: {target_file} not found.")
        return

    targets = load_target_names(target_file)
    logger.info(f"Loaded {len(targets)} targets form {target_file.name}.")

    # Find HTML files in Project Root
    html_files = list(project_root.glob("*.html"))
    if not html_files:
        logger.info("No .html files found in project root.")
        return

    logger.info(f"Found {len(html_files)} HTML reports.")

    for html_path in html_files:
        # Skip output files if they accidentally ended up here (though glob *.html helps)
        if html_path.name.startswith("output_"): 
            continue

        logger.info(f"\nProcessing: {html_path.name}...")
        
        try:
            report_data = parse_html_report(html_path)
            
            if not report_data:
                logger.warning(f"   [Warning] No data extracted from {html_path.name}. Skipping.")
                continue

            # Generate Output Filename
            base_name = html_path.stem
            # Strip trailing numbering identifiers if present (e.g. _01, _02)
            if re.search(r'_\d+$', base_name):
                output_base = base_name.rsplit('_', 1)[0]
            else:
                output_base = base_name
                
            output_file = output_dir / f"{output_base}.txt"

            with output_file.open('w', encoding='utf-8') as out_f:
                header = f"Report: {html_path.name}\n"
                header += "-" * 110 + "\n"
                header += f"{'Target Name':<35} | {'Mapped HTML Name':<50} | {'Version'}\n"
                header += "-" * 110 + "\n"
                out_f.write(header)

                for target in targets:
                    found_name, version = find_loose_match(target, report_data)
                    display_found = found_name if found_name else "---"
                    # Truncate long names for display
                    if len(display_found) > 48:
                        display_found = display_found[:45] + "..."
                    
                    line = f"{target:<35} | {display_found:<50} | {version}"
                    out_f.write(line + "\n")
            
            logger.info(f"   -> Generated: {output_file.name}")
            
            # --- Archiving ---
            archive_target = archive_dir / html_path.name
            
            # Handle collision in archive
            if archive_target.exists():
                counter = 1
                while True:
                    new_name = f"{html_path.stem}_{counter:02d}{html_path.suffix}"
                    new_path = archive_dir / new_name
                    if not new_path.exists():
                        archive_target = new_path
                        break
                    counter += 1
            
            logger.info(f"   -> Archiving to: bin\\{archive_target.name}")
            shutil.move(str(html_path), str(archive_target))

        except Exception as e:
            logger.error(f"   [Error] Failed to process {html_path.name}: {e}")

    logger.info("\nBatch processing complete!")

if __name__ == "__main__":
    main()