from pathlib import Path
import logging
import sys
import re
from multiprocessing import Pool, cpu_count
from typing import Literal
from zoneinfo import ZoneInfo
from datetime import datetime

from tqdm import tqdm

from .functions import load_file


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
        self, agent_id: str, reload: Literal[0, 1, True, False]=True, session_id=0
    ):
        self.agent_id = agent_id
        self.emits_dir = Path("product_test/logs")
        # self.emits_dir.mkdir(exist_ok=True, parents=True)
        self.file_path = self.emits_dir / f"agent-{self.agent_id}.json"
        self.file = self.generate_file(session_id)

    def generate_file(self, session_id=0) -> list:
        logger.info(f"Getting logs for agent {self.agent_id}...")
        content = load_file(agent_id=self.agent_id, type_file="log", decode=True, session_id=session_id)
        content_list = content.split("\n")
        logger.info(f"Get logs complete ({len(content_list)} lines).")
        return content_list


class TestLogProduct:

    def __init__(self, log_product: LogProduct):
        self.log_product = log_product
        self.path = Path(f"product_test/error/log-{self.log_product.agent_id}")
        # self.path.mkdir(exist_ok=True)

    def test_log(self):
        log_lines = self.log_product.file
        if not log_lines:
            logger.warning("Log file is empty, skipping test.")
            return "⚠️ Лог-файл порожній, аналіз пропущено."

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

        report_lines = [
            f"📝 Проаналізовано {len(log_lines)} рядків логу",
            f"❌ Помилки в логах: {len(standard_errors)}",
            f"❌ Помилки MAKING: {len(making_errors)}",
        ]
        return "\n".join(report_lines)
