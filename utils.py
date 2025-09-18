"""
utility functions for eulerdriver
"""

import os
import logging
from typing import List, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def setup_logging(log_file: str = "euler_webdriver.log", level: int = logging.INFO) -> logging.Logger:
    """Setup logging configuration"""
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    
    # remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

def validate_environment() -> bool:
    """validate that required environment variables are set"""
    required_vars = ['EULER_USERNAME', 'EULER_PASSWORD']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file")
        return False
    
    return True

def safe_find_element(driver, by: By, value: str, timeout: int = 10) -> Optional[object]:
    """safely find an element with timeout"""
    try:
        wait = WebDriverWait(driver, timeout)
        return wait.until(EC.presence_of_element_located((by, value)))
    except TimeoutException:
        return None

def safe_find_elements(driver, by: By, value: str, timeout: int = 10) -> List[object]:
    """safely find multiple elements with timeout"""
    try:
        wait = WebDriverWait(driver, timeout)
        wait.until(EC.presence_of_element_located((by, value)))
        return driver.find_elements(by, value)
    except TimeoutException:
        return []

def extract_problem_number_from_url(url: str) -> Optional[int]:
    """extract problem number from Project Euler URL"""
    import re
    
    patterns = [
        r'problem=(\d+)',
        r'/problem/(\d+)',
        r'problem(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return int(match.group(1))
    
    return None

def is_valid_answer(answer: str) -> bool:
    """check if an answer is valid (not blank or unknown)"""
    if not answer:
        return False
    
    answer_lower = answer.lower().strip()
    invalid_answers = ['', 'blank', 'unknown', '?', 'none', 'n/a']
    
    return answer_lower not in invalid_answers

def format_progress(current: int, total: int) -> str:
    """format progress as a percentage string"""
    if total == 0:
        return "0%"
    
    percentage = (current / total) * 100
    return f"{percentage:.1f}%"

def create_backup_file(file_path: str) -> str:
    """create a backup of a file"""
    import shutil
    from datetime import datetime
    
    if not os.path.exists(file_path):
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{file_path}.backup_{timestamp}"
    
    try:
        shutil.copy2(file_path, backup_path)
        return backup_path
    except Exception as e:
        logging.error(f"Failed to create backup: {e}")
        return None

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """decorator to retry function on failure"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    
                    logging.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
            
            return None
        return wrapper
    return decorator
