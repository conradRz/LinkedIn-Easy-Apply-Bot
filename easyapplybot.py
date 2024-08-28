# coding=utf-8

from __future__ import annotations
import time, random, os, csv
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import winsound
from selenium.webdriver.chrome.service import Service
import re
import yaml
from datetime import date, datetime, timedelta
from selenium.webdriver.common.action_chains import ActionChains
import subprocess
from os import path
from line_profiler import LineProfiler # it's for profiling program efficiency and timing it's execution line by line. Connected to #@profile . First $ kernprof -l .\easyapplybot.py -> Then $ python -m line_profiler .\easyapplybot.py.lprof > output.txt to generate output


log = logging.getLogger(__name__)

#chrome_path = path.dirname(__file__) + r"\assets\chrome-win64\chrome-win64\chrome.exe" # Specify the path to the Chrome executable

options = Options()
#options.binary_location = chrome_path

# #the below enabled headless mode (enabled 22:13 16/7/2024 - for performance stats)
# options.add_argument("--headless")
# options.add_argument("--disable-gpu")  # May be needed for Windows
# #options.add_argument("--no-sandbox")  # Required for some environments 
# options.add_argument("--disable-extensions")  # Disable extensions
# options.add_argument("--disable-browser-side-navigation")

executable_path = path.dirname(__file__) + r"\assets\chromedriver.exe"

service = Service(executable_path = path.dirname(__file__) + r"\assets\chromedriver.exe") #https://googlechromelabs.github.io/chrome-for-testing/
driver = webdriver.Chrome(options=options, service=service) # if you do just 
# driver = webdriver.Chrome() 
# you will sometimes get the below, if you use driver = webdriver.Chrome(), this might be because they don't keep on top of things

# Exception has occurred: NoSuchDriverException
# Message: Unable to obtain chromedriver using Selenium Manager; Message: Unsuccessful command executed: C:\Users\User\AppData\Local\Programs\Python\Python39\lib\site-packages\selenium\webdriver\common\windows\selenium-manager.exe --browser chrome --output json.
# The chromedriver version cannot be discovered
# ; For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors/driver_location

num_successful_jobs_global_variable = 0

#@profile
def setupLogger() -> None:
    dt: str = datetime.strftime(datetime.now(), 
                                "%m_%d_%Y %H_%M_%S ")

    if not os.path.isdir('./logs'):
        os.mkdir('./logs')

    # TODO need to check if there is a log dir available or not
    logging.basicConfig(filename=('./logs/' + str(dt) + 'applyJobs.log'), 
                        filemode='w',
                        format='%(asctime)s::%(name)s::%(levelname)s::%(message)s', 
                        datefmt='./logs/%d-%b-%Y %H:%M:%S')
    log.setLevel(logging.DEBUG)
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.DEBUG)
    c_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S')
    c_handler.setFormatter(c_format)
    log.addHandler(c_handler)

#@profile
def get_process_id(process_name):
  """Gets the PID of a process by its name.

  Args:
    process_name: The name of the process to get the PID of.

  Returns:
    The PID of the process, or None if the process could not be found.
  """

  # Get all running processes.
  processes = subprocess.check_output(["wmic", "process", "get", "processid,commandline"]).decode("latin-1").splitlines()

  # Find the process with the given name.
  for process in processes:
    if process_name in process:
        #Use regular expression to find the number
        result = re.search(r'\b\d+\b', process)
        return int(result.group())

  # If the process could not be found, return None.
  return None

process_id = get_process_id("automated-LinkedIn-applying\\run_script.bat")

#@profile
def terminate_process(process_id):
  """Terminates a process by its PID.

  Args:
    process_id: The PID of the process to terminate.
  """
  subprocess.check_call(["taskkill", "/F", "/T", "/PID", str(process_id)])

