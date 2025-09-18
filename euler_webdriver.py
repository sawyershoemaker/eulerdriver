"""
eulerdriver
automates solution to Project Euler
"""
import os
import time
import logging
import random
import base64
import threading
from typing import Optional, Dict, List, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException,
    ElementClickInterceptedException
)
from dotenv import load_dotenv
import openai

# load environment variables
load_dotenv()

class EulerWebdriver:
    """webdriver for automation"""
    
    def __init__(self, headless: bool = False, action_delay: float = 1.0, max_retries: int = 3):
        """Initialize webdriver with settings"""
        self.headless = headless
        self.action_delay = action_delay
        self.max_retries = max_retries
        self.driver = None
        self.wait = None
        self.is_logged_in = False
        
        # captcha settings
        self.captcha_dir = os.path.join(os.getcwd(), "captcha")
        os.makedirs(self.captcha_dir, exist_ok=True)
        self.captcha_cleanup_timer = None
        
        # logging setup
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('euler_webdriver.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # urls
        self.base_url = "https://projecteuler.net"
        self.login_url = f"{self.base_url}/sign_in"
        self.problems_url = f"{self.base_url}/archives"
        self.progress_url = f"{self.base_url}/progress"
        
    def _find_brave_executable(self) -> str:
        """Find Brave browser executable"""
        possible_paths = [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Users\{}\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe".format(os.getenv('USERNAME')),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.logger.info(f"Found Brave at: {path}")
                return path
        
        raise FileNotFoundError("Brave browser not found. Please install Brave or check the path.")
    
    def _download_chromedriver(self) -> str:
        """Download ChromeDriver if needed"""
        import requests
        import zipfile
        import shutil
        
        # latest ver
        try:
            response = requests.get("https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE")
            version = response.text.strip()
            download_url = f"https://storage.googleapis.com/chrome-for-testing-public/{version}/win32/chromedriver-win32.zip"
        except:
            # old api fallback
            try:
                response = requests.get("https://chromedriver.storage.googleapis.com/LATEST_RELEASE")
                version = response.text.strip()
                download_url = f"https://chromedriver.storage.googleapis.com/{version}/chromedriver_win32.zip"
            except:
                # final fallback
                version = "114.0.5735.90"
                download_url = f"https://chromedriver.storage.googleapis.com/{version}/chromedriver_win32.zip"
                self.logger.warning(f"Using fallback version: {version}")
        
        # create temp directory
        temp_dir = os.path.join(os.getcwd(), "chromedriver_temp")
        os.makedirs(temp_dir, exist_ok=True)
        chromedriver_path = os.path.join(temp_dir, "chromedriver.exe")
        
        if not os.path.exists(chromedriver_path):
            self.logger.info("Downloading ChromeDriver...")
            try:
                response = requests.get(download_url)
                response.raise_for_status()
                
                # save and extract
                zip_path = os.path.join(temp_dir, "chromedriver.zip")
                with open(zip_path, 'wb') as f:
                    f.write(response.content)
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # new api structure
                if "chrome-for-testing" in download_url:
                    extracted_dir = os.path.join(temp_dir, "chromedriver-win32")
                    if os.path.exists(extracted_dir):
                        chromedriver_src = os.path.join(extracted_dir, "chromedriver.exe")
                        if os.path.exists(chromedriver_src):
                            shutil.move(chromedriver_src, chromedriver_path)
                        shutil.rmtree(extracted_dir)
                
                os.remove(zip_path)
                self.logger.info("ChromeDriver downloaded successfully")
                
            except Exception as e:
                self.logger.error(f"Failed to download ChromeDriver: {e}")
                raise
        
        return chromedriver_path
    
    def _setup_driver(self) -> None:
        """Setup the Brave driver"""
        try:
            # find brave executable
            brave_path = self._find_brave_executable()
            
            # chrome options for brave
            options = Options()
            options.binary_location = brave_path
            
            if self.headless:
                options.add_argument('--headless')
            
            # basic options
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            # custom user agent if provided
            user_agent = os.getenv('USER_AGENT')
            if user_agent:
                options.add_argument(f'--user-agent={user_agent}')
            
            # download chromedriver if needed
            chromedriver_path = self._download_chromedriver()
            
            # create service and driver
            from selenium.webdriver.chrome.service import Service
            service = Service(chromedriver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # remove webdriver property for stealth
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # setup wait
            self.wait = WebDriverWait(self.driver, 10)
            
            self.logger.info("Brave webdriver setup completed")
            
        except Exception as e:
            self.logger.error(f"Failed to setup webdriver: {e}")
            raise
    
    def _human_delay(self, min_delay: float = None, max_delay: float = None) -> None:
        """Add human-like delay between actions"""
        if min_delay is None:
            min_delay = self.action_delay * 0.5
        if max_delay is None:
            max_delay = self.action_delay * 1.5
            
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def _safe_click(self, element, retries: int = None) -> bool:
        """Safely click an element with retries"""
        if retries is None:
            retries = self.max_retries
            
        for attempt in range(retries):
            try:
                # scroll element into view
                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                self._human_delay(0.1, 0.3)
                
                # try regular click first
                element.click()
                self._human_delay()
                return True
                
            except ElementClickInterceptedException:
                try:
                    # try javascript click if regular click fails
                    self.driver.execute_script("arguments[0].click();", element)
                    self._human_delay()
                    return True
                except Exception as e:
                    self.logger.warning(f"Click attempt {attempt + 1} failed: {e}")
                    if attempt < retries - 1:
                        self._human_delay(1, 2)
                        
            except Exception as e:
                self.logger.warning(f"Click attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    self._human_delay(1, 2)
        
        return False
    
    def _safe_send_keys(self, element, text: str) -> bool:
        """Safely send keys to an element"""
        try:
            element.clear()
            self._human_delay(0.1, 0.2)
            
            # type with human-like delays
            for char in text:
                element.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            self._human_delay()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send keys: {e}")
            return False
    
    def _screenshot_captcha_element(self, captcha_element) -> Optional[str]:
        """
        Take a screenshot of the captcha element to capture the EXACT currently displayed captcha
        
        args:
            captcha_element: The captcha image element
            
        returns:
            Optional[str]: Path to screenshot image or None if failed
        """
        try:
            # verify element is still valid and visible
            if not captcha_element.is_displayed():
                self.logger.error("Captcha element is not displayed")
                return None
            
            # ensure the element is visible and in view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", captcha_element)
            self._human_delay(0.2, 0.3)  # slightly longer delay to ensure rendering
            
            # get element dimensions before screenshot
            try:
                size = captcha_element.size
                location = captcha_element.location
                self.logger.info(f"Captcha element dimensions: {size}, location: {location}")
                
                # check if element has reasonable size
                if size['width'] < 50 or size['height'] < 20:
                    self.logger.warning(f"Captcha element seems too small: {size}")
                    return None
                    
            except Exception as e:
                self.logger.warning(f"Could not get element dimensions: {e}")
            
            # take screenshot of the specific element
            screenshot = captcha_element.screenshot_as_png
            
            # verify we got a valid screenshot
            if len(screenshot) < 1000:  # increased threshold for valid captcha
                self.logger.warning(f"Screenshot too small ({len(screenshot)} bytes), might be invalid")
                return None
            
            # save the screenshot
            timestamp = int(time.time())
            filename = f"captcha_screenshot_{timestamp}.png"
            filepath = os.path.join(self.captcha_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(screenshot)
            
            self.logger.info(f"Captured captcha screenshot: {filepath} (size: {len(screenshot)} bytes)")
            
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"Failed to screenshot captcha element: {e}")
            return None
    
    def _delete_captcha_image(self, filepath: str) -> None:
        """
        Delete captcha image immediately
        
        args:
            filepath: Path to the captcha image file
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                self.logger.info(f"Deleted captcha image: {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to delete captcha image {filepath}: {e}")
    
    def _solve_captcha_with_openai(self, image_path: str) -> Optional[str]:
        """
        Solve captcha using OpenAI API
        
        args:
            image_path: Path to the captcha image
            
        returns:
            Optional[str]: Captcha solution or None if failed
        """
        try:
            # check if OpenAI API key is available
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                self.logger.warning("OpenAI API key not found in environment variables")
                return None
            
            # initialize OpenAI client
            client = openai.OpenAI(api_key=api_key)
            
            # encode image to base64
            with open(image_path, 'rb') as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # call OpenAI API
            response = client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "I am having trouble reading this image. Return just the text displayed in this image with no spaces or trailing text. Expect 5-6 numbers."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
            )
            
            # extract solution
            solution = response.choices[0].message.content.strip()
            self.logger.info(f"OpenAI captcha solution: {solution}")
            return solution
            
        except Exception as e:
            self.logger.error(f"Failed to solve captcha with OpenAI: {e}")
            return None
    
    def start(self) -> None:
        """Start the webdriver"""
        self._setup_driver()
        self.logger.info("Euler Webdriver started")
    
    
    def stop(self) -> None:
        """Stop the webdriver"""
        if self.driver:
            self.driver.quit()
            self.logger.info("Euler Webdriver stopped")
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
    
    def login(self) -> bool:
        """
        try login to project euler with persistent browser session
        
        returns:
            bool: True if login successful, False otherwise
        """
        try:
            # check if already logged in (persistent session)
            if self.check_login_status():
                self.logger.info("Already logged in (persistent session)")
                return True
            
            username = os.getenv('EULER_USERNAME')
            password = os.getenv('EULER_PASSWORD')
            
            if not username or not password:
                self.logger.error("Username or password not found in environment variables")
                return False
            
            self.logger.info("Attempting to login to Project Euler...")
            
            # navigate to login page
            self.driver.get(self.login_url)
            self._human_delay(1, 2)
            
            # find and fill username field
            username_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            if not self._safe_send_keys(username_field, username):
                self.logger.error("Failed to enter username")
                return False
            
            # find and fill password field
            password_field = self.driver.find_element(By.NAME, "password")
            if not self._safe_send_keys(password_field, password):
                self.logger.error("Failed to enter password")
                return False
            
            # check "remember me" checkbox if present
            try:
                remember_me_selectors = [
                    "//input[@type='checkbox' and contains(@name, 'remember')]",
                    "//input[@type='checkbox' and contains(@id, 'remember')]",
                    "//input[@type='checkbox' and contains(@class, 'remember')]"
                ]
                
                for selector in remember_me_selectors:
                    try:
                        remember_checkbox = self.driver.find_element(By.XPATH, selector)
                        if not remember_checkbox.is_selected():
                            self._safe_click(remember_checkbox)
                            self.logger.info("Checked 'Remember Me' checkbox")
                        break
                    except NoSuchElementException:
                        continue
            except Exception as e:
                self.logger.debug(f"Could not find or check 'Remember Me' checkbox: {e}")
            
            # handle captcha if present (but don't check for failure yet)
            captcha_handled = self._handle_captcha_if_present(max_retries=3)
            if not captcha_handled:
                self.logger.error("Failed to handle captcha after retries")
                return False
            
            # find and click login button with multiple selectors
            login_button = None
            login_selectors = [
                "//input[@name='sign_in']",
                "//input[@type='submit' and @value='Sign In']",
                "//input[@type='submit']",
                "//input[@value='Sign In']",
                "//input[@value='Login']",
                "//button[@type='submit']",
                "//button[contains(text(), 'Sign In')]",
                "//button[contains(text(), 'Login')]"
            ]
            
            for selector in login_selectors:
                try:
                    login_button = self.driver.find_element(By.XPATH, selector)
                    self.logger.info(f"Found login button with selector: {selector}")
                    break
                except NoSuchElementException:
                    continue
            
            if not login_button:
                self.logger.error("Could not find login button")
                return False
            
            if not self._safe_click(login_button):
                self.logger.error("Failed to click login button")
                return False
            
            # wait for form submission and redirect
            self._human_delay(1.5, 2.5)
            
            # check if we're redirected away from login page
            current_url = self.driver.current_url
            if "sign_in" not in current_url:
                self.is_logged_in = True
                self.logger.info("Login successful!")
                return True
            else:
                # still on login page - check for specific error messages
                error_found = False
                
                # check for captcha failure messages
                captcha_error_messages = [
                    "The confirmation code you entered was not valid",
                    "You did not enter the confirmation code",
                    "Invalid confirmation code",
                    "Captcha verification failed"
                ]
                
                page_text = self.driver.page_source.lower()
                for error_msg in captcha_error_messages:
                    if error_msg.lower() in page_text:
                        self.logger.error(f"Captcha failed: {error_msg}")
                        error_found = True
                        break
                
                # check for general error messages
                if not error_found:
                    try:
                        error_elements = self.driver.find_elements(By.CLASS_NAME, "error")
                        for error_element in error_elements:
                            error_text = error_element.text.strip()
                            if error_text:
                                self.logger.error(f"Login failed: {error_text}")
                                error_found = True
                                break
                    except NoSuchElementException:
                        pass
                
                if not error_found:
                    self.logger.error("Login failed: Still on login page but no specific error found")
                
                return False
                
        except TimeoutException:
            self.logger.error("Login timeout - page elements not found")
            return False
        except Exception as e:
            self.logger.error(f"Login failed with exception: {e}")
            return False
    
    def check_login_status(self) -> bool:
        """
        Check if currently logged in to Project Euler
        
        Returns:
            bool: True if logged in, False otherwise
        """
        try:
            # navigate to main page
            self.driver.get(self.base_url)
            self._human_delay(1, 2)
            
            # look for logout link
            try:
                # check for logout link (indicates logged in)
                logout_element = self.driver.find_element(By.XPATH, "//a[contains(@href, 'sign_out')]")
                self.is_logged_in = True
                self.logger.info("Already logged in")
                return True
            except NoSuchElementException:
                # check for sign in link (indicates not logged in)
                try:
                    signin_element = self.driver.find_element(By.XPATH, "//a[contains(@href, 'sign_in')]")
                    self.is_logged_in = False
                    self.logger.info("Not logged in")
                    return False
                except NoSuchElementException:
                    # if neither found, assume logged in
                    self.is_logged_in = True
                    return True
                    
        except Exception as e:
            self.logger.error(f"Error checking login status: {e}")
            return False
    
    def navigate_to_problem(self, problem_number: int) -> bool:
        """
        go directly to a specific problem page
        
        args:
            problem_number: The problem number to navigate to
            
        returns:
            bool: True if navigation successful, False otherwise
        """
        try:
            self.logger.info(f"Navigating to problem {problem_number}...")
            
            # navigate directly to the problem URL
            problem_url = f"{self.base_url}/problem={problem_number}"
            self.driver.get(problem_url)
            self._human_delay(0.5, 1.0)
            
            # verify we're on the correct problem page
            current_url = self.driver.current_url
            if str(problem_number) in current_url or f"problem={problem_number}" in current_url:
                self.logger.info(f"Successfully navigated to problem {problem_number}")
                return True
            else:
                self.logger.error(f"Navigation verification failed for problem {problem_number}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to navigate to problem {problem_number}: {e}")
            return False
    
    def get_next_unsolved_problem(self) -> Optional[int]:
        """
        get the next unsolved problem from the progress page
        
        returns:
            Optional[int]: Next unsolved problem number, or None if none found
        """
        try:
            self.logger.info("Finding next unsolved problem from progress page...")
            
            # navigate to progress page
            self.driver.get(self.progress_url)
            self._human_delay(1, 1.5)
            
            try:
                # use the most efficient selector - direct td elements with problem links
                problem_elements = self.driver.find_elements(By.XPATH, "//td[@class='tooltip problem_unsolved']//a[contains(@href, 'problem=')]")
                
                if not problem_elements:
                    # fallback: look for any unsolved problem links
                    problem_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'problem=')]")
                
                self.logger.info(f"Found {len(problem_elements)} problem elements, checking for first unsolved...")
                
                for element in problem_elements:
                    try:
                        # extract problem number
                        href = element.get_attribute('href')
                        if href and 'problem=' in href:
                            problem_num = int(href.split('problem=')[1].split('&')[0])
                            
                            # check if this problem is unsolved (fast check)
                            parent_td = element.find_element(By.XPATH, "./..")
                            td_class = parent_td.get_attribute('class') or ''
                            
                            # if it has 'problem_unsolved' class, it's unsolved
                            if 'problem_unsolved' in td_class:
                                self.logger.info(f"Found next unsolved problem: {problem_num}")
                                return problem_num
                            # if it has 'problem_solved' class, skip it
                            elif 'problem_solved' in td_class:
                                continue
                            # if no class info, check style for orange background
                            else:
                                td_style = parent_td.get_attribute('style') or ''
                                if 'rgb(255, 186, 0)' not in td_style and 'orange' not in td_style.lower():
                                    self.logger.info(f"Found next unsolved problem: {problem_num} (no solved styling)")
                                    return problem_num
                                    
                    except Exception as e:
                        self.logger.debug(f"Error processing problem element: {e}")
                        continue
                
                self.logger.info("No unsolved problems found")
                return None
                
            except Exception as e:
                self.logger.error(f"Error parsing progress page: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting next unsolved problem: {e}")
            return None
    
    def submit_answer(self, answer: str) -> Tuple[bool, str]:
        """
        submit an answer for the current problem
        
        args:
            answer: The answer to submit
            
        returns:
            Tuple[bool, str]: (success, message) - success indicates if submission worked, message contains result
        """
        try:
            self.logger.info(f"Submitting answer: {answer}")
            
            # check for captcha before submitting
            captcha_handled = self._handle_captcha_if_present(max_retries=3)
            if not captcha_handled:
                self.logger.error("Failed to handle captcha before submission")
                return False, "Captcha handling failed"
            
            # look for answer input field  
            answer_selectors = [
                "//input[@name='answer']",
                "//input[@id='answer']",
                "//input[@type='text']",
                "//textarea[@name='answer']"
            ]
            
            answer_field = None
            for selector in answer_selectors:
                try:
                    # use a shorter timeout for answer field lookup to reduce delay
                    quick_wait = WebDriverWait(self.driver, 2)
                    answer_field = quick_wait.until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if not answer_field:
                self.logger.error("Could not find answer input field")
                return False, "Answer field not found"
            
            # enter the answer
            if not self._safe_send_keys(answer_field, answer):
                self.logger.error("Failed to enter answer")
                return False, "Failed to enter answer"
            
            # look for submit button
            submit_selectors = [
                "//input[@type='submit']",
                "//button[@type='submit']",
                "//input[@value='Submit']",
                "//button[contains(text(), 'Submit')]"
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = self.driver.find_element(By.XPATH, selector)
                    break
                except NoSuchElementException:
                    continue
            
            if not submit_button:
                self.logger.error("Could not find submit button")
                return False, "Submit button not found"
            
            # click submit button
            if not self._safe_click(submit_button):
                self.logger.error("Failed to click submit button")
                return False, "Failed to submit answer"
            
            # wait for response
            self._human_delay(0.5, 1.0)
            
            # check for result message
            result_message = self._check_submission_result()
            return True, result_message
            
        except Exception as e:
            self.logger.error(f"Failed to submit answer: {e}")
            return False, f"Submission error: {e}"
    
    def _check_submission_result(self) -> str:
        """
        check the result of answer submission
        
        returns:
            str: Result message
        """
        try:
            # check for rate limiting first
            is_limited, wait_time = self.is_rate_limited()
            if is_limited:
                if wait_time:
                    self.logger.warning(f"Rate limited after submission, need to wait {wait_time} seconds...")
                else:
                    self.logger.warning("Rate limited after submission, refreshing page...")
                if self.wait_for_rate_limit():
                    return "Rate limit cleared, ready for next submission"
                else:
                    return "Rate limited and unable to clear"
            
            # quick check for obvious success/failure indicators
            page_text = self.driver.page_source.lower()
            
            if 'correct' in page_text and 'congratulations' in page_text:
                return "Correct! Congratulations!"
            elif 'incorrect' in page_text:
                return "Incorrect answer"
            elif 'already solved' in page_text:
                return "Problem already solved"
            else:
                return "Submission completed"
                
        except Exception as e:
            self.logger.error(f"Error checking submission result: {e}")
            return f"Error checking result: {e}"
    
    def _parse_wait_time_from_message(self, message: str) -> Optional[int]:
        """
        Parse wait time in seconds from rate limit error message
        
        args:
            message: The error message containing wait time information
            
        returns:
            Optional[int]: Wait time in seconds, or None if not found
        """
        import re
        
        try:
            # convert to lowercase for case-insensitive matching
            message_lower = message.lower()
            
            # pattern to match "X minute(s), Y second(s)" format
            minute_second_pattern = r'(\d+)\s+minute(?:s)?,?\s+(\d+)\s+second(?:s)?'
            match = re.search(minute_second_pattern, message_lower)
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                total_seconds = minutes * 60 + seconds
                self.logger.info(f"Parsed wait time: {minutes} minutes, {seconds} seconds = {total_seconds} total seconds")
                return total_seconds
            
            # pattern to match just seconds "X second(s)"
            second_only_pattern = r'(\d+)\s+second(?:s)?'
            match = re.search(second_only_pattern, message_lower)
            if match:
                seconds = int(match.group(1))
                self.logger.info(f"Parsed wait time: {seconds} seconds")
                return seconds
            
            # pattern to match just minutes "X minute(s)" (convert to seconds)
            minute_only_pattern = r'(\d+)\s+minute(?:s)?'
            match = re.search(minute_only_pattern, message_lower)
            if match:
                minutes = int(match.group(1))
                total_seconds = minutes * 60
                self.logger.info(f"Parsed wait time: {minutes} minutes = {total_seconds} seconds")
                return total_seconds
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error parsing wait time from message: {e}")
            return None

    def is_rate_limited(self) -> Tuple[bool, Optional[int]]:
        """
        check if currently rate limited and extract wait time if available
        
        returns:
            Tuple[bool, Optional[int]]: (is_rate_limited, wait_time_seconds)
        """
        try:
            page_text = self.driver.page_source.lower()
            rate_limit_indicators = [
                'rate limit',
                'too many',
                'please wait',
                'try again later',
                'slow down',
                'you must wait',
                'before submitting any more answers'
            ]
            
            for indicator in rate_limit_indicators:
                if indicator in page_text:
                    self.logger.warning("Rate limit detected")
                    
                    # try to extract wait time from the page content
                    wait_time = self._parse_wait_time_from_message(page_text)
                    if wait_time:
                        self.logger.info(f"Extracted wait time: {wait_time} seconds")
                        return True, wait_time
                    else:
                        self.logger.warning("Rate limit detected but could not parse wait time")
                        return True, None
            
            return False, None
            
        except Exception as e:
            self.logger.error(f"Error checking rate limit: {e}")
            return False, None
    
    def wait_for_rate_limit(self, max_wait_time: int = 300) -> bool:
        """
        wait for rate limit to clear using precise timing based on extracted wait time
        
        args:
            max_wait_time: Maximum time to wait in seconds (fallback if no specific time found)
            
        returns:
            bool: True if rate limit cleared, False if timeout
        """
        try:
            # check current rate limit status and extract wait time
            is_limited, wait_time = self.is_rate_limited()
            
            if not is_limited:
                self.logger.info("No rate limit detected")
                return True
            
            # determine how long to wait
            if wait_time is not None:
                # use the specific wait time from the error message
                actual_wait_time = min(wait_time, max_wait_time)  # don't exceed max_wait_time
                self.logger.info(f"Rate limit detected with specific wait time: {wait_time} seconds")
                self.logger.info(f"Will wait for {actual_wait_time} seconds before refreshing...")
            else:
                # fallback to a reasonable default wait time
                actual_wait_time = min(60, max_wait_time)  # Default to 1 minute or max_wait_time
                self.logger.warning(f"Rate limit detected but no specific wait time found")
                self.logger.info(f"Will wait for {actual_wait_time} seconds before refreshing...")
            
            # wait for the specified time with progress updates
            self._wait_with_progress(actual_wait_time)
            
            # refresh the page after waiting
            self.logger.info("Wait time completed, refreshing page...")
            self.driver.refresh()
            self._human_delay(2, 3)
            
            # check if rate limit is cleared
            is_limited_after, _ = self.is_rate_limited()
            if not is_limited_after:
                self.logger.info("Rate limit cleared after timed wait and refresh!")
                return True
            else:
                self.logger.warning("Still rate limited after timed wait, trying one more refresh...")
                # one more refresh attempt
                time.sleep(5)
                self.driver.refresh()
                self._human_delay(2, 3)
                
                is_limited_final, _ = self.is_rate_limited()
                if not is_limited_final:
                    self.logger.info("Rate limit cleared after second refresh!")
                    return True
                else:
                    self.logger.error("Still rate limited after multiple refreshes and timed wait")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error handling rate limit: {e}")
            return False

    def _wait_with_progress(self, wait_seconds: int) -> None:
        """
        Wait for specified seconds with progress updates
        
        args:
            wait_seconds: Number of seconds to wait
        """
        try:
            # show progress updates every 10 seconds for waits longer than 30 seconds
            if wait_seconds > 30:
                update_interval = 10
                remaining = wait_seconds
                
                while remaining > 0:
                    if remaining <= update_interval:
                        # final wait
                        self.logger.info(f"Final wait: {remaining} seconds remaining...")
                        time.sleep(remaining)
                        break
                    else:
                        # wait for update interval
                        self.logger.info(f"Rate limit wait: {remaining} seconds remaining...")
                        time.sleep(update_interval)
                        remaining -= update_interval
            else:
                # for shorter waits, just wait without progress updates
                self.logger.info(f"Waiting {wait_seconds} seconds for rate limit to clear...")
                time.sleep(wait_seconds)
                
        except Exception as e:
            self.logger.error(f"Error during wait: {e}")
            # fallback to simple sleep
            time.sleep(wait_seconds)
    
    def _solve_captcha(self) -> Optional[str]:
        """
        solve captcha using automated OpenAI API with fallback to manual input
        
        returns:
            Optional[str]: Captcha solution or None if failed
        """
        try:
            captcha_img = None
            try:
                captcha_img = self.driver.find_element(By.ID, "captcha_image")
                self.logger.info("Found captcha image using id='captcha_image'")
            except NoSuchElementException:
                self.logger.info("No captcha image found with id='captcha_image', trying fallback selectors...")
                # fallback to other selectors
                captcha_selectors = [
                    "//img[contains(@id, 'captcha')]",
                    "//img[contains(@src, 'captcha')]",
                    "//img[contains(@alt, 'captcha')]",
                    "//img[contains(@class, 'captcha')]"
                ]
                
                for selector in captcha_selectors:
                    try:
                        captcha_img = self.driver.find_element(By.XPATH, selector)
                        self.logger.info(f"Found captcha image using selector: {selector}")
                        break
                    except NoSuchElementException:
                        continue
                if not captcha_img:
                    self.logger.info("No captcha image found with any selector, debugging page images...")
                    try:
                        all_images = self.driver.find_elements(By.TAG_NAME, "img")
                        self.logger.info(f"Found {len(all_images)} total images on page:")
                        for i, img in enumerate(all_images[:10]):  # show first 10
                            try:
                                src = img.get_attribute('src') or 'no src'
                                img_id = img.get_attribute('id') or 'no id'
                                img_class = img.get_attribute('class') or 'no class'
                                img_alt = img.get_attribute('alt') or 'no alt'
                                self.logger.info(f"  Image {i+1}: id='{img_id}', class='{img_class}', alt='{img_alt}', src='{src[:100]}...'")
                            except Exception as e:
                                self.logger.info(f"  Image {i+1}: Error getting attributes: {e}")
                    except Exception as e:
                        self.logger.error(f"Error debugging page images: {e}")
            
            # verify we found the right element
            if captcha_img:
                try:
                    # get element details for verification
                    element_id = captcha_img.get_attribute('id') or 'no id'
                    element_class = captcha_img.get_attribute('class') or 'no class'
                    element_src = captcha_img.get_attribute('src') or 'no src'
                    element_size = captcha_img.size
                    element_location = captcha_img.location
                    
                    self.logger.info(f"Captcha element details:")
                    self.logger.info(f"  ID: {element_id}")
                    self.logger.info(f"  Class: {element_class}")
                    self.logger.info(f"  Src: {element_src[:100]}...")
                    self.logger.info(f"  Size: {element_size}")
                    self.logger.info(f"  Location: {element_location}")
                    
                    # check if element is visible
                    is_displayed = captcha_img.is_displayed()
                    self.logger.info(f"  Is displayed: {is_displayed}")
                    
                except Exception as e:
                    self.logger.warning(f"Could not get captcha element details: {e}")
            
            if not captcha_img:
                self.logger.warning("No captcha image found")
                return None
            
            self.logger.info("Captcha detected, attempting to solve...")
            self.logger.info("Capturing currently displayed captcha using screenshot method...")
            image_path = self._screenshot_captcha_element(captcha_img)
            if not image_path:
                self.logger.error("Failed to capture captcha image using screenshot method")
                return None
            
            # try to solve with OpenAI API
            solution = self._solve_captcha_with_openai(image_path)
            if solution:
                self.logger.info(f"Successfully solved captcha with OpenAI: {solution}")
                # delete the captcha image immediately after solving
                self._delete_captcha_image(image_path)
                return solution
            
            # fallback to manual input
            self.logger.warning("OpenAI captcha solving failed, falling back to manual input")
            self.logger.info(f"Captured captcha image saved at: {image_path}")
            captcha_text = input("Enter captcha: ").strip()
            
            # delete the captcha image after manual input (regardless of success)
            self._delete_captcha_image(image_path)
            
            return captcha_text if captcha_text else None
                
        except Exception as e:
            self.logger.error(f"Error solving captcha: {e}")
            return None
    
    def _handle_captcha_if_present(self, max_retries: int = 3) -> bool:
        """
        check for and handle captcha if present with retry logic
        
        args:
            max_retries: Maximum number of captcha retry attempts
            
        returns:
            bool: True if captcha handled successfully, False otherwise
        """
        try:
            for attempt in range(max_retries):
                
                # look for captcha input field
                captcha_input_selectors = [
                    "//input[contains(@name, 'captcha')]",
                    "//input[contains(@id, 'captcha')]",
                    "//input[contains(@class, 'captcha')]",
                    "//input[@type='text'][following-sibling::img or preceding-sibling::img]"
                ]
                
                captcha_input = None
                for selector in captcha_input_selectors:
                    try:
                        captcha_input = self.driver.find_element(By.XPATH, selector)
                        break
                    except NoSuchElementException:
                        continue
                
                if not captcha_input:
                    # no captcha present
                    self.logger.info("No captcha detected")
                    return True
                
                # solve the captcha
                captcha_solution = self._solve_captcha()
                if not captcha_solution:
                    if attempt < max_retries - 1:
                        continue
                    return False
                
                # clear and enter the captcha solution
                captcha_input.clear()
                self._human_delay(0.1, 0.2)
                
                if not self._safe_send_keys(captcha_input, captcha_solution):
                    if attempt < max_retries - 1:
                        continue
                    return False
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error handling captcha: {e}")
            return False