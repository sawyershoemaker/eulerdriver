"""
eulerdriver
automates solution to Project Euler
"""
import os
import sys
import time
import logging
from typing import List, Dict, Optional

from euler_webdriver import EulerWebdriver

class EulerSolver:
    """main solving workflow"""
    
    def __init__(self, answers_file: str = "answers.txt"):
        """initialize with answers file path"""
        self.answers_file = answers_file
        self.answers: Dict[int, str] = {}
        self.solved_problems: List[int] = []
        self.failed_problems: List[int] = []
        
        # setup logging to both file and console
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('euler_solver.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_answers(self) -> bool:
        """load problem answers from file"""
        try:
            if not os.path.exists(self.answers_file):
                self.logger.error(f"Answers file '{self.answers_file}' not found")
                return False
            
            self.logger.info(f"Loading answers from '{self.answers_file}'...")
            
            with open(self.answers_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                try:
                    # parse different formats: "1. 200", "1: 200", "1 200"
                    if '.' in line:
                        parts = line.split('.', 1)
                    elif ':' in line:
                        parts = line.split(':', 1)
                    else:
                        parts = line.split(None, 1)
                    
                    if len(parts) != 2:
                        self.logger.warning(f"Invalid format on line {line_num}: {line}")
                        continue
                    
                    problem_num = int(parts[0].strip())
                    answer = parts[1].strip()
                    
                    # skip empty or placeholder answers
                    if not answer or answer.lower() in ['', 'blank', 'unknown', '?']:
                        self.logger.info(f"Skipping problem {problem_num} - blank answer")
                        continue
                    
                    self.answers[problem_num] = answer
                    
                except ValueError:
                    self.logger.warning(f"Invalid format on line {line_num}: {line}")
                    continue
            
            self.logger.info(f"Loaded {len(self.answers)} answers")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load answers: {e}")
            return False
    
    def solve_problem(self, webdriver: EulerWebdriver, problem_num: int) -> bool:
        """solve a specific problem using the webdriver"""
        try:
            self.logger.info(f"Attempting to solve problem {problem_num}")
            
            # get answer for this problem
            answer = self.answers.get(problem_num)
            if not answer:
                self.logger.error(f"No answer found for problem {problem_num}")
                return False
            
            # navigate to problem page
            if not webdriver.navigate_to_problem(problem_num):
                self.logger.error(f"Failed to navigate to problem {problem_num}")
                return False
            
            # check for rate limiting
            if webdriver.is_rate_limited():
                self.logger.warning("Rate limited before submission, waiting...")
                if not webdriver.wait_for_rate_limit():
                    self.logger.error("Rate limit wait timeout")
                    return False
            
            # submit the answer
            success, result_message = webdriver.submit_answer(answer)
            
            if not success:
                self.logger.error(f"Failed to submit answer for problem {problem_num}: {result_message}")
                return False
            
            # parse the result
            result_lower = result_message.lower()
            
            if 'correct' in result_lower and 'congratulations' in result_lower:
                self.logger.info(f"Problem {problem_num} solved successfully!")
                self.solved_problems.append(problem_num)
                return True
            elif 'incorrect' in result_lower:
                self.logger.warning(f"Problem {problem_num} - incorrect answer: {result_message}")
                self.failed_problems.append(problem_num)
                return False
            elif 'already solved' in result_lower:
                self.logger.info(f"Problem {problem_num} already solved")
                self.solved_problems.append(problem_num)
                return True
            elif 'rate limit' in result_lower:
                self.logger.warning(f"Problem {problem_num} - rate limited: {result_message}")
                return False  # Don't mark as failed, retry later
            else:
                self.logger.warning(f"Problem {problem_num} - unknown result: {result_message}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error solving problem {problem_num}: {e}")
            return False
    
    def run(self, headless: bool = False, max_problems: Optional[int] = None) -> None:
        """run the main solving process"""
        try:
            # Load answers first
            if not self.load_answers():
                self.logger.error("Failed to load answers, exiting")
                return
            
            # initialize webdriver
            with EulerWebdriver(headless=headless) as webdriver:
                # login if needed
                if not webdriver.check_login_status():
                    self.logger.info("Not logged in, attempting to login...")
                    if not webdriver.login():
                        self.logger.error("Failed to login, exiting")
                        return
                else:
                    self.logger.info("Already logged in")
                
                # main solving loop
                problems_solved = 0
                consecutive_failures = 0
                max_consecutive_failures = 5
                
                while True:
                    # check limits
                    if max_problems and problems_solved >= max_problems:
                        self.logger.info(f"Reached maximum problems limit ({max_problems})")
                        break
                    
                    # get next unsolved problem
                    problem_num = webdriver.get_next_unsolved_problem()
                    if not problem_num:
                        self.logger.info("No more unsolved problems found")
                        break
                    
                    # check if we have an answer
                    if problem_num not in self.answers:
                        self.logger.info(f"No answer available for problem {problem_num}, skipping...")
                        continue
                    
                    self.logger.info(f"Found unsolved problem {problem_num} with available answer")
                    
                    # solve the problem
                    success = self.solve_problem(webdriver, problem_num)
                    
                    if success:
                        problems_solved += 1
                        consecutive_failures = 0
                        self.logger.info(f"Progress: {problems_solved} problems solved")
                    else:
                        consecutive_failures += 1
                        self.logger.warning(f"Consecutive failures: {consecutive_failures}")
                        
                        # take a break if too many failures
                        if consecutive_failures >= max_consecutive_failures:
                            self.logger.warning("Too many consecutive failures, taking a longer break...")
                            time.sleep(60)
                            consecutive_failures = 0
                    
                    # small delay between problems
                    time.sleep(2)
                
                # show final summary
                self.print_summary()
                
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
            self.print_summary()
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.print_summary()
    
    def print_summary(self) -> None:
        """print session summary"""
        self.logger.info("=" * 50)
        self.logger.info("SOLVING SESSION SUMMARY")
        self.logger.info("=" * 50)
        self.logger.info(f"Problems solved: {len(self.solved_problems)}")
        self.logger.info(f"Problems failed: {len(self.failed_problems)}")
        self.logger.info(f"Total answers loaded: {len(self.answers)}")
        
        if self.solved_problems:
            self.logger.info(f"Solved problems: {sorted(self.solved_problems)}")
        
        if self.failed_problems:
            self.logger.info(f"Failed problems: {sorted(self.failed_problems)}")
        
        self.logger.info("=" * 50)

def main():
    """main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Project Euler Problem Solver")
    parser.add_argument("--answers", "-a", default="answers.txt", 
                       help="Path to answers file (default: answers.txt)")
    parser.add_argument("--headless", action="store_true", 
                       help="Run in headless mode")
    parser.add_argument("--max-problems", "-m", type=int, 
                       help="Maximum number of problems to solve")
    
    args = parser.parse_args()
    
    # check for environment file
    if not os.path.exists('.env'):
        print("Error: .env file not found!")
        print("Please copy env_example.txt to .env and fill in your credentials.")
        sys.exit(1)
    
    # create and run solver
    solver = EulerSolver(args.answers)
    solver.run(headless=args.headless, max_problems=args.max_problems)

if __name__ == "__main__":
    main()
