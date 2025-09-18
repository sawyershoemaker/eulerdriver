"""
eulerdriver
automates solution to Project Euler
"""
import os
import time
import logging
import random
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
    
    def get_unsolved_problems(self) -> List[int]:
        """
        get list of unsolved problems from the progress page
        
        returns:
            List[int]: List of unsolved problem numbers
        """
        try:
            self.logger.info("Getting list of unsolved problems from progress page...")
            
            # navigate to progress page
            self.driver.get(self.progress_url)
            self._human_delay(1, 1.5)
            
            unsolved_problems = []
            solved_problems = []
            
            try:
                # look for problem elements on the progress page
                # solved problems are orange/highlighted
                # unsolved problems are typically in normal text color
                
                # try different selectors for problem links/numbers
                problem_selectors = [
                    "//a[contains(@href, 'problem=')]",
                    "//td[contains(@class, 'id_column')]//a",
                    "//tr[contains(@class, 'problem_row')]//a",
                    "//div[contains(@class, 'problem')]//a"
                ]
                
                problem_elements = []
                for selector in problem_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        if elements:
                            problem_elements = elements
                            self.logger.info(f"Found {len(elements)} problem elements using selector: {selector}")
                            problem_elements = elements
                            break
                    except:
                        continue
                
                if not problem_elements:
                    # fallback: look for any links that might be problems
                    problem_elements = self.driver.find_elements(By.XPATH, "//a[contains(text(), 'Problem') or contains(@href, 'problem')]")
                
                for element in problem_elements:
                    try:
                        # extract problem number
                        href = element.get_attribute('href')
                        text = element.text
                        
                        problem_num = None
                        
                        # try to extract from href first
                        if href and 'problem=' in href:
                            problem_num = int(href.split('problem=')[1].split('&')[0])
                        elif text:
                            # extract from text
                            import re
                            match = re.search(r'(\d+)', text)
                            if match:
                                problem_num = int(match.group(1))
                        
                        if not problem_num:
                            continue
                        
                        # check if this problem is solved by looking at CSS classes
                        is_solved = False
                        
                        # get the parent td element (the actual problem cell)
                        try:
                            parent_td = element.find_element(By.XPATH, "./..")
                            td_class = parent_td.get_attribute('class') or ''
                            td_style = parent_td.get_attribute('style') or ''
                            
                            # debug: log first few elements to see the structure
                            if problem_num <= 5:
                                self.logger.info(f"Problem {problem_num} - TD class: '{td_class}', style: '{td_style}'")
                            
                            # check for solved indicators
                            if 'problem_solved' in td_class:
                                is_solved = True
                                self.logger.info(f"Problem {problem_num} is SOLVED (has 'problem_solved' class)")
                            elif 'rgb(255, 186, 0)' in td_style or 'orange' in td_style.lower():
                                is_solved = True
                                self.logger.info(f"Problem {problem_num} is SOLVED (has orange background)")
                            else:
                                self.logger.debug(f"Problem {problem_num} is unsolved (no solved indicators)")
                                
                        except Exception as e:
                            self.logger.debug(f"Problem {problem_num} - could not check parent TD: {e}")
                            # fallback: check the element itself
                            element_class = element.get_attribute('class') or ''
                            if 'problem_solved' in element_class:
                                is_solved = True
                        
                        # categorize the problem
                        if is_solved:
                            solved_problems.append(problem_num)
                        else:
                            unsolved_problems.append(problem_num)
                            
                    except (ValueError, NoSuchElementException) as e:
                        self.logger.debug(f"Error processing problem element: {e}")
                        continue
                
                # sort the problems
                unsolved_problems.sort()
                solved_problems.sort()
                
                self.logger.info(f"Found {len(solved_problems)} solved problems and {len(unsolved_problems)} unsolved problems")
                self.logger.info(f"Solved problems: {solved_problems[:10]}{'...' if len(solved_problems) > 10 else ''}")
                self.logger.info(f"Unsolved problems: {unsolved_problems[:10]}{'...' if len(unsolved_problems) > 10 else ''}")
                
                return unsolved_problems
                
            except Exception as e:
                self.logger.error(f"Error parsing progress page: {e}")
                return []
                
        except Exception as e:
            self.logger.error(f"Failed to get unsolved problems from progress page: {e}")
            return []
    
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
    
    def get_solved_problems(self) -> List[int]:
        """
        get list of solved problems from the progress page
        
        returns:
            List[int]: List of solved problem numbers
        """
        try:
            self.logger.info("Getting list of solved problems from progress page...")
            
            # navigate to progress page
            self.driver.get(self.progress_url)
            self._human_delay(1, 1.5)
            
            solved_problems = []
            
            try:
                # look for problem elements on the progress page
                # solved problems are orange/highlighted
                
                # try different selectors for problem links/numbers
                problem_selectors = [
                    "//a[contains(@href, 'problem=')]",
                    "//td[contains(@class, 'id_column')]//a",
                    "//tr[contains(@class, 'problem_row')]//a",
                    "//div[contains(@class, 'problem')]//a"
                ]
                
                problem_elements = []
                for selector in problem_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        if elements:
                            problem_elements = elements
                            break
                    except:
                        continue
                
                if not problem_elements:
                    # fallback: look for any links that might be problems
                    problem_elements = self.driver.find_elements(By.XPATH, "//a[contains(text(), 'Problem') or contains(@href, 'problem')]")
                
                for element in problem_elements:
                    try:
                        # extract problem number
                        href = element.get_attribute('href')
                        text = element.text
                        
                        problem_num = None
                        
                        # try to extract from href first
                        if href and 'problem=' in href:
                            problem_num = int(href.split('problem=')[1].split('&')[0])
                        elif text:
                            # extract from text
                            import re
                            match = re.search(r'(\d+)', text)
                            if match:
                                problem_num = int(match.group(1))
                        
                        if not problem_num:
                            continue
                        
                        # check if this problem is solved (orange/highlighted)
                        is_solved = False
                        
                        # check parent row/element for solved indicators
                        try:
                            parent = element.find_element(By.XPATH, "./ancestor::tr | ./ancestor::div | ./..")
                            parent_class = parent.get_attribute('class') or ''
                            parent_style = parent.get_attribute('style') or ''
                            
                            # look for solved indicators
                            if 'solved' in parent_class.lower() or 'completed' in parent_class.lower():
                                is_solved = True
                            elif 'background-color' in parent_style and 'orange' in parent_style.lower():
                                is_solved = True
                                
                        except:
                            pass
                        
                        # check element itself for solved indicators
                        element_class = element.get_attribute('class') or ''
                        element_style = element.get_attribute('style') or ''
                        
                        if 'solved' in element_class.lower() or 'completed' in element_class.lower():
                            is_solved = True
                        elif 'color' in element_style and 'orange' in element_style.lower():
                            is_solved = True
                        
                        # add to solved list if it's solved
                        if is_solved:
                            solved_problems.append(problem_num)
                            
                    except (ValueError, NoSuchElementException):
                        continue
                
                # sort the problems
                solved_problems.sort()
                
                self.logger.info(f"Found {len(solved_problems)} solved problems")
                return solved_problems
                
            except Exception as e:
                self.logger.error(f"Error parsing progress page: {e}")
                return []
                
        except Exception as e:
            self.logger.error(f"Failed to get solved problems from progress page: {e}")
            return []
    
    def find_next_unsolved_problem(self, current_problem: int, unsolved_list: List[int]) -> Optional[int]:
        """
        find the next unsolved problem after the current one
        
        args:
            current_problem: Current problem number
            unsolved_list: List of unsolved problem numbers
            
        returns:
            Optional[int]: Next unsolved problem number, or None if none found
        """
        for problem_num in unsolved_list:
            if problem_num > current_problem:
                return problem_num
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
            if self.is_rate_limited():
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
    
    def is_rate_limited(self) -> bool:
        """
        check if currently rate limited
        
        returns:
            bool: True if rate limited, False otherwise
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
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking rate limit: {e}")
            return False
    
    def wait_for_rate_limit(self, max_wait_time: int = 300) -> bool:
        """
        wait for rate limit to clear by refreshing the page
        
        args:
            max_wait_time: Maximum time to wait in seconds
            
        returns:
            bool: True if rate limit cleared, False if timeout
        """
        self.logger.info("Rate limit detected, refreshing page to continue...")
        
        try:
            # refresh the current page
            self.driver.refresh()
            self._human_delay(2, 3)
            
            # check if rate limit is cleared
            if not self.is_rate_limited():
                self.logger.info("Rate limit cleared after refresh!")
                return True
            else:
                self.logger.warning("Still rate limited after refresh, waiting...")
                # wait a bit more and try again
                time.sleep(5)
                self.driver.refresh()
                self._human_delay(2, 3)
                
                if not self.is_rate_limited():
                    self.logger.info("Rate limit cleared after second refresh!")
                    return True
                else:
                    self.logger.error("Still rate limited after multiple refreshes")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error handling rate limit: {e}")
            return False
    
    def _solve_captcha(self) -> Optional[str]: ## this function is so dirty from ocr and openai api attempts
        """
        solve captcha using manual input
        
        returns:
            Optional[str]: Captcha solution or None if failed
        """
        try:
            # look for captcha image with more specific selectors
            captcha_selectors = [
                "//img[@id='captcha_image']",
                "//img[contains(@id, 'captcha')]",
                "//img[contains(@src, 'captcha')]",
                "//img[contains(@alt, 'captcha')]",
                "//img[contains(@class, 'captcha')]",
                "//img[contains(@src, 'image')]",
                "//img[contains(@src, 'data:image')]",
                "//img[contains(@src, '.png')]",
                "//img[contains(@src, '.jpg')]",
                "//img[contains(@src, '.gif')]"
            ]
            
            captcha_img = None
            for selector in captcha_selectors:
                try:
                    captcha_img = self.driver.find_element(By.XPATH, selector)
                    self.logger.info(f"Found captcha image using selector: {selector}")
                    break
                except NoSuchElementException:
                    continue
            
            if not captcha_img:
                self.logger.warning("No captcha image found with any selector")
                # debug: list all images on the page
                try:
                    all_images = self.driver.find_elements(By.TAG_NAME, "img")
                    self.logger.info(f"Found {len(all_images)} images on page:")
                    for i, img in enumerate(all_images[:5]):  # show first 5
                        try:
                            src = img.get_attribute('src') or 'no src'
                            img_id = img.get_attribute('id') or 'no id'
                            img_class = img.get_attribute('class') or 'no class'
                            self.logger.info(f"  Image {i+1}: id='{img_id}', class='{img_class}', src='{src[:50]}...'")
                        except:
                            pass
                except:
                    pass
                return None
            
            self.logger.info("Captcha detected, attempting to solve...")
            
            # get manual input for captcha
            captcha_text = input("Enter captcha: ").strip()
            return captcha_text if captcha_text else None
                
        except Exception as e:
            self.logger.error(f"Error solving captcha: {e}")
            return None
    
    
    def _check_captcha_failure(self) -> bool:
        """
        check if captcha validation failed
        
        returns:
            bool: True if captcha failed, False if successful or no captcha error
        """
        try:
            # wait a moment for any error messages to appear
            self._human_delay(1, 2)
            
            # check page content for captcha failure messages
            page_text = self.driver.page_source.lower()
            
            captcha_failure_indicators = [
                'confirmation code you entered was not valid',
                'you did not enter the confirmation code',
                'captcha is incorrect',
                'verification code is wrong',
                'invalid captcha',
                'wrong captcha',
                'captcha failed'
            ]
            
            for indicator in captcha_failure_indicators:
                if indicator in page_text:
                    self.logger.warning(f"Captcha failure detected: '{indicator}'")
                    return True
            
            # also check for specific error elements
            error_selectors = [
                "//div[contains(@class, 'error')]",
                "//div[contains(@class, 'message')]",
                "//span[contains(@class, 'error')]",
                "//p[contains(@class, 'error')]"
            ]
            
            for selector in error_selectors:
                try:
                    error_elements = self.driver.find_elements(By.XPATH, selector)
                    for element in error_elements:
                        error_text = element.text.lower()
                        for indicator in captcha_failure_indicators:
                            if indicator in error_text:
                                self.logger.warning(f"Captcha failure in error element: '{error_text}'")
                                return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking captcha failure: {e}")
            return False
    
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