# coding=utf-8

from __future__ import annotations
import time, random, os, csv
import logging
import ast
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
import pandas as pd
import winsound
import yaml
from datetime import datetime, timedelta
from os import path
#from line_profiler import LineProfiler # it's for profiling program efficiency and timing it's execution line by line. Connected to #@profile . First $ kernprof -l .\easyapplybot.py -> Then $ python -m line_profiler .\easyapplybot.py.lprof > output.txt to generate output. To get timings in seconds on that output file, multiply them by [time]×0.000001
from get_process_id import get_process_id, terminate_process
import sys

log = logging.getLogger(__name__)

# Instead of a global variable, use a list to hold the counter value [pylint said it's better than using globals]
num_successful_jobs_global_variable = [0]

executable_path = path.dirname(__file__) + r"\assets\chromedriver.exe"

service = Service(executable_path = path.dirname(__file__) + r"\assets\chromedriver.exe") #https://googlechromelabs.github.io/chrome-for-testing/

del executable_path

# def print_variable_sizes(scope: dict, scope_name: str):
#     """Prints memory usage of all variables in a given scope."""
#     print(f"\nMemory usage in {scope_name}:")
#     total_size = 0

#     for var_name, var_value in scope.items():
#         size = sys.getsizeof(var_value)
#         total_size += size
#         print(f"{var_name}: {size / 1024:.2f} KB")

#     print(f"Total memory: {total_size / 1024:.2f} KB")

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

process_id = get_process_id("automated-LinkedIn-applying\\run_script.bat")

