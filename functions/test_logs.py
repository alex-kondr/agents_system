from pathlib import Path
import json
import logging
import sys
import re
from multiprocessing import Pool, cpu_count
from typing import Literal
from tqdm import tqdm

from functions.functions import load_file


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
        message = super().format(record)
        return f"{log_color}{message}{self.RESET}"


logger = logging.getLogger("LogTest")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredFormatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)


def process_log_chunk(chunk: list[str]) -> list[list[str]]:
    """
    Processes a chunk of log lines to find errors and their preceding request URL.
    """
    errors_in_chunk = []
    error_pattern = re.compile(r"^error ")
    request_pattern = re.compile(r"Request [A-Z]+ u?'([^']*)'")

    for i, line in enumerate(chunk):
        found_url = None
        error_type = None

        # Перевіряємо тип помилки
        if error_pattern.search(line):
            error_type = "STANDARD"
        elif "ERROR MAKING REQUEST" in line:
            error_type = "MAKING"

        if error_type:
            # Шукаємо URL у попередніх 20 рядках
            for j in range(i - 1, max(i - 20, -1), -1):
                if match := request_pattern.search(chunk[j]):
                    found_url = match.group(1)
                    break

            if found_url:
                # Зберігаємо тип помилки разом із даними для подальшої фільтрації
                errors_in_chunk.append([found_url, error_type, line])
            else:
                errors_in_chunk.append(["URL not found", error_type, line])

    return errors_in_chunk


class LogProduct:

    def __init__(
        self, agent_id: int, reload: Literal[0, 1, True, False]=False, session_id=0
    ):
        self.agent_id = agent_id
        self.emits_dir = Path("product_test/logs")
        self.emits_dir.mkdir(exist_ok=True)
        self.file_path = self.emits_dir / f"agent-{self.agent_id}.json"

        if not self.file_path.exists() or reload:
            self.file = self.generate_file(session_id)
        else:
            logger.info(f"Opening existing log file: {self.file_path}")
            self.file = self.open_file()

    def generate_file(self, session_id=0) -> list:
        logger.info(f"Getting logs for agent {self.agent_id}...")
        content = load_file(agent_id=self.agent_id, type_file="log", decode=True, session_id=session_id)
        content_list = content.split("\n")
        logger.info(f"Get logs complete ({len(content_list)} lines). Saving logs...")
        self.save_file(content_list)
        logger.info("Logs saved successfully.")
        return content_list

    def open_file(self):
        with open(self.file_path, "r", encoding="utf-8") as fd:
            file = json.load(fd)
        return file

    def save_file(self, file):
        with open(self.file_path, "w", encoding="utf-8") as fd:
            json.dump(file, fd, indent=2)


class TestLogProduct:

    def __init__(self, log_product: LogProduct):
        self.log_product = log_product
        self.path = Path(f"product_test/error/log-{self.log_product.agent_id}")
        self.path.mkdir(exist_ok=True)

    def test_log(self):
        log_lines = self.log_product.file
        if not log_lines:
            logger.warning("Log file is empty, skipping test.")
            return

        num_processes = cpu_count()
        chunk_size = max(1000, len(log_lines) // (num_processes * 2))
        chunks = [log_lines[i:i + chunk_size] for i in range(0, len(log_lines), chunk_size)]

        logger.info(f"Starting log analysis with {num_processes} cores...")

        error_log = []
        with Pool(num_processes) as p:
            results_iterator = p.imap_unordered(process_log_chunk, chunks)
            for chunk_errors in tqdm(results_iterator, total=len(chunks), desc="Analyzing logs"):
                if chunk_errors:
                    error_log.extend(chunk_errors)

        # Розділяємо помилки для статистики
        standard_errors = [e for e in error_log if e[1] == "STANDARD"]
        making_errors = [e for e in error_log if e[1] == "MAKING"]

        logger.info(f"Analyzed {len(log_lines)} log lines.")

        # Вивід згідно з вашими вимогами:
        # Стандартні помилки (без "MAKING")
        logger.error(f"Find error in {self.log_product.agent_id} logs: {len(standard_errors)}")
        # Тільки "MAKING" помилки
        logger.error(f"Find error in logs MAKING: {len(making_errors)}")

        # Зберігаємо все разом або лише стандартні (за вашим бажанням)
        # Якщо потрібно зберегти все:
        self.save(error_log)

    def save(self, error_log: list):
        file_path = self.path / "log.json"
        logger.info(f"Saving error log to: {file_path}")
        with open(file_path, "w", encoding="utf-8") as fd:
            json.dump(error_log, fd, indent=2)
