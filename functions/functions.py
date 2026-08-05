import os
from typing import List, Optional, Dict, Any
import sys
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import aiohttp
from bs4 import BeautifulSoup
from lxml import etree  # Для підтримки точних XPath виразів

from models import AgentModel

load_dotenv()


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


def get_auth() -> aiohttp.BasicAuth:
    """Хелпер для створення об'єкта авторизації aiohttp."""
    return aiohttp.BasicAuth(
        login=os.getenv("USER_NAME", ""),
        password=os.getenv("PASS", "")
    )


async def load_file(
    session: aiohttp.ClientSession,
    agent_id: int,
    type_file: str = "yaml",
    size: int | str = "",
    decode: bool = False,
    session_id: int = 0
) -> str | bytes:
    """
    type_file: "yaml", "log"
    Завантажує файл потоком (streaming), не завантажуючи весь масив даних у пам'ять одночасно.
    """
    action = {
        "log": "looksession",
        "yaml": "yaml"
    }
    url = f"https://prunesearch.com/manage?action={action[type_file]}&agent_id={agent_id}&lastbytes={size}"
    if session_id:
        url += f"&session_id={session_id}"

    # ssl=False відповідає verify=False у requests
    async with session.get(url, auth=get_auth(), ssl=False) as response:
        content = bytearray()
        # Зчитуємо почастинно (по 1MB), щоб зекономити RAM
        async for chunk in response.content.iter_chunked(1024 * 1024):
            content.extend(chunk)

    return content.decode("utf-8") if decode else bytes(content)


def is_include(xnames: list = [], text: str = "", lower: bool = False) -> Optional[str]:
    for xname in xnames:
        if lower:
            if xname.lower() in text.lower():
                return xname
        else:
            if xname in text:
                return xname
    return None


async def get_old_agent_html(session: aiohttp.ClientSession, agent_id: str) -> str:
    url = f"https://prunesearch.com/manage?action=agent&agent_id={agent_id}"
    async with session.get(url, auth=get_auth(), ssl=False) as response:
        return await response.text()


def get_agent_name(html_content: str) -> str:
    """Використовуємо lxml.html для точного збереження логики XPath."""
    tree = etree.HTML(html_content)
    result = tree.xpath("//body/b/text()")
    return result[0] if result else ""


def get_agent_code(html_content: str) -> List[str]:
    """Парсинг тегу textarea через BeautifulSoup."""
    soup = BeautifulSoup(html_content, "html.parser")
    textarea = soup.find("textarea")
    if not textarea:
        return []

    full_text = textarea.get_text()
    cleaned_code = full_text.replace(
        "(data, context, session)",
        "(data: Response, context: dict[str, str], session: Session)"
    ).replace(
        "(context, session)",
        "(context: dict[str, str], session: Session)"
    )
    return cleaned_code.split('\n')


async def get_source_name(session: aiohttp.ClientSession, agent_id: str) -> str:
    url = f"https://prunesearch.com/manage?action=editagent&agent_id={agent_id}"
    async with session.get(url, auth=get_auth(), ssl=False) as response:
        html_content = await response.text()

    tree = etree.HTML(html_content)
    values = tree.xpath('//input[@name="source_name"]/@value')
    return values[0] if values else ""


async def upload_code(session: aiohttp.ClientSession, agent_id: str, code: str, run: bool = True):
    url = f"https://prunesearch.com/manage?action=agent&agent_id={agent_id}"

    payload = {
        'agent_id': agent_id,
        'action': 'editagentcode',
        'code': code,
        'subaction': 'Save and run' if run else 'Save and continue editing'
    }

    async with session.post(url, data=payload, auth=get_auth(), ssl=False) as response:
        if response.status == 200:
            logger.info(f"Code '{payload['subaction']}' successfully")
        else:
            logger.error(f"Some error uploaded: code: {response.status}")


async def get_end_date_agent(session: aiohttp.ClientSession, agent_id: str) -> Optional[str]:
    url = f"https://prunesearch.com/manage?action=sessions&agent_id={agent_id}"

    async with session.get(url, auth=get_auth(), ssl=False) as response:
        html_content = await response.text()

    tree = etree.HTML(html_content)
    date_list = tree.xpath('(//td)[1]/parent::*/td[4]/text()')
    date = date_list[0].strip() if date_list else 'None'

    if date == 'None':
        error_list = tree.xpath('(//td)[1]/parent::*/td[16]/text()')
        emit_list = tree.xpath('(//td)[1]/parent::*/td[8]/text()')

        error = error_list[0].strip() if error_list else ""
        emit_count = emit_list[0].strip() if emit_list else ""
        raise ValueError(f"error = {error}\nemit_count = {emit_count}\nNot end")

    return datetime.fromisoformat(date).replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Kyiv")).strftime("%d.%m.%Y %H:%M")


async def get_status_agent(session: aiohttp.ClientSession, agent_id: str) -> Dict[str, Any]:
    url = f"https://prunesearch.com/manage?action=sessions&agent_id={agent_id}"

    async with session.get(url, auth=get_auth(), ssl=False) as response:
        html_content = await response.text()
        status_code = response.status

    tree = etree.HTML(html_content)

    def get_xpath_val(index: int) -> str:
        res = tree.xpath(f'(//td)[1]/parent::*/td[{index}]/text()')
        return res[0].strip() if res else ''

    emit_count = get_xpath_val(8)
    errors_count = get_xpath_val(9)
    jobs_in_queue = get_xpath_val(12)
    requests_count = get_xpath_val(13)
    error = get_xpath_val(16)
    date = get_xpath_val(4)

    if date and date != 'None':
        date = datetime.fromisoformat(date).replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Kyiv")).strftime("%d.%m.%Y %H:%M")

    logger.info(f"Зроблено запит до ресурсу: статус {status_code}")
    del html_content
    del tree
    return {
        "end_date": date,
        "emit_count": emit_count,
        "errors_count": errors_count,
        "jobs_in_queue": jobs_in_queue,
        "requests_count": requests_count,
        "error": error,
    }


async def post_edit_page_agent(session: aiohttp.ClientSession, agent: AgentModel):
    if not agent.bb:
        logger.info(f"Агент <b>{agent.source_name}</b> вже був переміщений в Git/BB")
        return

    url = f"https://prunesearch.com/manage?action=editagent&agent_id={agent.agent_id}"
    data = {
        "action": "editagent",
        "agent_id": str(agent.agent_id),
        "name": agent.name,
        "source_name": agent.source_name,
        "description": agent.description + "\n<br><b>Moved to Git/BB</b>",
        "state_id": "10",
        "priority": str(agent.priority),
        "group": str(agent.group)
    }

    async with session.post(url, data=data, auth=get_auth(), ssl=False) as response:
        logger.info(f"Агент <b>{agent.source_name}</b> переміщений в Git/BB. Статус: {response.status}")