class EasyApplyBot:
    setupLogger()

    #@profile
    def __init__(self,
                 phoneNumber,
                 filename='output.csv',
                 blacklist_param=None,
                 blackListTitles_param=None) -> None:
        
        # Initialize the sets if the arguments are None
        self.blacklist = blacklist_param if blacklist_param is not None else set()
        self.blackListTitles = blackListTitles_param if blackListTitles_param is not None else set()

        past_ids: set | None = self.get_appliedIDs(filename)
        self.appliedJobIDs: set = past_ids if past_ids is not None else set()
        self.filename: str = filename
        self.phoneNumber = phoneNumber

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
                            usecols=[0, 1, 2, 3, 4, 5],  # Specify the columns to read (ignore extras)
                            encoding='Windows-1252',
                            engine='c',  # Use the faster C engine
                            )
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], format="%d/%m/%Y %H:%M")

            df = df[df['timestamp'] > (datetime.now() - timedelta(days=14))]

            # converting to set removes duplicates, and they're faster than lists for purpose of this program
            jobIDs = set(df.jobID)
            log.info("%d jobIDs found after filtration and removal of duplicates", len(jobIDs))

            return jobIDs
        except Exception as e:
            log.info("%s   jobIDs could not be loaded from CSV %s", str(e), filename)
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

        options.add_argument('--log-level=3')
        #options.binary_location = chrome_path

        #the below enabled headless mode (enabled 22:13 16/7/2024 - for performance stats)
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")  # Required for some environments 
        options.add_argument("--disable-browser-side-navigation")
        # options.add_argument('--blink-settings=imagesEnabled=false')  # Disable loading images. Causes problems with LinkedIn
        return options

    #@profile
    def start_linkedin(self, username, password) -> None:
        log.info("Logging in.....Please wait :)  ")
        self.load_page_and_wait_until_it_stops_loading("https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin")
        #pass
        try:
            user_field = self.browser.find_element("id","username")
            pw_field = self.browser.find_element("id","password")
            login_button = self.browser.find_element(By.XPATH, "//button[@data-litms-control-urn='login-submit']")
            user_field.send_keys(username)
            pw_field.send_keys(password)
            # Wait for the link to be clickable and then click it
            WebDriverWait(self.browser, 10, poll_frequency=0.2).until(
                EC.element_to_be_clickable(login_button)
            )
            login_button.click()
            #time.sleep(3)
        except TimeoutException:
            log.info("TimeoutException! Username/password field or login button not found")

        if "verification" in self.browser.title.lower():
            winsound.PlaySound(r"C:\Windows\Media\chimes.wav", winsound.SND_FILENAME)
            input("Press Enter to continue...") # pause the script in case of captcha type verification
            log.debug("captcha verification needed")

    #@profile
    def start_apply(self, positions_param, locations_param, username, password) -> None:
        # Define the CSV file name
        csv_combo_log_file = 'combos_output_log.csv'

        df = pd.read_csv(csv_combo_log_file, 
                         names=['Date', 'Combo'], 
                         parse_dates=['Date'],
                         date_parser=lambda x: pd.to_datetime(x, format='%d/%m/%Y %H:%M')
                         )

        # Calculate the timestamp 48 hours ago from the current date and time
        forty_eight_hours_ago = datetime.now() - timedelta(hours=48)

        # Filter rows based on timestamp within the last 48 hours
        filtered_df = df[df['Date'] > forty_eight_hours_ago]

        # Extract the 'Combo' values into a list of tuples
        combos_within_last_48_hours = list(filtered_df['Combo'])
        combos_within_last_48_hours = [tuple(ast.literal_eval(combo)) for combo in combos_within_last_48_hours]


        # Now convert the list of tuples to a tuple
        combos_within_last_48_hours = tuple(combos_within_last_48_hours)

        executingForTheFirstTime = True
        
        combos: list = []
        while len(combos) < len(positions_param) * len(locations_param):
            for location in locations_param:
                for position in positions_param:
                    combo: tuple = (position, location)
                    if combo not in combos:
                        combos.append(combo)
                        if combo not in combos_within_last_48_hours:
                            # so if here and this is executing for the first time, only then it should open up and long into the linkedin
                            if executingForTheFirstTime:
                                driver = webdriver.Chrome(options=self.browser_options(), service=service) # this will launch the browser, so if you want to delay that step move it, but then you will need to pass it somehow, and be defined globally, not locally inside a function

                                # Enable the Network domain to block URLs
                                driver.execute_cdp_cmd("Network.enable", {})

                                # Block requests from 'media.licdn.com' which is only pics (profile and compnay logos)
                                driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": 
                                                                                [
                                                                                    "*://media.licdn.com/*",
                                                                                    "*://www.linkedin.com/sensorCollect/?action=reportMetrics"
                                        ]})

                                self.browser = driver
                                self.wait = WebDriverWait(self.browser, 45)
                                self.start_linkedin(username, password)
                                executingForTheFirstTime = False

                            log.debug("Number of job/location combos already applied to: %d", len(combos))
                            log.debug("All possible job/location combos given the config.yaml file: %d", len(positions_param) * len(locations_param))
                            log.debug("Remaining job/location combos to apply to: %d", (len(positions_param) * len(locations_param)) - len(combos))
                            log.info("Applying to %s: %s", position, location)
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
        inputTextJobTitle = ''
        inputTextCompanyTitle = ''

        self.next_jobs_page(position, location, jobs_per_page)

        log.info("Looking for jobs.. Please wait..")

        while True:
            try:
                # exit this combo if the page contains "No matching jobs found." as it will have some jobs listed, but those are "Jobs you may be interested in" which are not very relevant location wise
                if "No matching jobs found" in self.browser.page_source:
                    log.debug("No matching jobs found. Moving onto next job/location combo")
                    break


                container = self.browser.find_element("css selector", "#main > div > div.scaffold-layout__list-detail-inner.scaffold-layout__list-detail-inner--grow > div.scaffold-layout__list > div > ul")
                # get job links, (the following are actually the job card objects)

                links = container.find_elements(By.XPATH, './/div[@data-job-id and .//text()[contains(., "Easy Apply")]]')

                if len(links) == 0:
                    log.debug("No links found")
                    jobs_per_page = jobs_per_page + 25
                                        #if jobs_per_page is <= than "results" then abandon, and move on to the next combo
                    # Locate the element and get the text
                    try:
                        element = self.browser.find_element(By.XPATH, '//*[@id="main"]/div/div[2]/div[1]/header/div[1]/small/div/span')
                    except NoSuchElementException:
                        self.browser.refresh()
                        element = self.wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="main"]/div/div[2]/div[1]/header/div[1]/small/div/span')))
                    text = element.text

                    # Remove " results" or " result" from the text
                    if " results" in text:
                        text = text.replace(" results", "").replace(",", "")
                    elif " result" in text:
                        text = text.replace(" result", "").replace(",", "")
                    
                    # Convert the cleaned text to a number
                    number = int(text)

                    if jobs_per_page >= number:
                        # it would break and move onto the next combo
                        break
                    count_job = 0
                    log.info("""****************************************\n\n
                    Going to next jobs page, YEAAAHHH!!
                    ****************************************\n\n""")
                    self.next_jobs_page        (position,                                                                    location,                                                                    jobs_per_page)

                else: # we have some links, but first one of them are over 1 week old, then skip this job/location combo, and move to the next one # TODO: would be beneficial to add this to config.yaml as an option
                    # raw links[0].text is like 'Senior QA Automation Engineer\nSenior QA Automation Engineer\nWeDo \nUnited Kingdom (Remote)\n£70K/yr - £75K/yr\nActively recruiting\n3 days ago\nEasy Apply'
                    first_link_text = links[0].text.split('\n')[-2]
                    if any(phrase in first_link_text for phrase in ["week ago", 
                                                                    "6 days ago", 
                                                                    #"5 days ago", 
                                                                    #"4 days ago", 
                                                                    #"3 days ago", 
                                                                    #"2 days ago", 
                                                                    #"weeks ago",  
                                                                    #"month ago", 
                                                                    #"months ago"
                                                                    ]):
                        log.debug("moving onto the next combo, due to no new jobs available to apply to for this combo")
                        break # this skips this job/location combo

                    last_link_text = links[-1].text # don't put this further down, as you will then get StaleElementReferenceException(). Also don't do last_link = links[-1] as that would be reference assignment only, and not hold a copy

                    IDs = {} # dictionary on purpose, as they won't be repeating themselves, and pairs of values are required

                    # children selector is the container of the job cards on the left
                    for link in links:
                        temp = link.get_attribute("data-job-id")#[:10]  # Limit job ID to 10 characters
                        if temp == "search":
                            temp = link.get_attribute("data-job-id")
                            if temp == 'search':
                                continue #moving onto the next link
                        jobID = int(temp)

                        if jobID not in self.appliedJobIDs: # be careful if they are both of the same type - string, mixed types won't work. Now it works.
                            self.appliedJobIDs.add(jobID)
                            # Extract what is needed (once they changed this on their end..., and you needed to change [1] to [2])
                            lines = link.text.lower().split('\n')
                            
                            # Use try-except to handle any index issues with the lines
                            try:
                                inputTextJobTitle = lines[0]
                                inputTextCompanyTitle = lines[2]
                            except IndexError:
                                continue

                            if not (any(phrase in inputTextJobTitle for phrase in self.blackListTitles) 
                                    or 
                                    any(phrase in inputTextCompanyTitle for phrase in self.blacklist)):                          
                                    # Symmetric Difference (symmetric_difference):
                                        # Returns a new set containing elements that are present in either of the sets, but not in both. DON'T DO IT, union in this case is an equivalent. Symetric difference cannot handle strings, union can
                                #IDs.add(jobID)
                                IDs[jobID] = (link, inputTextJobTitle, inputTextCompanyTitle)

                    log.info("it found this many job IDs with EasyApply button: %s", len(links))

                    log.info("it found this many job IDs with EasyApply button and not containing any blacklisted phrases, as well as filtration of already applied to jobs: %s", len(IDs))

                    # assumes it didn't find any suitable job, moving onto the next page
                    if len(IDs) == 0:
                        jobs_per_page = jobs_per_page + 25

                        #if jobs_per_page is <= than "results" then abandon, and move on to the next combo
                        # Locate the element and get the text
                        try:
                            element = self.browser.find_element(By.XPATH, '//*[@id="main"]/div/div[2]/div[1]/header/div[1]/small/div/span')
                        except NoSuchElementException:
                            self.browser.refresh()
                            element = self.wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="main"]/div/div[2]/div[1]/header/div[1]/small/div/span')))
                        text = element.text

                        # Remove " results" or " result" from the text
                        if " results" in text:
                            text = text.replace(" results", "").replace(",", "")
                        elif " result" in text:
                            text = text.replace(" result", "").replace(",", "")
                        
                        # Convert the cleaned text to a number
                        number = int(text)

                        if jobs_per_page >= number:
                            # it would break and move onto the next combo
                            break

                        count_job = 0
                        self.next_jobs_page(position, location, jobs_per_page)
                    else:
                        # here it should just start appllying since it's still on the right page


                        # loop over IDs to apply
                        # although _ doesn't seem used, don't delete it. It's there for a reason
                        #for _, jobID in enumerate(IDs):
                        for jobID, values in IDs.items():
                            count_job += 1
                            link, inputTextJobTitle, inputTextCompanyTitle = values
                            
                            if count_job > 1:
                                try:
                                    # Wait for the dismiss button to be clickable and click it
                                    dismiss_button = WebDriverWait(self.browser, 5, poll_frequency=0.2).until(
                                        EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Dismiss']"))
                                    )
                                    dismiss_button.click()
                                except (NoSuchElementException, TimeoutException):
                                    pass 
                                try:
                                    # Wait for the discard button to be clickable and click it
                                    discard_button = WebDriverWait(self.browser, 5, poll_frequency=0.2).until(
                                        EC.element_to_be_clickable((By.XPATH, "//button[@data-control-name='discard_application_confirm_btn']"))
                                    )
                                    discard_button.click()
                                except (NoSuchElementException, TimeoutException):
                                    pass

                            time.sleep(random.uniform(1.5, 2.5))
                            link.click()
                            try:
                                # Wait for the link to be clickable and then click it
                                WebDriverWait(self.browser, 10, poll_frequency=0.2).until(
                                    EC.element_to_be_clickable(link)
                                )
                                link.click()
                            except (NoSuchElementException, TimeoutException):
                                pass

                            # get easy apply button
                            easyApplyButton = self.get_easy_apply_button()

                            exit_bool = False

                            if easyApplyButton is not False:
                                log.info("Clicking the EASY apply button")

                                while True:
                                    try:
                                        # if self.browser.find_elements(By.XPATH, './/div[@data-job-id and .//text()[contains(., "reached the Easy Apply application limit for today. Save this job and come back tomorrow to continue applying.")]]'):
                                        #     log.debug("You reached the Easy Apply application limit for today. Exiting the app...")
                                        #     # Get the PID of the process with "cmd.exe" and "easyapplybot.py" in its name.
                                        #     process_id = get_process_id("automated-LinkedIn-applying\\run_script.bat")
                                        #     if process_id is not None:
                                        #         terminate_process(process_id)
                                        #         exit() #just incase if running from the VSC
                                        #     else:
                                        #         exit() #just incase if running from the VSC

                                        if easyApplyButton.is_enabled():
                                            try:
                                                # Wait for the link to be clickable and then click it
                                                WebDriverWait(self.browser, 10, poll_frequency=0.2).until(
                                                    EC.element_to_be_clickable(easyApplyButton)
                                                )
                                                easyApplyButton.click()
                                            except (NoSuchElementException, TimeoutException):
                                                pass
                                            try:
                                                # Wait for the <h2> element to become visible
                                                WebDriverWait(self.browser, 20).until(
                                                    EC.visibility_of_element_located((By.ID, "jobs-apply-header"))
                                                )
                                                print("Element is visible. Clicking Easy Apply button successful.")
                                                break  # exit the While loop if the element is visible
                                            except Exception as e:
                                                print(f"Error: {e}")
                                                dismiss_button = WebDriverWait(self.browser, 5, poll_frequency=0.2).until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Dismiss']")))
                                                dismiss_button.click()
                                                time.sleep(random.uniform(1.5, 2.5))
                                                exit_bool = True
                                                break
                                
                                    except StaleElementReferenceException:
                                        # If the element is stale, try to find it again
                                        easyApplyButton = self.get_easy_apply_button()
                                        continue

                                if exit_bool:
                                    break
                                
                                result, hasNumericalFieldsBeenAutoFilled = self.send_resume(num_successful_jobs_global_variable)
                                count_application += 1
                            else:
                                log.info("The button does not exist.")
                                # TODO: job ID should be added to applied to, to avoid it being openend again, dones already, but keep this here, as it's another way know where to insert that
                                result = False

                            self.write_to_file(easyApplyButton, jobID, inputTextJobTitle, inputTextCompanyTitle, result, hasNumericalFieldsBeenAutoFilled)

                            # go to new page if all jobs are done
                            #TODO: you should not go to the next page, if there will be no next page
                            if count_job == len(IDs):                        
                                # break right here in case last job was old, this will save another reload, and just speed thing up in general. If it matches, do a break statement, which will move onto the next job/location combo
                                if any(phrase in last_link_text for phrase in ["week ago", 
                                                                        "6 days ago", 
                                                                        #"5 days ago", 
                                                                        #"4 days ago", 
                                                                        #"3 days ago", 
                                                                        #"2 days ago", 
                                                                        #"weeks ago", 
                                                                        #"month ago", 
                                                                        #"months ago"
                                                                        ]):
                                    log.debug("moving onto the next combo, due to no new jobs available to apply to for this combo")
                                    break # this skips this job/location combo
                                jobs_per_page = jobs_per_page + 25
                                count_job = 0
                                log.info("""****************************************\n\n
                                Going to next jobs page, YEAAAHHH!!
                                ****************************************\n\n""")
                                self.next_jobs_page(position, location, jobs_per_page)
            except Exception as e:
                log.info(e)

    #@profile
    def write_to_file(self, button, jobID, job, company, result, hasNumericalFieldsBeenAutoFilled) -> None:
        timestamp: str = datetime.now().strftime('%d/%m/%Y %H:%M')
        attempted: bool = not button

        toWrite: list = [timestamp, jobID, job, company, attempted, result, hasNumericalFieldsBeenAutoFilled]

        # Remove Unicode characters from string elements
        toWrite = [str(item).encode('ascii', 'ignore').decode('ascii') if isinstance(item, str) else item for item in toWrite]

        with open(self.filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(toWrite)

    #@profile
    def get_easy_apply_button(self):
        try:
            daily_applications_exceeded_element = self.browser.find_element(
                By.CLASS_NAME, 'artdeco-inline-feedback--error')
            if daily_applications_exceeded_element.text in ['You’ve reached the Easy Apply application limit for today. Save this job and come back tomorrow to continue applying.']:
                log.debug("You reached the Easy Apply application limit for today. Exiting the app...")
                # Get the PID of the process with "cmd.exe" and "easyapplybot.py" in its name.
                if process_id is not None:
                    terminate_process(process_id)
                    sys.exit() #just incase if running from the VSC
                else:
                    sys.exit() #just incase if running from the VSC
        except NoSuchElementException:
            pass

        easy_apply_button = False
        while True:
            try:
                if self.browser.find_elements(By.XPATH, "//*[contains(., 'Job search safety reminder')]"):
                    break
                # Refresh the page if an error message is found
                if self.browser.find_elements(By.XPATH, "//*[contains(text(), 'Something went wrong')]"):
                    # self.browser.refresh()
                    break

                # Break the loop if no longer accepting applications
                if self.browser.find_elements(By.XPATH, "//*[contains(., 'No longer accepting applications')]"):
                    break

                # Wait for the Easy Apply button to appear
                self.wait.until(EC.presence_of_all_elements_located((By.XPATH, '//button[contains(@class, "jobs-apply-button")]')))

                # Find and assign the Easy Apply button
                button = self.browser.find_element(By.XPATH, '//button[contains(@class, "jobs-apply-button")]')
                easy_apply_button = button
                if easy_apply_button:
                    break  # Exit the loop if the button is found successfully

            except IndexError:
                # Handles rare cases where the button is not found
                print("Button not found. Waiting for 2 seconds and trying again...")
                time.sleep(2)
                break

            except Exception as e:
                log.info("Exception: %s", e)
                break

        return easy_apply_button       

    #@profile
    def send_resume(self, num_successful_jobs_global_variable_param: list) -> tuple[bool, bool]:
        #@profile
        def is_present(button_locator) -> bool:
            return len(self.browser.find_elements(button_locator[0],
                                                  button_locator[1])) > 0

        def click_and_navigate(question_flag, question_xpath, delay_after_click=1, delay_after_tab=1):
            if not question_flag and is_present((By.XPATH, question_xpath)):
                input_element = self.browser.find_element(By.XPATH, question_xpath)
                question_flag = True
                input_element.click()
                time.sleep(delay_after_click)

                # Create an ActionChains object
                actions = ActionChains(self.browser)
                actions.send_keys(Keys.TAB).perform()
                time.sleep(delay_after_tab)
                actions.send_keys(Keys.SPACE).perform()
                time.sleep(delay_after_click)
                if question_xpath == "//span[contains(text(), 'Will you now or in the future require sponsorship for employment visa status?')]":
                    actions.send_keys(Keys.ARROW_DOWN).perform()
                    time.sleep(delay_after_click)

            return question_flag

        try:
            next_locater = (By.CSS_SELECTOR,
                            "button[aria-label='Continue to next step']")
            review_locater = (By.CSS_SELECTOR,
                              "button[aria-label='Review your application']")
            submit_application_locator = (By.CSS_SELECTOR,
                                          "button[aria-label='Submit application']")
            term_agree = (By.CSS_SELECTOR, "label[data-test-text-selectable-option__label='I Agree Terms & Conditions']")

            cancel_button = (By.XPATH, "//span[contains(@class, 'artdeco-button__text') and normalize-space(text())='Cancel']")

            phone_number_input_field = (By.XPATH, '//*[contains(@aria-describedby, "phoneNumber-nationalNumber")]')

            question_element_was_it_clicked_once_already_for_this_submission = False
            question_element_was_it_clicked_once_already_for_this_submission2 = False
            question_element_was_it_clicked_once_already_for_this_submission3 = False
            question_element_was_it_clicked_once_already_for_this_submission4 = False
            question_element_was_it_clicked_once_already_for_this_submission5 = False
            question_element_was_it_clicked_once_already_for_this_submission6 = False
            question_element_was_it_clicked_once_already_for_this_submission7 = False
            question_element_was_it_clicked_once_already_for_this_submission8 = False
            question_element_was_it_clicked_once_already_for_this_submission9 = False
            question_element_was_it_clicked_once_already_for_this_submission10 = False

            if is_present(phone_number_input_field):
                elements = self.browser.find_elements(By.XPATH, '//*[contains(@aria-describedby, "phoneNumber-nationalNumber")]')
                element = elements[0]
                current_text = element.get_attribute('value')
                if current_text:
                    pass
                else:
                    element.send_keys(self.phoneNumber)
                    time.sleep(random.uniform(1.5, 2.5))

            def fill_numerical_fields():
                """
                Finds numerical input fields, checks if they're empty, and fills them with 99 if so.

                Args:
                    driver: The Selenium WebDriver instance.
                """
                hasNumericalFieldsBeenAutoFilled = False    

                try:
                    # Locate numerical input fields (adjust the selector if needed)
                    numerical_fields = self.browser.find_elements(By.CSS_SELECTOR, "input[id^='single-line-text-form-component-formElement'][id$='-numeric'][required]") # Include type='number' too

                    for field in numerical_fields:
                        # Check if the field is empty (considering whitespace)
                        if not field.get_attribute("value").strip():
                            field.clear()  # Ensure the field is clear, even if there's whitespace
                            field.send_keys("99")
                            log.debug("Filled numerical field with 99: %s", field.get_attribute('id'))
                            hasNumericalFieldsBeenAutoFilled = True
                        else:
                            log.debug("Numerical field already has a value: %s", field.get_attribute('id'))  #For debugging or monitoring


                except Exception as e:
                    log.debug("An error occurred: %s", e)

                return hasNumericalFieldsBeenAutoFilled

            submitted = False
            hasNumericalFieldsBeenAutoFilled = False

            while True:
                if submitted:
                    break

                if self.browser.find_elements(By.XPATH, "//*[contains(., 'Job search safety reminder')]"):
                    break

                if is_present(term_agree):
                    button: None = self.wait.until(EC.element_to_be_clickable(term_agree))
                    button.click()
                    time.sleep(2)

                if is_present(cancel_button):
                    button: None = self.wait.until(EC.element_to_be_clickable(cancel_button))
                    button.click()
                    time.sleep(2)

                question_element_was_it_clicked_once_already_for_this_submission = click_and_navigate(
                    question_element_was_it_clicked_once_already_for_this_submission,
                    "//span[contains(text(), 'Will you now or in the future require sponsorship for employment visa status?')]"
                )

                question_element_was_it_clicked_once_already_for_this_submission2 = click_and_navigate(
                    question_element_was_it_clicked_once_already_for_this_submission2,
                    "//span[contains(text(), 'Are you authorized to work in the ')]"
                )

                question_element_was_it_clicked_once_already_for_this_submission3 = click_and_navigate(
                    question_element_was_it_clicked_once_already_for_this_submission3,
                    "//span[contains(text(), 'Are you comfortable commuting to this ')]"
                )

                question_element_was_it_clicked_once_already_for_this_submission4 = click_and_navigate(
                    question_element_was_it_clicked_once_already_for_this_submission4,
                    "//span[contains(text(), 'Are you comfortable working in a hybrid setting?')]"
                )

                question_element_was_it_clicked_once_already_for_this_submission5 = click_and_navigate(
                    question_element_was_it_clicked_once_already_for_this_submission5,
                    "//span[contains(text(), 'Are you comfortable working in an onsite setting?')]"
                )

                question_element_was_it_clicked_once_already_for_this_submission6 = click_and_navigate(
                    question_element_was_it_clicked_once_already_for_this_submission6,
                    "//span[contains(text(), 'Have you completed the following level of education: ')]"
                )

                question_element_was_it_clicked_once_already_for_this_submission7 = click_and_navigate(
                    question_element_was_it_clicked_once_already_for_this_submission7,
                    "//span[contains(text(), 'We must fill this position urgently. Can you start immediately?')]"
                )

                question_element_was_it_clicked_once_already_for_this_submission8 = click_and_navigate(
                    question_element_was_it_clicked_once_already_for_this_submission8,
                    "//span[contains(text(), 'Do you have the right to work in the UK without a VISA or sponsorship?')]"
                )

                question_element_was_it_clicked_once_already_for_this_submission9 = click_and_navigate(
                    question_element_was_it_clicked_once_already_for_this_submission9,
                    "//span[contains(text(), 'Do you live in the United Kingdom?')]"
                )

                question_element_was_it_clicked_once_already_for_this_submission10 = click_and_navigate(
                    question_element_was_it_clicked_once_already_for_this_submission10,
                    "//span[contains(text(), 'Are you comfortable working in a remote setting?')]"
                )

                if fill_numerical_fields():
                    hasNumericalFieldsBeenAutoFilled = True

                # Click Next or submitt button if possible
                button: None = None
                buttons: list = [next_locater, 
                                 review_locater, 
                                 submit_application_locator
                                 ]
                for i, button_locator in enumerate(buttons):
                    if is_present(button_locator):
                        button: None = self.wait.until(EC.element_to_be_clickable(button_locator))

                    # Define a list of XPaths to check
                    xpath_checks = [
                        "//*[@class='artdeco-button__text'][contains(text(), 'Done')]",
                        "//*[contains(., 'Your application was sent to')]",
                        "//*[contains(., 'You can keep track of your application in the \"Applied\" tab of My Jobs')]"
                    ]

                    # Check if any of the elements are found
                    submitted = any(self.browser.find_elements(By.XPATH, xpath) for xpath in xpath_checks)

                    # If any checks are true, set submitted to True and break
                    if submitted:
                        break

                    if self.browser.find_elements(By.XPATH, "//*[contains(., 'Job search safety reminder')]"):
                        break

                    if self.browser.find_elements(By.XPATH, "//*[contains(., 'Wie gut beherrschen Sie Deutsch')]"):
                        break

                    # print_variable_sizes(globals(), "Global Scope")  # Check global scope
                    # print_variable_sizes(locals(), "Local Scope")  # Check global scope

                    if button:
                        try:
                            # Wait for the link to be clickable and then click it
                            WebDriverWait(self.browser, 10, poll_frequency=0.2).until(
                                EC.element_to_be_clickable(button)
                            )
                            button.click()
                        except (NoSuchElementException, TimeoutException):
                            pass

                        time.sleep(2)
                        if i in (3, 4):
                            submitted = True
                        if i != 2:
                            break

                if self.browser.find_elements(By.XPATH, "//li-icon[@type='error-pebble-icon']"):
                    # it would be good here to bring forward the window, or pause to fill it by hand #breakpoint
                    break

            if submitted:
                num_successful_jobs_global_variable_param[0] += 1
                log.info("Application Submitted. Today you have applied to %d jobs", num_successful_jobs_global_variable_param[0])


            time.sleep(2)


        except Exception as e:
            log.info(e)
            log.info("cannot apply to this job")
            #raise (e)

        return submitted, hasNumericalFieldsBeenAutoFilled

    #@profile
    def load_page(self, position):
        self.wait.until(lambda driver: self.browser.execute_script('return document.readyState') == 'complete')

        if "No matching jobs found" in self.browser.page_source:
            return

        try:
            scrollresults = self.browser.find_element(By.CLASS_NAME,
                "jobs-search-results-list")
        except NoSuchElementException:  
            self.browser.refresh()
            scrollresults = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "jobs-search-results-list")))

        # Locate the element and get the text
        try:
            element = self.browser.find_element(By.XPATH, '//*[@id="main"]/div/div[2]/div[1]/header/div[1]/small/div/span')
        except NoSuchElementException:
            self.browser.refresh()
            element = self.wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="main"]/div/div[2]/div[1]/header/div[1]/small/div/span')))
        text = element.text

        # Clean the result count text and convert to an integer
        text = int(text.replace(" results", "").replace(" result", "").replace(",", ""))

        # Determine the number of scrolls required
        scroll_count = min(25, text - position) if text > position + 25 else text - position

        # Scroll only if there are more than 2 results
        if scroll_count > 2:
            for i in range(300, scroll_count * 150, 150):
                self.browser.execute_script("arguments[0].scrollTo(0, {})".format(i), scrollresults)
                time.sleep(0.3)  # Adjust the speed of scrolling

    #@profile
    def next_jobs_page(self, position, location, jobs_per_page):
        #"&f_AL=true" makes sure only easy apply jobs appear
        #"&sortBy=DD" sorts by the most recent
        job_url = f"https://www.linkedin.com/jobs/search/?f_LF=f_AL&keywords={position}{location}&sortBy=DD&start={jobs_per_page}&origin=JOBS_HOME_SEARCH_BUTTON&refresh=true"
            
        # Load the page and scroll the left pane with job results
        self.load_page_and_wait_until_it_stops_loading(job_url)

        if "No matching jobs found" in self.browser.page_source:
            return

        # try:
        #     scrollresults = self.browser.find_element(By.CLASS_NAME,
        #         #"jobs-search-results-list"
        #         "scaffold-layout__list-container")
        # except NoSuchElementException:  
        #     self.browser.refresh()
        #     scrollresults = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "scaffold-layout__list-container")))

        # Locate the element and get the text
        try:
            element = self.browser.find_element(By.XPATH, '//*[@id="main"]/div/div[2]/div[1]/header/div[1]/small/div/span')
        except NoSuchElementException:
            self.browser.refresh()
            element = self.wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="main"]/div/div[2]/div[1]/header/div[1]/small/div/span')))

        text = element.text

        # Clean the result count text and convert to an integer
        text = int(text.replace(" results", "").replace(" result", "").replace(",", ""))

        def scroll_to_every_third_job():
            job_elements = self.browser.find_elements(By.CLASS_NAME, "scaffold-layout__list-item")

            for i in range(0, len(job_elements), 3):
                job_element = job_elements[i]
                if job_element:
                    # Option 1: Direct scrollIntoView (may be inconsistent)
                    self.browser.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth' });", job_element)

                    # # Option 2: Scroll to element's location (more reliable)
                    # y_offset = job_element.location['y']
                    # self.browser.execute_script(f"window.scrollTo(0, {y_offset});")

                    time.sleep(1)  # Wait for 1 second


        while True:  # Keep trying until no placeholders are found
            self.wait.until(lambda driver: self.browser.execute_script('return document.readyState') == 'complete') # Wait for full page load initially

            placeholder_elements = self.browser.find_elements(By.CLASS_NAME, "job-card-container__ghost-placeholder")
            if placeholder_elements:
                log.debug("Placeholders found. Reloading page...")
                self.browser.refresh()
                time.sleep(5) # Increased wait time after reload (adjust as needed)
            else:  # No placeholders, proceed with scrolling
                break

        # Example usage (assuming this is inside a class with self.browser):
        scroll_to_every_third_job()

        return
    
    #@profile
    def load_page_and_wait_until_it_stops_loading(self, job_url):
        self.browser.get(job_url)
        self.wait.until(lambda driver: self.browser.execute_script('return document.readyState') == 'complete')
        # Page is now fully loaded and ready to be interacted with

