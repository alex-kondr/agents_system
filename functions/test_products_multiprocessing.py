from typing import Literal
from zoneinfo import ZoneInfo
from datetime import datetime
import logging
import sys
from pathlib import Path
import time
import re
from multiprocessing import Pool, cpu_count
import os
from collections import defaultdict

import yaml
from tqdm import tqdm
import difflib

from .functions import load_file, get_agent_name, get_old_agent, get_end_date_agent


def is_include(xnames: list = [], text: str = "", lower: bool = False) -> str|None:
    if not text:
        return None

    emoji_pattern = re.compile("["
                               u"\U0001F600-\U0001F64F"  # emoticons
                               u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                               u"\U0001F680-\U0001F6FF"  # transport & map symbols
                               u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                               u"\U00002500-\U00002BEF"  # chinese char
                               u"\U00002702-\U000027B0"
                               u"\U00002702-\U000027B0"
                               u"\U000024C2-\U0001F251"
                               u"\U0001f926-\U0001f937"
                               u"\U00010000-\U0010ffff"
                               u"\u2640-\u2642"
                               u"\u2600-\u2B55"
                               u"\u200d"
                               u"\u23cf"
                               u"\u23e9"
                               u"\u231a"
                               u"\ufe0f"  # dingbats
                               u"\u3030"
                               "]+", flags=re.UNICODE)
    match_emoji = emoji_pattern.search(text)
    if match_emoji:
        return match_emoji.group(0)

    if not xnames:
        return None

    # Build a regex pattern: word1|word2|word3 for faster searching
    # We escape to treat special characters literally
    pattern = '|'.join(re.escape(xname) for xname in xnames)
    flags = re.IGNORECASE if lower else 0
    match = re.search(pattern, text, flags)
    return match.group(0) if match else None