class EasyApplyBot:
    setupLogger()
    # MAX_SEARCH_TIME is 12 hours by default, feel free to modify it
    MAX_SEARCH_TIME = 12 * 60 * 60
    # LinkedIn limits how many you can apply to per day. After that it doesn't allow one to click the easy apply button
    MAX_ALLOWED_POSITIONS_TO_APPLY_TO_PER_DAY = 249

    #@profile
    def __init__(self,
                 username,
                 password,
                 filename='output.csv',
                 blacklist={},
                 blackListTitles={}) -> None:

        past_ids: set | None = self.get_appliedIDs(filename)
        self.appliedJobIDs: set = past_ids if past_ids != None else {}
        self.filename: str = filename
        self.options = self.browser_options()
        self.browser = driver
        self.wait = WebDriverWait(self.browser, 45)
        self.blacklist = blacklist
        self.blackListTitles = blackListTitles
        self.start_linkedin(username, password)

    #@profile
    def get_appliedIDs(self, filename) -> set | None:
        try:
            df = pd.read_csv(filename,
                            header=None,
                            names=['timestamp', 
                                    'jobID', 
                                    'job', 
                                    'company', 
                                    'attempted', 
                                    'result'],
                            lineterminator=None, #If you're not dealing with a specific case of line terminators, it's better to leave lineterminator as None and let pandas automatically handle line endings.
                            # parse_dates=['timestamp'],  # Parse the 'timestamp' column as datetime
                            # date_parser=lambda x: pd.to_datetime(x, format="%d/%m/%Y %H:%M"),  # Custom parser for the date format
                            #dtype={'jobID': 'int64'},
                            encoding='Windows-1252',
                            engine='c',  # Use the faster C engine
                            )
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], format="%d/%m/%Y %H:%M")

            df = df[df['timestamp'] > (datetime.now() - timedelta(days=14))]

            today = date.today()
            jobs_today = df[df['timestamp'].dt.date == today] 

            global num_successful_jobs_global_variable 
            num_successful_jobs_global_variable = len(jobs_today[jobs_today['result'] == True])

            #the limit seem to be 249 succesfully applied to jobs in 24hours, after that, Linkedin doesn't let you click the button. Add code check to do nothing once the daily limit is reached
            #then add the script to daily autostart, to apply till it reaches its daily limit
            if num_successful_jobs_global_variable > 249:
                log.debug("You have applied to more than 249 jobs today. Exiting the app...")
                # Get the PID of the process with "cmd.exe" and "easyapplybot.py" in its name.
                if process_id is not None:
                    terminate_process(process_id)
                    exit() #just incase if running from the VSC
                else:
                    exit() #just incase if running from the VSC

            # converting to set removes duplicates, and they're faster than lists for purpose of this program
            jobIDs = set(df.jobID)
            log.info(f"{len(jobIDs)} jobIDs found after filtration and removal of duplicates")

            return jobIDs
        except Exception as e:
            log.info(str(e) + "   jobIDs could not be loaded from CSV {}".format(filename))
            return None

    #@profile
    def browser_options(self):
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument('--no-sandbox')
        options.add_argument("--disable-extensions")

        # disables “Chrome is being controlled by automated software” infobar, which is anoying as it takes away from useful space
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        # Disable webdriver flags or you will be easily detectable
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")
        return options

    #@profile
    def start_linkedin(self, username, password) -> None:
        log.info("Logging in.....Please wait :)  ")
        self.load_page_and_wait_until_it_stops_loading("https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin")
        try:
            user_field = self.browser.find_element("id","username")
            pw_field = self.browser.find_element("id","password")
            login_button = self.browser.find_element("xpath",
                        '//*[@id="organic-div"]/form/div[3]/button')
            user_field.send_keys(username)
            #user_field.send_keys(Keys.TAB)
            #time.sleep(2)
            pw_field.send_keys(password)
            #time.sleep(2)
            login_button.click()
            time.sleep(3)
        except TimeoutException:
            log.info("TimeoutException! Username/password field or login button not found")

        if "verification" in self.browser.title.lower():
            winsound.PlaySound("C:\Windows\Media\chimes.wav", winsound.SND_FILENAME)
            input("Press Enter to continue...") # pause the script in case of captcha type verification
            log.debug("captcha verification needed")

    #@profile
    def start_apply(self, positions, locations) -> None:
        # Define the CSV file name
        csv_combo_log_file = 'combos_output_log.csv'

        df = pd.read_csv(csv_combo_log_file, 
                         names=['Date', 'Combo'], 
                         parse_dates=['Date'],
                         date_parser=lambda x: pd.to_datetime(x, format='%d/%m/%Y %H:%M')
                         )

        # Get the current date and time
        current_datetime = datetime.now()

        # Calculate the timestamp 24 hours ago from the current date and time
        twenty_four_hours_ago = current_datetime - timedelta(hours=24)

        # Filter rows based on timestamp within the last 24 hours
        filtered_df = df[df['Date'] > twenty_four_hours_ago]

        # Extract the 'Combo' values into a list of tuples
        combos_within_last_24_hours = list(filtered_df['Combo'])
        combos_within_last_24_hours = [tuple(eval(combo)) for combo in combos_within_last_24_hours]

        # Now convert the list of tuples to a tuple
        combos_within_last_24_hours = tuple(combos_within_last_24_hours)
        
        combos: list = []
        while len(combos) < len(positions) * len(locations):
            position = positions[random.randint(0, len(positions) - 1)]
            location = locations[random.randint(0, len(locations) - 1)]
            combo: tuple = (position, location)
            if combo not in combos:
                combos.append(combo)
                if combo not in combos_within_last_24_hours:
                    # log.debug(f"Combos already applied to: {combos}")
                    log.debug(f"Number of job/location combos already applied to: {len(combos)}")
                    log.debug(f"All possible job/location combos given the config.yaml file: {len(positions) * len(locations)}")
                    log.debug(f"Remaining job/location combos to apply to: {(len(positions) * len(locations))-len(combos)}")
                    log.info(f"Applying to {position}: {location}")
                    location = "&location=" + location
                    self.applications_loop(position, location)

                # Open the CSV file in append mode with the specified encoding and line terminator
                with open(csv_combo_log_file, 
                          mode='a', 
                          encoding='Windows-1252', 
                          newline=None) as file:
                    writer = csv.writer(file)

                    # Get the current date and time in the desired format
                    current_datetime = datetime.now().strftime('%d/%m/%Y %H:%M')

                    # Log the combo along with the current date and time to the CSV file
                    writer.writerow([current_datetime, combo])

    #@profile
    def applications_loop(self, position, location):

        count_application = 0
        count_job = 0
        jobs_per_page = 0
        start_time: float = time.time()

        self.browser, _ = self.next_jobs_page(position, location, jobs_per_page)
        log.info("Looking for jobs.. Please wait..")

        while time.time() - start_time < self.MAX_SEARCH_TIME:
            try:
                # sleep to make sure everything loads, add random to make us look human.
                # randoTime: float = random.uniform(3.5, 4.9)
                # log.debug(f"Sleeping for {round(randoTime, 1)}")
                # time.sleep(randoTime)

                # exit this combo if the page contains "No matching jobs found." as it will have some jobs listed, but those are "Jobs you may be interested in" which are not very relevant location wise
                if "No matching jobs found" in self.browser.page_source:
                    log.debug("No matching jobs found. Moving onto next job/location combo")
                    break

                # get job links, (the following are actually the job card objects)
                links = self.browser.find_elements("xpath",
                                                   '//div[@data-job-id and .//text()[contains(., "Easy Apply")]]'
                )

                if len(links) == 0:
                    log.debug("No links found")
                    jobs_per_page = jobs_per_page + 25
                    count_job = 0
                    log.info("""****************************************\n\n
                    Going to next jobs page, YEAAAHHH!!
                    ****************************************\n\n""")
                    self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                    location,
                                                                    jobs_per_page)
                    # break #that will move onto the next combo, but that's not what we want, we want to go into the next page instead

                else: # we have some links, but first one of them are over 1 week old, then skip this job/location combo, and move to the next one # TODO: would be beneficial to add this to config.yaml as an option
                    # raw links[0].text is like 'Senior QA Automation Engineer\nSenior QA Automation Engineer\nWeDo \nUnited Kingdom (Remote)\n£70K/yr - £75K/yr\nActively recruiting\n3 days ago\nEasy Apply'
                    first_link_text = links[0].text.split('\n')[-2]
                    if any(phrase in first_link_text for phrase in ["week ago", 
                                                                    "6 days ago", 
                                                                    "5 days ago", 
                                                                    "4 days ago", 
                                                                    #"3 days ago", 
                                                                    #"2 days ago", 
                                                                    "weeks ago",  
                                                                    "month ago", 
                                                                    "months ago"]):
                        log.debug("moving onto the next combo, due to no new jobs available to apply to for this combo")
                        break # this skips this job/location combo

                    last_link_text = links[-1].text # don't put this further down, as you will then get StaleElementReferenceException(). Also don't do last_link = links[-1] as that would be reference assignment only, and not hold a copy

                    rawLinksEasyApplyCount = 0
                    IDs = set() # type set on purpose, as they won't be repeating themselves
                    
                    # children selector is the container of the job cards on the left
                    for link in links:
                        rawLinksEasyApplyCount += 1

                        temp = link.get_attribute("data-job-id")#[:10]  # Limit job ID to 10 characters
                        if temp == "search":
                            temp = link.get_attribute("data-job-id")
                            if temp == 'search':
                                continue #moving onto the next link
                        jobID = int(temp)
                        #jobID = int(temp.split(":")[-1])

                        if jobID not in self.appliedJobIDs: # be careful if they are both of the same type - string, mixed types won't work. Now it works.
                            self.appliedJobIDs.add(jobID)
                            # Extract what is needed (once they changed this on their end..., and you needed to change [1] to [2])
                            lines = link.text.lower().split('\n')
                            inputTextJobTitle = lines[0]
                            inputTextCompanyBlacklist = lines[2]

                            if not (any(phrase in inputTextJobTitle for phrase in self.blackListTitles) 
                                    or 
                                    any(phrase in inputTextCompanyBlacklist for phrase in self.blacklist)):                          
                                    # Symmetric Difference (symmetric_difference):
                                        # Returns a new set containing elements that are present in either of the sets, but not in both. DON'T DO IT, union in this case is an equivalent. Symetric difference cannot handle strings, union can
                                IDs.add(jobID)

                    log.info("it found this many job IDs with EasyApply button: %s", rawLinksEasyApplyCount)
            
                    length_of_ids = len(IDs)
                    log.info("it found this many job IDs with EasyApply button and not containing any blacklisted phrases, as well as filtration of already applied to jobs: %s", length_of_ids)
                    # # remove already applied jobs
                    # jobIDs = set(IDs).difference(self.appliedJobIDs)
                    # # given how the script works now, it should be the same number to this print and the above print, unless you also implement filtration by the job titles without opening the thing  
                    # log.info("This many job IDs passed filtration: %s", len(jobIDs))

                    # assumes it didn't find any suitable job, moving onto the next page
                    if len(IDs) == 0:
                        jobs_per_page = jobs_per_page + 25
                        count_job = 0
                        self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                        location,
                                                                        jobs_per_page)
                    else:
                        # loop over IDs to apply
                        # although _ doesn't seem used, don't delete it. It's there for a reason
                        for _, jobID in enumerate(IDs):
                            count_job += 1
                            self.get_job_page(jobID)

                            while self.browser.find_elements(By.XPATH, "//*[contains(text(), 'We experienced an error loading this application. Save this job to try again later.')]"):
                                self.get_job_page(jobID)

                            # get easy apply button
                            easyApplyButton = self.get_easy_apply_button()


                            if easyApplyButton is not False:
                                string_easy = "* has Easy Apply Button"
                                log.info("Clicking the EASY apply button")

                                while True:
                                    try:
                                        if easyApplyButton.is_enabled():
                                            easyApplyButton.click()
                                            try:
                                                # Wait for the <h2> element to become visible
                                                WebDriverWait(self.browser, 10).until(
                                                    EC.visibility_of_element_located((By.ID, "jobs-apply-header"))
                                                )
                                                print("Element is visible. Clicking Easy Apply button successful.")
                                                break  # exit the While loop if the element is visible
                                            except Exception as e:
                                                print(f"Error: {e}")
                                    except StaleElementReferenceException:
                                        # If the element is stale, try to find it again
                                        easyApplyButton = self.get_easy_apply_button()
                                        continue
                                    # else:
                                    #     self.browser.execute_script("""
                                    #         let xpathExpression = '//button[contains(@class, "jobs-apply-button")]';
                                    #         let matchingElement = document.evaluate(xpathExpression, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                    #         if (matchingElement) {
                                    #             matchingElement.click();
                                    #         }
                                    #     """)
                                    #     try:
                                    #         # Wait for the <h2> element to become visible
                                    #         WebDriverWait(self.browser, 10).until(
                                    #             EC.visibility_of_element_located((By.ID, "jobs-apply-header"))
                                    #         )
                                    #         print("Element is visible. Clicking Easy Apply button successful.")
                                    #         break  # exit the While loop if the element is visible
                                    #     except Exception as e:
                                    #         print(f"Error: {e}")

                                result: bool = self.send_resume()
                                count_application += 1
                            else:
                                log.info("The button does not exist.")
                                string_easy = "* Doesn't have Easy Apply Button"
                                # TODO: job ID should be added to applied to, to avoid it being openend again, dones already, but keep this here, as it's another way know where to insert that
                                result = False

                            position_number: str = str(count_job + jobs_per_page)

                            # Define a regular expression pattern to match non-UTF-8 characters
                            non_utf8_pattern = re.compile(r'[^\x00-\x7F]+')

                            # Remove or replace non-UTF-8 characters with a space
                            cleaned_title = re.sub(non_utf8_pattern, ' ', self.browser.title)

                            sanitisedBrowserTitle = cleaned_title.encode("utf-8").decode("utf-8")

                            log.info(f"Position {position_number}:\n {sanitisedBrowserTitle} \n {string_easy} \n")

                            self.write_to_file(easyApplyButton, jobID, sanitisedBrowserTitle, result)

                            # go to new page if all jobs are done
                            if count_job == len(IDs):                        
                                # break right here in case last job was old, this will save another reload, and just speed thing up in general. If it matches, do a break statement, which will move onto the next job/location combo
                                if any(phrase in last_link_text for phrase in ["week ago", 
                                                                        "6 days ago", 
                                                                        "5 days ago", 
                                                                        #"4 days ago", 
                                                                        #"3 days ago", 
                                                                        #"2 days ago", 
                                                                        "weeks ago", 
                                                                        "month ago", 
                                                                        "months ago"]):
                                    log.debug("moving onto the next combo, due to no new jobs available to apply to for this combo")
                                    break # this skips this job/location combo
                                jobs_per_page = jobs_per_page + 25
                                count_job = 0
                                log.info("""****************************************\n\n
                                Going to next jobs page, YEAAAHHH!!
                                ****************************************\n\n""")
                                self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                                location,
                                                                                jobs_per_page)
            except Exception as e:
                log.info(e)

    #@profile
    def write_to_file(self, button, jobID, browserTitle, result) -> None:
        #@profile
        def re_extract(text, pattern):
            target = re.search(pattern, text)
            if target:
                target = target.group(1)
            return target

        timestamp: str = datetime.now().strftime('%d/%m/%Y %H:%M')
        attempted: bool = False if button == False else True
        # Split the browserTitle once and store the results
        parts = browserTitle.split(' | ')

        # Extract job ID and company information with regular expressions
        job = re_extract(parts[0], r"\(?\d?\)?\s?(\w.*)")[:10]  # Limit job ID to 10 characters
        company = re_extract(parts[1], r"(\w.*)")

        toWrite: list = [timestamp, jobID, job, company, attempted, result]
        with open(self.filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(toWrite)

    #@profile
    def get_job_page(self, jobID):

        job: str = 'https://www.linkedin.com/jobs/view/' + str(jobID)
        self.load_page_and_wait_until_it_stops_loading(job)
        self.job_page = self.load_page(sleep=0.5)
        return self.job_page

    #@profile
    def get_easy_apply_button(self):
        while True:
            try:
                if self.browser.find_elements(By.XPATH, "//*[contains(text(), 'Something went wrong')]"):
                    self.browser.refresh()
                if self.browser.find_elements(By.XPATH, "//*[contains(text(), 'No longer accepting applications')]"):
                    easyApplyButton = False
                    break

                self.wait.until(EC.presence_of_all_elements_located((By.XPATH, '//button[contains(@class, "jobs-apply-button")]')))
                button = self.browser.find_elements("xpath",
                    '//button[contains(@class, "jobs-apply-button")]'
                    )

                easyApplyButton = button[1]
                if easyApplyButton:
                    break # Exit the loop if button is found successfully
            except IndexError: # this happens very rarely, it hapened only once after 1500 succesful applications
                print("Button not found. Waiting for 2 seconds and trying again...")
                time.sleep(2)  # Wait for 2 seconds before trying again
                easyApplyButton = False
                break
            except Exception as e: 
                log.info("Exception:",e)
                easyApplyButton = False
                break

        return easyApplyButton        

    #@profile
    def send_resume(self) -> bool:
        #@profile
        def is_present(button_locator) -> bool:
            return len(self.browser.find_elements(button_locator[0],
                                                  button_locator[1])) > 0

        try:
            time.sleep(random.uniform(1.5, 2.5))
            next_locater = (By.CSS_SELECTOR,
                            "button[aria-label='Continue to next step']")
            review_locater = (By.CSS_SELECTOR,
                              "button[aria-label='Review your application']")
            submit_locater = (By.CSS_SELECTOR,
                              "button[aria-label='Submit application']")
            submit_application_locator = (By.CSS_SELECTOR,
                                          "button[aria-label='Submit application']")
            # follow_locator = (By.CSS_SELECTOR, "label[for='follow-company-checkbox']")
            term_agree = (By.CSS_SELECTOR, "label[data-test-text-selectable-option__label='I Agree Terms & Conditions']")

            question_element = (By.XPATH, "//span[contains(text(), 'Will you now or in the future require sponsorship for employment visa status?')]")

            question_element_was_it_clicked_once_already_for_this_submission = False

            submitted = False
            while True:
                if is_present(term_agree):
                    button: None = self.wait.until(EC.element_to_be_clickable(term_agree))
                    button.click()
                    time.sleep(random.uniform(1.5, 2.5))

                if is_present(question_element) and not question_element_was_it_clicked_once_already_for_this_submission:
                    input_element = self.browser.find_element(By.XPATH, 
                                                              "//span[contains(text(), 'Will you now or in the future require sponsorship for employment visa status?')]")
                    question_element_was_it_clicked_once_already_for_this_submission = True
                    input_element.click()
                    time.sleep(1)
                    # Create an ActionChains object
                    actions = ActionChains(self.browser)
                    # Send keys to the browser window using ActionChains
                    actions.send_keys(Keys.TAB).perform()
                    time.sleep(1)
                    actions.send_keys(Keys.DOWN).perform()
                    # actions.send_keys(Keys.SPACE).perform()
                    time.sleep(random.uniform(1.5, 2.5))

                # Click Next or submitt button if possible
                button: None = None
                buttons: list = [next_locater, 
                                 review_locater, 
                                 #follow_locator, #good and works, but slows you down unecesserly, when following doesn't cause indentified harm
                                 submit_locater, 
                                 submit_application_locator]
                for i, button_locator in enumerate(buttons):
                    if is_present(button_locator):
                        button: None = self.wait.until(EC.element_to_be_clickable(button_locator))

                    succesfully_finished_submission = self.browser.find_elements(By.XPATH,
                                                                                 "//*[@class='artdeco-button__text'][contains(text(), 'Done')]")
                    
                    succesfully_finished_submission_check2 = self.browser.find_elements(By.XPATH,
                                                                                 "//*[@class='jpac-modal-header'][contains(text(), 'Your application was sent to')]")
                    
                    succesfully_finished_submission_check3 = self.browser.find_elements(By.XPATH,
                                                                                 "//*[@class='t-black--light'][contains(text(), 'You can keep track of your application in the \"Applied\" tab of My Jobs')]")

                    if (succesfully_finished_submission or 
                        succesfully_finished_submission_check2 or 
                        succesfully_finished_submission_check3
                        ):
                        submitted = True
                        break

                    # Find the element with the class "artdeco-inline-feedback__message"
                    # Find all of the elements with the class "artdeco-inline-feedback__message"
                    message_elements = self.browser.find_elements(By.CLASS_NAME, "artdeco-inline-feedback__message")

                    # Flag variable to track whether we need to break out of the outer loop
                    break_outer_loop = False

                    # Iterate over the message elements and print the text of each one
                    # for message_element in message_elements:
                    if message_elements:
                        # message_text = message_element.text
                        # log.info(message_text)
                        break_outer_loop = True  # Set the flag to break the outer loop
                        log.debug("setting break_outer_loop to True, due to 'message_elements' existing")
                        # winsound.PlaySound("C:\Windows\Media\chimes.wav", winsound.SND_FILENAME)
                        # input("Press Enter to continue...")
                        # print("needed manual intervention")
                        break

                    if break_outer_loop:
                        break  # Break the outer loop if the flag is set

                    if button:
                        button.click()
                        time.sleep(random.uniform(1.5, 2.5))
                        if i in (3, 4):
                            submitted = True
                        if i != 2:
                            break
                if break_outer_loop: #button is None or break_outer_loop:
                    log.info(f"Could not complete submission, break_outer_loop is {break_outer_loop} and button is {button}") # if you don't figure it out why it sometimes skips valid jobs here, you will be logging job ids and applying to them manually - they all have easy apply
                    # TODO: job ID should be added to applied to, to avoid it being openend again
                    break
                elif submitted:
                    global num_successful_jobs_global_variable
                    num_successful_jobs_global_variable += 1
                    log.info(f"Application Submitted. Today you have applied to {num_successful_jobs_global_variable} jobs")

                    if (num_successful_jobs_global_variable > 249):
                        log.debug("You have applied to more than 249 jobs today. Exiting the app...")
                        # Get the PID of the process with "cmd.exe" and "easyapplybot.py" in its name.
                        process_id = get_process_id("automated-LinkedIn-applying\\run_script.bat")
                        if process_id is not None:
                            terminate_process(process_id)
                            exit() #just incase if running from the VSC
                        else:
                            exit() #just incase if running from the VSC
                    break

            time.sleep(random.uniform(1.5, 2.5))


        except Exception as e:
            log.info(e)
            log.info("cannot apply to this job")
            raise (e)

        return submitted

    #@profile
    def load_page(self, sleep=1):
        if sleep == 2:
            self.wait.until(lambda driver: self.browser.execute_script('return document.readyState') == 'complete')

            try:
                scrollresults = self.browser.find_element(By.CLASS_NAME,
                    "jobs-search-results-list")
            except NoSuchElementException:  
                self.browser.refresh()
                scrollresults = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "jobs-search-results-list")))
                scrollresults = self.browser.find_element(By.CLASS_NAME, "jobs-search-results-list")

            # Detect if it says on the website "No matching jobs found", if so, don't waste time on scrolling the search results
            try:
                if "No matching jobs found" in self.browser.page_source:
                    # return BeautifulSoup(self.browser.page_source, "lxml")
                    return
                
            except NoSuchElementException:
                # No "No matching jobs found" message was found, continue with scrolling
                pass

            # in case of just one result no scrolling is necessery 
            # Max number of results is 25 (on one page, but technically it can say in text 143 results, it will be just multiple pages), and currently you have 21 scrolls to scroll it fully, and that works perfectly. The scrolling code works perfect, don't change, it's efficient
            if not self.browser.find_elements(By.XPATH, "//*[contains(text(), '1 result')]"):
                # Regular expression to find the pattern and extract the number
                pattern = r'"USER_LOCALE","text":"(\d+) results"'
                # Search for the first match in the page source
                match = re.search(pattern, self.browser.page_source)
                result = int(match.group(1)) if match and int(match.group(1)) <= 19 else 20
                # Selenium only detects visible elements; if we scroll to the bottom too fast, only 8-9 results will be loaded into IDs list
                for i in range(300, result*150+300, 150): #potential for speeding up, just increase the last value gradually
                    self.browser.execute_script("arguments[0].scrollTo(0, {})".format(i), scrollresults)
                    time.sleep(0.3) # otherwise it scrolls too fast

        return BeautifulSoup(self.browser.page_source, "lxml")

    #@profile
    def next_jobs_page(self, position, location, jobs_per_page):
        #"&f_AL=true" makes sure only easy apply jobs appear
        #"&sortBy=DD" sorts by the most recent
        self.load_page_and_wait_until_it_stops_loading("https://www.linkedin.com/jobs/search/?f_LF=f_AL" + "&f_AL=true" + "&keywords=" +
            position + location + "&sortBy=DD" + "&start=" + str(jobs_per_page))
            
        # todo: now that would be a good call to do that scrolling thing, of the left pane
        self.load_page(sleep=2)
        return (self.browser, jobs_per_page)
    
    #@profile
    def load_page_and_wait_until_it_stops_loading(self, job_url):
        self.browser.get(job_url)
        self.wait.until(lambda driver: self.browser.execute_script('return document.readyState') == 'complete')
        # Page is now fully loaded and ready to be interacted with