if __name__ == '__main__':
    with open("config.yaml", 'r', encoding="utf-8") as stream:
        try:
            parameters = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise exc
    
    del stream

    assert len(parameters['positions']) > 0
    assert len(parameters['locations']) > 0
    assert parameters['username'] is not None
    assert parameters['password'] is not None
    assert parameters['phoneNumber'] is not None

    log.info({k: parameters[k] for k in parameters.keys() if k not in ['username', 'password']})

    output_filename: list = [f for f in parameters.get('output_filename', ['output.csv']) if f is not None]
    output_filename: list = output_filename[0] if len(output_filename) > 0 else 'output.csv'
    blacklist = {phrase.lower() for phrase in parameters.get('blacklist', {})} # set comprehension
    blackListTitles = {phrase.lower() for phrase in parameters.get('blackListTitles', {})}

    bot = EasyApplyBot(parameters['phoneNumber'],
                       filename=output_filename,
                       blacklist_param=blacklist,
                       blackListTitles_param=blackListTitles
                       )

    locations: list = [l for l in parameters['locations'] if l is not None]
    positions: list = [p for p in parameters['positions'] if p is not None]
    bot.start_apply(positions, locations, username=parameters['username'] ,password=parameters['password'])

    del parameters

    log.debug("controlled exit due to all job/location combos being processed successfully")
    # Get the PID of the process with "cmd.exe" and "easyapplybot.py" in its name.
    if process_id is not None:
        terminate_process(process_id)
        sys.exit() #just incase if running from the VSC, defensive programming.
    else:
        sys.exit() #just incase if running from the VSC

# make it run headless unless last login attempt lead to captcha, as a setting in the config.yaml

# TODO: play around with auto filling fields which require a number with 0, as it will increase autocompletion rate of applications

# TODO: searching for jobs should happen in parrarel, in other tab, as you're applying to jobs in another tab, to make applying to jobs faster

# TODO: compare with the LineProfiler, how much faster a headless version would be.

# handle it in a specific way, but for other problems, do a timer/count number of tries, then first refresh, and if that fails, move onto the next job

    # if "Tunnel Connection Failed" refresh the website

# right now, you're assesing how many applications applied to by one way of counting. Make sure for the script to be able to also pick up on other ways when for example easyapply button becomes grayed out due to applying to over 250 jobs/day. In those cases the script should exit both loops

# looking if first job is not "weeks" old, should be done before even scrolling down, and if so, move to the next combo, although that will require serious reorganization of the code, and the current code works well, it's just that sub functionality could be improved to gain a few seconds if the combo is early discarded

# use memory profiler to see how that is used