class ColoredFormatter(logging.Formatter):
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    BOLD = "\033[1m"

    COLORS = {
        'DEBUG': BLUE,
        'INFO': GREEN,
        'WARNING': YELLOW,
        'ERROR': RED,
        'CRITICAL': RED + BOLD,
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        # Format the message first
        message = super().format(record)
        # Apply color to the whole line or just levelname. Here applying to the whole line for visibility.
        return f"{log_color}{message}{self.RESET}"


logger = logging.getLogger("ProductTestMulti")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = ColoredFormatter(
    "%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
# Перевизначаємо конвертер часу для цього форматера на Київський часовий пояс
formatter.converter = lambda timestamp: datetime.fromtimestamp(
    timestamp,
    tz=ZoneInfo("Europe/Kyiv")
).timetuple()
handler.setFormatter(formatter)
logger.addHandler(handler)
# -----------------------------------------


def calculate_code_change(old_file_path: Path, new_file_path: Path) -> tuple[int, int, float, float] | None:
    """
    Compares two files and calculates the percentage of change.
    Returns a tuple of (added_lines, deleted_lines, percentage_with_whitespace, percentage_without_whitespace), or None on error.
    Added/deleted lines are counted from a whitespace-sensitive comparison.
    """
    try:
        with open(old_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            old_lines = f.readlines()
        with open(new_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            new_lines = f.readlines()
    except FileNotFoundError as e:
        logger.error(f"File not found during code change calculation: {e}")
        return None

    # --- Calculation with whitespace (considers indentation and trailing spaces) ---
    differ_ws = difflib.Differ()
    diff_ws = list(differ_ws.compare(old_lines, new_lines))
    added_lines = len([line for line in diff_ws if line.startswith('+ ')])
    deleted_lines = len([line for line in diff_ws if line.startswith('- ')])

    total_lines_old = len(old_lines)
    if total_lines_old == 0:
        percentage_ws = 100.0 if added_lines > 0 else 0.0
    else:
        percentage_ws = (added_lines + deleted_lines) / total_lines_old * 100

    # --- Calculation without whitespace (ignores leading/trailing spaces) ---
    old_lines_stripped = [line.strip() for line in old_lines]
    new_lines_stripped = [line.strip() for line in new_lines]

    differ_no_ws = difflib.Differ()
    diff_no_ws = list(differ_no_ws.compare(old_lines_stripped, new_lines_stripped))
    added_lines_no_ws = len([line for line in diff_no_ws if line.startswith('+ ')])
    deleted_lines_no_ws = len([line for line in diff_no_ws if line.startswith('- ')])

    if total_lines_old == 0:
        percentage_no_ws = 100.0 if added_lines_no_ws > 0 else 0.0
    else:
        # The number of changed lines ignoring whitespace, as a percentage of original total lines.
        percentage_no_ws = (added_lines_no_ws + deleted_lines_no_ws) / total_lines_old * 100

    return added_lines, deleted_lines, percentage_ws, percentage_no_ws


def check_code_changes(root_dir: str = None):
    """
    Analyzes the specified directory for 'old_*' and 'new_*' file pairs and logs code changes.
    If root_dir is not provided, it will search from the project's root directory.
    """
    root_path = Path(root_dir).parent if root_dir else Path(__file__).parent
    logger.info("-" * 40)
    logger.info(f"Analyzing directory for code changes: {root_path.resolve()}")
    found_pairs = False
    for dirpath, _, filenames in os.walk(root_path):
        old_files = [f for f in filenames if f.startswith('old_')]
        for old_file_name in old_files:
            new_file_name = 'new_' + old_file_name[len('old_'):]
            if new_file_name in filenames:
                found_pairs = True
                result = calculate_code_change(Path(dirpath) / old_file_name, Path(dirpath) / new_file_name)
                if result:
                    added, deleted, percentage_ws, percentage_no_ws = result
                    relative_path = Path(dirpath).relative_to(root_path)
                    logger.info(f"Comparison for '{old_file_name[4:]}' in './{relative_path}':")
                    logger.info(f"  - Added: {added}, Deleted: {deleted} (literal lines)")
                    logger.info(f"  - Change (with whitespace): {percentage_ws:.2f}%")
                    logger.info(f"  - Change (ignoring whitespace): {percentage_no_ws:.2f}%")
    if not found_pairs:
        logger.warning("No 'old_*' and 'new_*' file pairs found to compare.")
    logger.info("-" * 40)


class ResultParse:
    def __init__(self, agent_id: str, session_id=0):
        self.agent_id = agent_id

        self.date = get_end_date_agent(agent_id)
        self.result(session_id)

    def __str__(self):
        return f"""
End date: {self.date}
Agent id: {self.agent_id}
Found {self.emitted} emitted objects
Completed_jobs: {self.completed_jobs}
Dupe jobs: {self.dupe_jobs}
Denied jobs: {self.denied_jobs}
Failed jobs: {self.failed_jobs}
Wasted time: {self.time}
            """

    def result(self, session_id=0):
        content = load_file(agent_id=self.agent_id, type_file="log", size=400, decode=True, session_id=session_id)

        try:
            def find_stat(pattern, text):
                match = re.search(pattern, text)
                return int(match.group(1)) if match else 0

            self.emitted = find_stat(r"Found (\d+) emitted", content)
            self.completed_jobs = find_stat(r"completed_jobs:(\d+)", content)
            self.dupe_jobs = find_stat(r"dupe_jobs:(\d+)", content)
            self.denied_jobs = find_stat(r"denied_jobs:(\d+)", content)
            self.failed_jobs = find_stat(r"failed_jobs:(\d+)", content)

            time_in_seconds = 0.0
            # Ця логіка з регулярними виразами замінює крихкий парсинг часу на основі split.
            # Спочатку вона намагається знайти число після останнього двокрапки, що йде за "browse-cache-hits:".
            time_match = re.search(r"browse-cache-hits:.*:([\d\.]+)", content)
            if not time_match:
                # Якщо це не вдається, вона шукає число безпосередньо після "browse-cache-hits:".
                time_match = re.search(r"browse-cache-hits:([\d\.]+)", content)

            if time_match:
                try:
                    time_in_seconds = float(time_match.group(1))
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse time value from log: '{time_match.group(1)}'")

            hours = int(time_in_seconds // 3600)
            minutes = int(time_in_seconds % 3600 // 60)
            seconds = int(time_in_seconds % 3600 % 60)
            self.time = f"Hours: {hours}, minutes: {minutes}, seconds: {seconds}"

        except Exception as e:
            logger.error(f"Error parsing result logs: {e}")
            self.emitted = 0
            self.completed_jobs = 0
            self.dupe_jobs = 0
            self.denied_jobs = 0
            self.failed_jobs = 0
            self.time = "Error"


class Product:
    def __init__(self, agent_id: str, reload: Literal[0, 1, True, False]=True, session_id=0):
        self.agent_id = agent_id
        self.emits_dir = Path("product_test/emits")
        # self.emits_dir.mkdir(exist_ok=True, parents=True)
        self.file_path = self.emits_dir / f"agent-{self.agent_id}.json"
        self.result = ResultParse(self.agent_id, session_id=session_id)

        # New directory for raw YAML files
        self.raw_yaml_dir = Path("product_test/raw_yamls")
        # self.raw_yaml_dir.mkdir(exist_ok=True, parents=True)
        self.raw_yaml_path = self.raw_yaml_dir / f"agent-{self.agent_id}.yaml"

        self.file = self.generate_file(session_id=session_id)

        self.agent_name = self.file["meta"]["agent_name"].strip()

    def generate_file(self, session_id=0) -> dict:
        logger.info(f"Loading YAML for agent {self.agent_id}...")
        content = load_file(agent_id=self.agent_id, type_file="yaml", session_id=session_id, decode=True)

        # Save the original YAML content
        # logger.info(f"Saving original YAML content to: {self.raw_yaml_path}")
        # with open(self.raw_yaml_path, "w", encoding="utf-8") as f:
        #     f.write(content)

        try:
            from yaml import CSafeLoader as Loader
        except ImportError:
            from yaml import SafeLoader as Loader

        file_data = {"products": []}
        meta_data = {}

        # yaml.load_all розділяє файл по символам "---"
        # Кожен doc — це дані про один товар (список об'єктів у вашому випадку)
        logger.info("Parsing and merging YAML documents...")
        for doc in yaml.load_all(content, Loader=Loader):
            if not doc:
                continue

            # Якщо документ — це список (один товар та його компоненти)
            if isinstance(doc, list):
                combined_product = {}
                for item in doc:
                    if not isinstance(item, dict): continue

                    if "meta" in item:
                        meta_data.update(item["meta"])
                        continue

                    for key, value in item.items():
                        if key in combined_product:
                            # Якщо ключ вже є (наприклад, декілька review), робимо список
                            if not isinstance(combined_product[key], list):
                                combined_product[key] = [combined_product[key]]
                            combined_product[key].append(value)
                        else:
                            combined_product[key] = value

                if combined_product:
                    file_data["products"].append(combined_product)

            # Якщо документ — це словник (наприклад, блок meta)
            elif isinstance(doc, dict):
                if "meta" in doc:
                    meta_data.update(doc["meta"])
                else:
                    file_data["products"].append(doc)

        # Перевірка наявності імені агента
        if not meta_data.get("agent_name"):
            try:
                from functions.functions import get_agent_name, get_old_agent
                logger.info(f"Agent name not found in YAML. Fetching from API for ID {self.agent_id}...")
                html = get_old_agent(self.agent_id)
                meta_data["agent_name"] = get_agent_name(html)
            except Exception:
                meta_data["agent_name"] = f"Agent-{self.agent_id}"

        file_data["meta"] = meta_data
        return file_data



class ProductValidator:
    """
    Validates a single product. Used by worker processes.
    """
    def __init__(self, product_data):
        self.original_product = product_data
        self.product_map = self._structure_product(product_data)
        self.errors = defaultdict(list)

        self.xproduct_names_category = ["review", "test", u"\uFEFF", u"\ufeff", "...", "•", "análise", "u000", u"&amp", "обзор", "тест", "recensione", "Ã", "¼", "hírek", "reseña", "inceleme", "(element)"]
        self.xproduct_names_category_start_end = []
        self.xreview_title = ["\uFEFF", "\ufeff", u"U000", u"&amp", "(element)"]
        self.xreview_excerpt = ["Conclusion", "Verdict", u"\uFEFF", u"\ufeff", "Summary", "Fazit", "href=", "U000", u"&amp", "Les plus", "Les moins", "Résumé", "►", "Выводы", "Slutsats", "CONTRO", "Závěr", "Ã", "¼", "PREGI", "DIFETTI", "(element)"]
        self.xreview_pros_cons = ["–", "-", "+", "•", "►", "none found", 'n/a', 'n\\a', u"U000", u"&amp", "etc.", "Ã", "¼", "(element)"]
        # Compile regex for pros/cons check to improve performance
        pros_cons_pattern_parts = [re.escape(x) for x in self.xreview_pros_cons]
        self.pros_cons_regex = re.compile(f"^({'|'.join(pros_cons_pattern_parts)})|({'|'.join(pros_cons_pattern_parts)})$", re.IGNORECASE)

    def _structure_product(self, product_data):
        structured = defaultdict(list)
        for section_key, section_value in product_data.items():
            items = section_value if isinstance(section_value, list) else [section_value]
            for item in items:
                if isinstance(item, dict) and 'properties' in item:
                    props_list = item.get('properties', [])
                    for prop in props_list:
                        prop_type = prop.get('type')
                        if prop_type:
                            structured_key = f"{section_key}.{prop_type}"
                            # Зберігаємо посилання на батьківський список властивостей для звіту
                            prop['_parent_props'] = props_list
                            structured[structured_key].append(prop)
        return structured

    def validate(self, config):
        self.test_product_name(
            xproduct_names=config.get('xproduct_names', []),
            not_xproduct_name=config.get('not_xproduct_name'),
            len_name=config.get('len_name', 3)
        )
        self.test_product_category(config.get('xproduct_names', []))
        self.test_review_title(config.get('xreview_title', []))
        self.test_review_date()
        self.test_review_grade()
        self.test_review_author()
        self.test_review_pros_cons()
        self.test_review_conclusion(config.get('xreview_conclusion', []))
        self.test_review_excerpt(
            xreview_excerpt=config.get('xreview_excerpt', []),
            len_chank=100,
            len_excerpt=3,
            not_xrev_excerpt=config.get('not_xproduct_name')
        )

        # Cleanup temporary references to avoid circular dependency in JSON serialization
        for section_value in self.original_product.values():
            items = section_value if isinstance(section_value, list) else [section_value]
            for item in items:
                if isinstance(item, dict) and 'properties' in item:
                    for prop in item.get('properties', []):
                        prop.pop('_parent_props', None)

        return self.errors

    def test_product_name(self, xproduct_names: list[str]=[], not_xproduct_name: str = None, len_name: int = 6) -> None:
        xproduct_names_category = self.xproduct_names_category + xproduct_names
        if not_xproduct_name and not_xproduct_name in xproduct_names_category:
            xproduct_names_category.remove(not_xproduct_name)

        name_props = self.product_map.get("product.name")
        if not name_props:
            return

        for property in name_props:
            name = property.get("value", "")
            if not name: continue

            temp_name = False
            for xname in self.xproduct_names_category_start_end:
                if name.startswith(xname) or name.endswith(xname):
                    property["error_start_end"] = f"Starts or ends '{xname}'"
                    temp_name = True
                    break

            if len(name) < len_name:
                property["error_len"] = f"Len name < {len_name}"
                temp_name = True

            xproduct_name = is_include(xproduct_names_category, name, lower=True)
            if xproduct_name:
                property["error_name"] = xproduct_name
                temp_name = True

            if temp_name:
                self.errors["prod_name"].append(property.get('_parent_props', []))

    def test_product_category(self, xproduct_names: list[str]=[]) -> None:
        xproduct_names_category = self.xproduct_names_category + xproduct_names + [')', '(']

        cat_props = self.product_map.get("product.category")
        if not cat_props:
            return

        for property in cat_props:
            category = property.get("value")
            temp_cat = False
            for xname in self.xproduct_names_category_start_end:
                if not category or category.startswith(xname) or category.endswith(xname):
                    temp_cat = True
                    break

            if category:
                xproduct_name = is_include(xproduct_names_category, category, lower=True)
                if xproduct_name:
                    temp_cat = True

            if temp_cat:
                self.errors["prod_category"].append(property.get('_parent_props', []))

    def test_review_title(self, xreview_title: list[str]=[]) -> None:
        xreview_title = self.xreview_title + xreview_title
        title_props = self.product_map.get("review.title")
        if not title_props: return

        for property in title_props:
            title = property.get("value")
            xtitle = is_include(xreview_title, title)
            if xtitle:
                property["error_name"] = xtitle
                self.errors["rev_title"].append(property.get('_parent_props', []))

    def test_review_date(self) -> None:
        # Перевіряємо кожен блок відгуку на наявність дати
        reviews = self.original_product.get("review", [])
        if not isinstance(reviews, list): reviews = [reviews]
        for review in reviews:
            props = review.get("properties", [])
            if not any(p.get("type") == "publish_date" for p in props):
                self.errors["rev_date"].append(props)

    def test_review_grade(self) -> None:
        reviews = self.original_product.get("review", [])
        if not isinstance(reviews, list): reviews = [reviews]
        for review in reviews:
            props = review.get("properties", [])
            if not any(p.get("type") == "grade" for p in props):
                self.errors["rev_grades"].append(props)

    def test_review_author(self) -> None:
        # Складна логіка, бо person може бути окремо. 
        # Якщо person.name взагалі немає в документі, вважаємо це помилкою для всіх відгуків
        if not self.product_map.get("person.name"):
            reviews = self.original_product.get("review", [])
            if not isinstance(reviews, list): reviews = [reviews]
            for review in reviews:
                props = review.get("properties", [])
                props.append({"error_no_author": "No author"})
                self.errors["rev_author"].append(props)

    def test_review_award(self) -> None:
        reviews = self.original_product.get("review", [])
        if not isinstance(reviews, list): reviews = [reviews]
        for review in reviews:
            props = review.get("properties", [])
            if not any(p.get("type") == "awards" for p in props):
                props.append({"error_no_award": "No award"})
                self.errors["rev_award"].append(props)

    def test_review_pros_cons(self) -> None:
        property_pros = self.product_map.get("review.pros", [])
        property_cons = self.product_map.get("review.cons", [])
        all_pros_vals = [p.get("value") for p in property_pros if p.get("value")]
        all_cons_vals = [p.get("value") for p in property_cons if p.get("value")]

        for property in property_pros:
            pro = property.get("value")
            if not pro: continue
            has_err = False
            if pro and len(pro) < 2:
                property["error_len"] = "< 2"
                has_err = True
            if pro in all_cons_vals:
                property["error_in_con"] = f"Pro: '{pro}' in cons"
                has_err = True
            match = self.pros_cons_regex.search(pro)
            if match:
                property["error_start_end"] = f"starts or ends with '{match.group(0)}'"
                has_err = True
            if has_err:
                self.errors["rev_pros_cons"].append(property.get('_parent_props', []))

        for property in property_cons:
            con = property.get("value")
            if not con: continue
            has_err = False
            if con and len(con) < 3:
                property["error_len"] = "< 3"
                has_err = True
            if con in all_pros_vals:
                property["error_in_pro"] = f"Con: '{con}' in pros"
                has_err = True
            match = self.pros_cons_regex.search(con)
            if match:
                property["error_start_end"] = f"starts or ends with '{match.group(0)}'"
                has_err = True
            if has_err:
                self.errors["rev_pros_cons"].append(property.get('_parent_props', []))

    def test_review_conclusion(self, xreview_conclusion: list[str] = []) -> None:
        xreview_conclusions = self.xreview_excerpt + xreview_conclusion
        conclusion_props = self.product_map.get("review.conclusion")
        if not conclusion_props: return
        for property in conclusion_props:
            conclusion = property.get("value")
            found = is_include(xreview_conclusions, conclusion)
            if found:
                property["error_name"] = found
                self.errors["rev_conclusion"].append(property.get('_parent_props', []))

    def _check_text_chunk(self, text: str, excerpt: str, len_chank: int) -> str | None:
        """Helper to check if an excerpt is found within chunks of a larger text."""
        if not text or not excerpt:
            return None

        chank_count = len(text) // len_chank
        chunk_list = [text[len_chank * i:len_chank * (i + 1)] for i in range(chank_count)]

        return is_include(chunk_list, excerpt)

    def test_review_excerpt(self, xreview_excerpt: list[str] = [], len_chank: int = 100, len_excerpt: int = 10, not_xrev_excerpt: str|None = None) -> None:
        xreview_excerpts = self.xreview_excerpt + xreview_excerpt
        if not_xrev_excerpt and not_xrev_excerpt in xreview_excerpts:
            xreview_excerpts.remove(not_xrev_excerpt)

        excerpt_props = self.product_map.get("review.excerpt")
        if not excerpt_props:
            # Якщо немає жодного excerpt у всьому документі
            reviews = self.original_product.get("review", [])
            if not isinstance(reviews, list): reviews = [reviews]
            for r in reviews:
                p = r.get("properties", [])
                p.append({"error_no": "No excerpt"})
                self.errors["rev_excerpt"].append(p)
            return

        for excerpt_property in excerpt_props:
            excerpt = excerpt_property.get("value")
            if not excerpt: continue
            parent_props = excerpt_property.get('_parent_props', [])
            has_error = False

            for prop_type in ["summary", "conclusion"]:
                text_val = next((p.get("value") for p in parent_props if p.get("type") == prop_type), "")
                element = self._check_text_chunk(text_val, excerpt, len_chank)
                if element:
                    excerpt_property[f"error_in_{prop_type[:3]}"] = f"This element in {prop_type}: '{element}'"
                    has_error = True

            if len(excerpt) < len_excerpt:
                excerpt_property["error_len"] = f"Len excerpt < {len_excerpt}"
                has_error = True

            found = is_include(xreview_excerpts, excerpt)
            if found:
                excerpt_property["error_name"] = found
                has_error = True

            if has_error:
                self.errors["rev_excerpt"].append(parent_props)


def validate_product_task(args):
    """
    Worker function to process a single product.
    Defined at module level to avoid pickling the entire TestProductMultiprocessing instance.
    """
    product_data, config = args
    validator = ProductValidator(product_data)
    return validator.validate(config)


class TestProductMultiprocessing:
    def __init__(self, product: Product):
        self.products = product.file.get("products")
        self.agent_name = product.agent_name
        self.path = Path(f"product_test/error/{self.agent_name}")
        self.config = {}

    def run(self, xproduct_names=[], not_xproduct_name=None, len_name=3, xreview_title=[], xreview_conclusion=[], xreview_excerpt=[]):
        run_start_time = time.time()

        self.config = {
            'xproduct_names': xproduct_names,
            'not_xproduct_name': not_xproduct_name,
            'len_name': len_name,
            'xreview_title': xreview_title,
            'xreview_conclusion': xreview_conclusion,
            'xreview_excerpt': xreview_excerpt
        }

        with tqdm(total=3, desc="Overall test run") as pbar:
            # Step 1: Validation
            pbar.set_description("Step 1/3: Validating products")
            num_processes = cpu_count()
            num_products = len(self.products)
            logger.info(f"Starting multiprocessing with {num_processes} cores for {num_products} products.")

            # Calculate a reasonable chunksize to improve performance by reducing IPC overhead.
            chunksize = max(1, num_products // (num_processes * 4))
            logger.info(f"Using chunksize: {chunksize} for validation.")

            # Create a generator of arguments to avoid creating a large intermediate list
            tasks = ((product, self.config) for product in self.products)

            with Pool(num_processes) as p:
                results = list(tqdm(p.imap(validate_product_task, tasks, chunksize=chunksize), total=num_products, desc=f"Validating products (chunksize={chunksize})", leave=False))

            pool_end_time = time.time()
            logger.info(f"Multiprocessing validation took: {pool_end_time - run_start_time:.2f} seconds")
            pbar.update(1)

            # Step 2: Aggregation
            pbar.set_description("Step 2/3: Aggregating results")
            agg_start_time = time.time()
            logger.info("Aggregating results...")
            aggregated_errors = defaultdict(list)
            for res in results:
                for key, val in res.items():
                    aggregated_errors[key].extend(val)
            agg_end_time = time.time()
            logger.info(f"Result aggregation took: {agg_end_time - agg_start_time:.2f} seconds")
            pbar.update(1)

            # Step 3: Collecting results
            pbar.set_description("Step 3/3: Collecting results")
            save_start_time = time.time()
            error_types = [
                ("prod_name", "product name"),
                ("prod_category", "product category"),
                ("prod_sku", "product sku"),
                ("prod_id_manufacturer", "product id.manufacturer"),
                ("prod_ean", "product ean"),
                ("rev_title", "review title"),
                ("rev_date", "review date"),
                ("rev_grades", "review grades"),
                ("rev_author", "review author"),
                ("rev_award", "review award"),
                ("rev_pros_cons", "review pros_cons"),
                ("rev_conclusion", "review conclusion"),
                ("rev_excerpt", "review excerpt"),
            ]

            report_lines = []
            for key, desc in error_types:
                errors = aggregated_errors.get(key, [])
                count = len(errors)
                logger.error(f"Count error {desc}: {count}")
                if count > 0:
                    report_lines.append(f"❌ {desc}: {count}")

            save_end_time = time.time()
            logger.info(f"Collecting results took: {save_end_time - save_start_time:.2f} seconds")
            pbar.update(1)

        total_run_time = time.time()
        logger.info(f"Total run time: {total_run_time - run_start_time:.2f} seconds")

        if report_lines:
            header = f"🔍 Перевірено {num_products} товарів за {total_run_time - run_start_time:.2f}s"
            return header + "\n" + "\n".join(report_lines)
        else:
            return f"✅ Перевірено {num_products} товарів — помилок не знайдено ({total_run_time - run_start_time:.2f}s)"