if __name__ == '__main__':
    with open("config.yaml", 'r') as stream:
        try:
            parameters = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise exc

    assert len(parameters['positions']) > 0
    assert len(parameters['locations']) > 0
    assert parameters['username'] is not None
    assert parameters['password'] is not None

    log.info({k: parameters[k] for k in parameters.keys() if k not in ['username', 'password']})

    output_filename: list = [f for f in parameters.get('output_filename', ['output.csv']) if f != None]
    output_filename: list = output_filename[0] if len(output_filename) > 0 else 'output.csv'
    blacklist = {phrase.lower() for phrase in parameters.get('blacklist', {})}
    blackListTitles = {phrase.lower() for phrase in parameters.get('blackListTitles', {})}

    bot = EasyApplyBot(parameters['username'],
                       parameters['password'],
                       filename=output_filename,
                       blacklist=blacklist,
                       blackListTitles=blackListTitles
                       )

    locations: list = [l for l in parameters['locations'] if l != None]
    positions: list = [p for p in parameters['positions'] if p != None]
    bot.start_apply(positions, locations)

    log.debug("controlled exit due to all job/location combos being processed successfully")
    # Get the PID of the process with "cmd.exe" and "easyapplybot.py" in its name.
    if process_id is not None:
        terminate_process(process_id)
        exit() #just incase if running from the VSC, defensive programming.
    else:
        exit() #just incase if running from the VSC

# make it run headless unless last login attempt lead to captcha, as a setting in the config.yaml

# TODO: play around with auto filling fields which require a number with 0, as it will increase autocompletion rate of applications

# TODO: searching for jobs should happen in parrarel, in other tab, as you're applying to jobs in another tab, to make applying to jobs faster

# TODO: compare with the LineProfiler, how much faster a headless version would be.

# handle it in a specific way, but for other problems, do a timer/count number of tries, then first refresh, and if that fails, move onto the next job

    # if "Tunnel Connection Failed" refresh the website

# right now, you're assesing how many applications applied to by one way of counting. Make sure for the script to be able to also pick up on other ways when for example easyapply button becomes grayed out due to applying to over 250 jobs/day. In those cases the script should exit both loops

# looking if first job is not "weeks" old, should be done before even scrolling down, and if so, move to the next combo, although that will require serious reorganization of the code, and the current code works well, it's just that sub functionality could be improved to gain a few seconds if the combo is early discarded

# <h3 class="jpac-modal-header t-20 t-bold pt0 pb2">
#     Your application was sent to Ciphr!
#   </h3>

# ________________

# <div class="t-14 t-black--light text-align-center mh8">You can keep track of your application in the "Applied" tab of My Jobs</div>