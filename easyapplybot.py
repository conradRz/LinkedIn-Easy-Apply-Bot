# coding=utf-8

import time, random, os, csv
import logging
import ast
import sys
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
from selenium.webdriver.remote.webelement import WebElement
import pandas as pd
import winsound
import yaml
from datetime import datetime, timedelta
from typing import Optional

# from line_profiler import LineProfiler # it's for profiling program efficiency and timing it's execution line by line. Connected to #@profile . First $ kernprof -l .\easyapplybot.py -> Then $ python -m line_profiler .\easyapplybot.py.lprof > output.txt to generate output. To get timings in seconds on that output file, multiply them by [time]×0.000001
from get_process_id import get_process_id, terminate_process

log = logging.getLogger(__name__)

executable_path = os.path.dirname(__file__) + r"\assets\chromedriver.exe"

service = Service(
    executable_path=os.path.dirname(__file__) + r"\assets\chromedriver.exe"
)  # https://googlechromelabs.github.io/chrome-for-testing/

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


# @profile
def setup_logger() -> None:
    dt: str = datetime.strftime(datetime.now(), "%m_%d_%Y %H_%M_%S ")

    if not os.path.isdir("./logs"):
        os.mkdir("./logs")

    # log = logging.getLogger()  # Initialize the logger

    logging.basicConfig(
        filename=("./logs/" + str(dt) + "applyJobs.log"),
        filemode="w",
        format="%(asctime)s::%(name)s::%(levelname)s::%(message)s",
        datefmt="%d-%b-%Y %H:%M:%S",
    )
    log.setLevel(logging.DEBUG)
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.DEBUG)
    c_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"
    )
    c_handler.setFormatter(c_format)
    log.addHandler(c_handler)


process_id = get_process_id("automated-LinkedIn-applying\\run_script.bat")


class EasyApplyBot:
    setup_logger()

    # @profile
    def __init__(
        self,
        phone_number,
        filename="output.csv",
        blacklist_param=None,
        blacklist_titles_param=None,
    ) -> None:

        # Initialize the sets if the arguments are None
        self.blacklist = blacklist_param if blacklist_param is not None else set()
        self.black_list_titles = (
            blacklist_titles_param if blacklist_titles_param is not None else set()
        )

        past_ids: set | None = self.get_appliedIDs(filename)
        self.applied_job_IDs: set = past_ids if past_ids is not None else set()
        self.filename: str = filename
        self.phone_number = phone_number
        # Define the CSV file name, for outputting combination succefully searched wholy
        self.csv_combo_log_file: str = "combos_output_log.csv"
        self.num_successful_jobs_global_variable: int = 0

    # @profile
    def get_appliedIDs(self, filename) -> set | None:
        try:
            df = pd.read_csv(
                filepath_or_buffer=filename,
                header=None,
                names=[
                    "timestamp",
                    "jobID",
                    "job",
                    "company",
                    "attempted",
                    "result",
                ],
                lineterminator=None,  # If you're not dealing with a specific case of line terminators, it's better to leave lineterminator as None and let pandas automatically handle line endings.
                # parse_dates=['timestamp'],  # Parse the 'timestamp' column as datetime
                # date_parser=lambda x: pd.to_datetime(x, format="%d/%m/%Y %H:%M"),  # Custom parser for the date format
                usecols=[
                    0,
                    1,
                    2,
                    3,
                    4,
                    5,
                ],  # Specify the columns to read (ignore extras)
                encoding="Windows-1252",
                engine="c",  # Use the faster C engine
            )

            df["timestamp"] = pd.to_datetime(df["timestamp"], format="%d/%m/%Y %H:%M")

            df = df[df["timestamp"] > (datetime.now() - timedelta(days=14))]

            # converting to set removes duplicates, and they're faster than lists for purpose of this program
            jobIDs = set(df.jobID)
            log.info(
                "%d jobIDs found after filtration and removal of duplicates",
                len(jobIDs),
            )

            return jobIDs
        except Exception as e:
            log.exception(
                "%s   jobIDs could not be loaded from CSV %s", str(e), filename
            )
            return None

    # @profile
    def browser_options(self) -> Options:
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-extensions")

        # disables “Chrome is being controlled by automated software” infobar, which is anoying as it takes away from useful space
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        # Disable webdriver flags or you will be easily detectable
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")

        options.add_argument("--log-level=3")
        # options.binary_location = chrome_path

        # # the below enabled headless mode (enabled 22:13 16/7/2024 - for performance stats)
        # options.add_argument("--headless")
        # options.add_argument("--no-sandbox")  # Required for some environments
        # options.add_argument("--disable-browser-side-navigation")
        # # options.add_argument('--blink-settings=imagesEnabled=false')  # Disable loading images. Causes problems with LinkedIn
        return options

    # @profile
    def start_linkedin(self, username, password) -> None:
        log.info("Logging in.....Please wait :)  ")
        self.load_page_and_wait_until_it_stops_loading(
            "https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin"
        )

        try:
            user_field = self.browser.find_element("id", "username")
            pw_field = self.browser.find_element("id", "password")
            login_button = self.browser.find_element(
                By.XPATH, "//button[@data-litms-control-urn='login-submit']"
            )
            user_field.send_keys(username)
            pw_field.send_keys(password)
            # Wait for the link to be clickable and then click it
            WebDriverWait(self.browser, 10, poll_frequency=0.2).until(
                EC.element_to_be_clickable(login_button)
            )
            login_button.click()
            # time.sleep(3)
        except TimeoutException:
            log.info(
                "TimeoutException! Username/password field or login button not found"
            )
            log.exception("An error occurred:")

        if "verification" in self.browser.title.lower():
            winsound.PlaySound(r"C:\Windows\Media\chimes.wav", winsound.SND_FILENAME)
            input(
                "Press Enter to continue..."
            )  # pause the script in case of captcha type verification
            log.debug("captcha verification needed")

    def combos_output_log_read_in(self) -> tuple:
        df = pd.read_csv(
            filepath_or_buffer=self.csv_combo_log_file,
            names=["Date", "Combo"],
            parse_dates=["Date"],
            # date_parser=lambda x: pd.to_datetime(x, format="%d/%m/%Y %H:%M"),
            converters={"Date": lambda x: pd.to_datetime(x, format="%d/%m/%Y %H:%M")},
        )

        # Calculate the timestamp 48 hours ago from the current date and time
        forty_eight_hours_ago = datetime.now() - timedelta(hours=48)

        # Filter rows based on timestamp within the last 48 hours
        filtered_df = df[df["Date"] > forty_eight_hours_ago]

        # Extract the 'Combo' values into a list of tuples
        combos_within_last_48_hours = list(filtered_df["Combo"])
        combos_within_last_48_hours = [
            tuple(ast.literal_eval(combo)) for combo in combos_within_last_48_hours
        ]

        # Now convert the list of tuples to a tuple
        combos_within_last_48_hours = tuple(combos_within_last_48_hours)

        return combos_within_last_48_hours

    def first_execution_driver_options_setup(self, username, password) -> None:
        driver = webdriver.Chrome(
            options=self.browser_options(), service=service
        )  # this will launch the browser, so if you want to delay that step move it, but then you will need to pass it somehow, and be defined globally, not locally inside a function

        # Enable the Network domain to block URLs
        driver.execute_cdp_cmd("Network.enable", {})

        # Block requests from 'media.licdn.com' which is only pics (profile and compnay logos)
        driver.execute_cdp_cmd(
            "Network.setBlockedURLs",
            {
                "urls": [
                    "*://media.licdn.com/*",
                    "*://www.linkedin.com/sensorCollect/?action=reportMetrics",
                ]
            },
        )

        self.browser = driver
        self.wait = WebDriverWait(self.browser, 45)
        self.start_linkedin(username, password)

    def log_combo_progress(
        self,
        combos,
        positions_param,
        locations_param,
        position,
        location,
        combos_within_last_48_hours,
    ) -> None:
        log.debug(
            "Number of job/location combos already applied to: %d",
            len(combos),
        )
        log.debug(
            "All possible job/location combos given the config.yaml file: %d",
            len(positions_param) * len(locations_param),
        )
        log.debug(
            "Remaining job/location combos to apply to: %d",
            (len(positions_param) * len(locations_param)) - len(combos),
        )
        log.info("Applying to %s: %s", position, location)

    def append_combo_to_csv(self, combo) -> None:
        # Open the CSV file in append mode with the specified encoding and line terminator
        # TODO: that would work well as an async/with threading/as a separate function
        with open(
            self.csv_combo_log_file,
            mode="a",
            encoding="Windows-1252",
            newline=None,
        ) as file:
            writer = csv.writer(file)

            # Get the current date and time in the desired format
            current_datetime = datetime.now().strftime("%d/%m/%Y %H:%M")

            # Log the combo along with the current date and time to the CSV file
            writer.writerow([current_datetime, combo])

    # @profile
    def start_apply(self, positions_param, locations_param, username, password) -> None:
        combos_within_last_48_hours = self.combos_output_log_read_in()

        executing_for_the_first_time: bool = True

        combos: list = []
        for location in locations_param:
            for position in positions_param:
                combo: tuple = (position, location)
                combos.append(combo)
                if combo not in combos_within_last_48_hours:
                    # so if here and this is executing for the first time, only then it should open up and long into the linkedin
                    if executing_for_the_first_time:
                        self.first_execution_driver_options_setup(username, password)
                        executing_for_the_first_time = False

                    self.log_combo_progress(
                        combo,
                        positions_param,
                        locations_param,
                        position,
                        location,
                        combos_within_last_48_hours,
                    )

                    self.jobs_applications_loop_for_a_single_combo(
                        position, "&location=" + location
                    )

                    self.append_combo_to_csv(combo)

    # @profile
    def get_job_links(self) -> list:
        container = self.browser.find_element(
            "css selector",
            "#main > div > div.scaffold-layout__list-detail-inner.scaffold-layout__list-detail-inner--grow > div.scaffold-layout__list > div > ul",
        )
        # get job links, (the following are actually the job card objects)
        return container.find_elements(
            By.XPATH,
            './/div[@data-job-id and .//text()[contains(., "Easy Apply")]]',
        )

    # @profile
    def get_number_of_results_on_page(self, element) -> int:
        text = element.text

        # Remove " results" or " result" from the text
        if " results" in text:
            text = text.replace(" results", "").replace(",", "")
        elif " result" in text:
            text = text.replace(" result", "").replace(",", "")

        # Convert the cleaned text to a number
        return int(text)

    def iterate_links(
        self, links, IDs: dict
    ) -> None:  # dict is a reference, not a copy
        # children selector is the container of the job cards on the left
        for link in links:
            jobID: int = 0

            temp = link.get_attribute(
                "data-job-id"
            )  # [:10]  # Limit job ID to 10 characters
            if temp == "search":
                continue  # moving onto the next link
            if temp is not None:
                jobID = int(temp)

            if (
                jobID not in self.applied_job_IDs
            ):  # be careful if they are both of the same type - string, mixed types won't work. Now it works.
                self.applied_job_IDs.add(jobID)
                # Extract what is needed (once they changed this on their end..., and you needed to change [1] to [2])
                lines = link.text.lower().split("\n")

                # Use try-except to handle any index issues with the lines
                try:
                    input_text_job_title = lines[0]
                    input_text_company_title = lines[2]
                except IndexError:
                    log.exception("An error occurred:")
                    continue

                if not (
                    any(phrase in input_text_job_title for phrase in self.black_list_titles)
                    or any(phrase in input_text_company_title for phrase in self.blacklist)
                ):
                    # Symmetric Difference (symmetric_difference):
                    # Returns a new set containing elements that are present in either of the sets, but not in both. DON'T DO IT, union in this case is an equivalent. Symetric difference cannot handle strings, union can
                    # IDs.add(jobID)
                    IDs[jobID] = (
                        link,
                        input_text_job_title,
                        input_text_company_title,
                    )

    # @profile
    def jobs_applications_loop_for_a_single_combo(self, position, location):
        count_application = 0
        count_job = 0
        jobs_per_page = 0
        input_text_job_title = ""
        input_text_company_title = ""

        self.next_jobs_page(position, location, jobs_per_page)

        log.info("Looking for jobs.. Please wait..")

        has_numerical_fields_been_auto_filled: bool = False
        while True:
            # exit this combo if the page contains "No matching jobs found." as it will have some jobs listed, but those are "Jobs you may be interested in" which are not very relevant location wise
            if "No matching jobs found" in self.browser.page_source:
                log.debug("No matching jobs found. Moving onto next job/location combo")
                return
            try:
                links = self.get_job_links()  # those are just links, unfiltered
                if len(links) == 0:
                    log.error("No links found. This shouldn't really happen")
                    return  # onto next combo
                # we have some links
                # if first one of them is over 1 week old, then skip this job/location combo, and move to the next one # TODO: would be beneficial to add this to config.yaml as an option
                # raw links[0].text is like 'Senior QA Automation Engineer\nSenior QA Automation Engineer\nWeDo \nUnited Kingdom (Remote)\n£70K/yr - £75K/yr\nActively recruiting\n3 days ago\nEasy Apply'
                first_link_text = links[0].text.split("\n")[-2]
                if any(
                    phrase in first_link_text
                    for phrase in [
                        "week ago",
                        "6 days ago",
                        # "5 days ago",
                        # "4 days ago",
                        # "3 days ago",
                        # "2 days ago",
                        # "weeks ago",
                        # "month ago",
                        # "months ago"
                    ]
                ):
                    log.debug(
                        "moving onto the next combo, due to no new jobs available to apply to for this combo"
                    )
                    return  # this skips this job/location combo

                last_link_text = links[
                    -1
                ].text  # don't put this further down, as you will then get StaleElementReferenceException(). Also don't do last_link = links[-1] as that would be reference assignment only, and not hold a copy

                IDs = {}
                # dictionary on purpose, as they won't be repeating themselves, and pairs of values are required

                self.iterate_links(links, IDs)

                log.info(
                    "it found this many job IDs with EasyApply button: %s",
                    len(links),
                )

                log.info(
                    "it found this many job IDs with EasyApply button and not containing any blacklisted phrases, as well as filtration of already applied to jobs: %s",
                    len(IDs),
                )

                # assumes it didn't find any suitable job, moving onto the next page
                if not IDs:
                    jobs_per_page = jobs_per_page + 25

                    # if jobs_per_page is <= than "results" then abandon, and move on to the next combo
                    # Locate the element and get the text
                    try:
                        element = self.browser.find_element(
                            By.XPATH,
                            '//*[@id="main"]/div/div[2]/div[1]/header/div[1]/small/div/span',
                        )
                    except NoSuchElementException:
                        log.exception("An error occurred:")
                        self.browser.refresh()
                        element = self.wait.until(
                            EC.presence_of_element_located(
                                (
                                    By.XPATH,
                                    '//*[@id="main"]/div/div[2]/div[1]/header/div[1]/small/div/span',
                                )
                            )
                        )
                    number_of_results_on_page = self.get_number_of_results_on_page(
                        element
                    )

                    if jobs_per_page >= number_of_results_on_page:
                        # it would return to move onto the next combo
                        return

                    count_job = 0
                    self.next_jobs_page(position, location, jobs_per_page)
                else:
                    # here it should just start applying since it's still on the right page and has IDs which passed filtration

                    # loop over IDs to apply
                    # although _ doesn't seem used, don't delete it. It's there for a reason
                    # for _, jobID in enumerate(IDs):
                    for jobID, values in IDs.items():
                        count_job += 1
                        link, input_text_job_title, input_text_company_title = values

                        try:
                            # Wait for the dismiss button to be clickable and click it
                            dismiss_button = WebDriverWait(
                                self.browser, 5, poll_frequency=0.2
                            ).until(
                                EC.element_to_be_clickable(
                                    (
                                        By.XPATH,
                                        "//button[@aria-label='Dismiss']",
                                    )
                                )
                            )
                            dismiss_button.click()
                        except (NoSuchElementException, TimeoutException):
                            log.exception("An error occurred:")
                        try:
                            # Wait for the discard button to be clickable and click it
                            discard_button = WebDriverWait(
                                self.browser, 5, poll_frequency=0.2
                            ).until(
                                EC.element_to_be_clickable(
                                    (
                                        By.XPATH,
                                        "//button[@data-control-name='discard_application_confirm_btn']",
                                    )
                                )
                            )
                            discard_button.click()
                        except (NoSuchElementException, TimeoutException):
                            log.exception("An error occurred:")

                        time.sleep(random.uniform(1.5, 2.5))
                        link.click()
                        try:
                            # Wait for the link to be clickable and then click it
                            WebDriverWait(self.browser, 10, poll_frequency=0.2).until(
                                EC.element_to_be_clickable(link)
                            )
                            link.click()
                        except (NoSuchElementException, TimeoutException):
                            log.exception("An error occurred:")

                        # get easy apply button
                        easy_apply_button = self.get_easy_apply_button()

                        exit_bool = False

                        if easy_apply_button is not False:
                            log.info("Clicking the EASY apply button")

                            while True:
                                try:
                                    if easy_apply_button and easy_apply_button.is_enabled():

                                        try:
                                            # Wait for the link to be clickable and then click it
                                            WebDriverWait(
                                                self.browser, 10, poll_frequency=0.2
                                            ).until(
                                                EC.element_to_be_clickable(
                                                    easy_apply_button
                                                )
                                            )
                                            easy_apply_button.click()
                                        except (
                                            NoSuchElementException,
                                            TimeoutException,
                                        ):
                                            log.exception("An error occurred:")
                                        try:
                                            # Wait for the <h2> element to become visible
                                            WebDriverWait(self.browser, 20).until(
                                                EC.visibility_of_element_located(
                                                    (By.ID, "jobs-apply-header")
                                                )
                                            )
                                            log.info(
                                                "Element is visible. Clicking Easy Apply button successful."
                                            )
                                            break  # exit the While loop if the element is visible
                                        except Exception:
                                            log.exception("An error occurred:")
                                            dismiss_button = WebDriverWait(
                                                self.browser, 5, poll_frequency=0.2
                                            ).until(
                                                EC.element_to_be_clickable(
                                                    (
                                                        By.XPATH,
                                                        "//button[@aria-label='Dismiss']",
                                                    )
                                                )
                                            )
                                            dismiss_button.click()
                                            time.sleep(random.uniform(1.5, 2.5))
                                            exit_bool = True
                                            break
                                    else:
                                        self.check_if_daily_application_limit_exceeded()

                                except StaleElementReferenceException:
                                    log.exception("An error occurred:")
                                    # If the element is stale, try to find it again
                                    easy_apply_button = self.get_easy_apply_button()
                                    continue

                            if exit_bool:
                                break

                            result, has_numerical_fields_been_auto_filled = (
                                self.send_resume()
                            )
                            count_application += 1
                        else:
                            log.info("The button does not exist.")
                            # TODO: job ID should be added to applied to, to avoid it being openend again, dones already, but keep this here, as it's another way know where to insert that
                            result = False

                        self.write_to_file(
                            easy_apply_button,
                            jobID,
                            input_text_job_title,
                            input_text_company_title,
                            result,
                            has_numerical_fields_been_auto_filled,
                        )

                    # go to new page if all jobs are done
                    # TODO: you should not go to the next page, if there will be no next page

                    # return right here in case last job was old, this will save another reload, and just speed thing up in general. If it matches, do a return statement, which will move onto the next job/location combo
                    if any(
                        phrase in last_link_text
                        for phrase in [
                            "week ago",
                            "6 days ago",
                            # "5 days ago",
                            # "4 days ago",
                            # "3 days ago",
                            # "2 days ago",
                            # "weeks ago",
                            # "month ago",
                            # "months ago"
                        ]
                    ):
                        log.debug(
                            "moving onto the next combo, due to no new jobs available to apply to for this combo"
                        )
                        return  # this skips this job/location combo
                    jobs_per_page = jobs_per_page + 25
                    count_job = 0
                    log.info(
                        """****************************************\n\n
                    Going to next jobs page.
                    ****************************************\n\n"""
                    )
                    self.next_jobs_page(position, location, jobs_per_page)
            except Exception:
                log.exception("An error occurred:")

    # @profile
    def write_to_file(
        self, button, jobID, job, company, result, has_numerical_fields_been_autofilled
    ) -> None:
        # TODO: that would work well as an async/with threading
        timestamp: str = datetime.now().strftime("%d/%m/%Y %H:%M")
        attempted: bool = not button

        toWrite: list = [
            timestamp,
            jobID,
            job,
            company,
            attempted,
            result,
            has_numerical_fields_been_autofilled,
        ]

        # Remove Unicode characters from string elements
        toWrite = [
            (
                str(item).encode("ascii", "ignore").decode("ascii")
                if isinstance(item, str)
                else item
            )
            for item in toWrite
        ]

        with open(self.filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(toWrite)

    def check_if_daily_application_limit_exceeded(self):
        try:
            daily_applications_exceeded_element = self.browser.find_element(
                By.CLASS_NAME, "artdeco-inline-feedback--error"
            )
            if daily_applications_exceeded_element.text in [
                "You’ve reached the Easy Apply application limit for today. Save this job and come back tomorrow to continue applying."
            ]:
                log.debug(
                    "You reached the Easy Apply application limit for today. Exiting the app..."
                )
                # Get the PID of the process with "cmd.exe" and "easyapplybot.py" in its name.
                if process_id is not None:
                    terminate_process(process_id)
                    sys.exit()  # just incase if running from the VSC
                else:
                    sys.exit()  # just incase if running from the VSC
        except NoSuchElementException:
            log.exception("An error occurred:")

    # @profile
    def get_easy_apply_button(self):
        # self.check_if_daily_application_limit_exceeded()

        xpath_condition: str = (
            "//*[contains(., 'Job search safety reminder')] | "
            "//*[contains(text(), 'Something went wrong')] | "
            "//*[contains(., 'No longer accepting applications')]"
        )  # | is OR in xpath

        easy_apply_button = False
        while True:
            try:
                if self.browser.find_elements(By.XPATH, xpath_condition):
                    break

                # Wait for the Easy Apply button to appear
                self.wait.until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, '//button[contains(@class, "jobs-apply-button")]')
                    )
                )

                # Find and assign the Easy Apply button
                button = self.browser.find_element(
                    By.XPATH, '//button[contains(@class, "jobs-apply-button")]'
                )
                easy_apply_button = button
                if easy_apply_button:
                    break  # Exit the loop if the button is found successfully

            except IndexError:
                log.exception("An error occurred:")
                # Handles rare cases where the button is not found
                log.info("Button not found. Waiting for 2 seconds and trying again...")
                time.sleep(2)
                break

            except Exception as e:
                log.exception("An error occurred:")
                break

        return easy_apply_button

    # @profile
    def is_present(self, button_locator) -> bool:
        return len(self.browser.find_elements(button_locator[0], button_locator[1])) > 0

    # @profile
    def check_if_phone_number_is_present_and_fill(
        self, phone_number_input_field
    ) -> None:
        if self.is_present(phone_number_input_field):
            elements = self.browser.find_elements(
                By.XPATH,
                '//*[contains(@aria-describedby, "phoneNumber-nationalNumber")]',
            )
            element = elements[0]
            current_text = element.get_attribute("value")
            if not current_text:
                element.send_keys(self.phone_number)
                time.sleep(random.uniform(1.5, 2.5))

    def fill_numerical_fields(self) -> bool:
        """
        Finds numerical input fields, checks if they're empty, and fills them with 99 if so.
        """
        _hasNumericalFieldsBeenAutoFilled: bool = False

        try:
            # Locate numerical input fields (adjust the selector if needed)
            numerical_fields = self.browser.find_elements(
                By.CSS_SELECTOR,
                "input[id^='single-line-text-form-component-formElement'][id$='-numeric'][required]",
            )  # Include type='number' too

            for field in numerical_fields:
                # Check if the field is empty (considering whitespace)
                value = field.get_attribute("value")
                if value is None or not value.strip():
                    field.clear()  # Ensure the field is clear, even if there's whitespace
                    field.send_keys("99")
                    log.debug(
                        "Filled numerical field with 99: %s",
                        field.get_attribute("id"),
                    )
                    _hasNumericalFieldsBeenAutoFilled = True
                else:
                    log.debug(
                        "Numerical field already has a value: %s",
                        field.get_attribute("id"),
                    )  # For debugging or monitoring

        except Exception as e:
            log.exception("An error occurred:")

        return _hasNumericalFieldsBeenAutoFilled

    # @profile
    def click_and_navigate(
        self, question_flag, question_xpath, delay_after_click=1, delay_after_tab=1
    ) -> bool:
        if not question_flag and self.is_present((By.XPATH, question_xpath)):
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
            if (
                question_xpath
                == "//span[contains(text(), 'Will you now or in the future require sponsorship for employment visa status?')]"
            ):
                actions.send_keys(Keys.ARROW_DOWN).perform()
                time.sleep(delay_after_click)

        return question_flag

    def enumerate_over_buttons(self, buttons) -> bool:
        for i, button_locator in enumerate(buttons):
            # Define a list of XPaths to check
            xpath_checks = [
                "//*[@class='artdeco-button__text'][contains(text(), 'Done')]",
                "//*[contains(., 'Your application was sent to')]",
                "//*[contains(., 'You can keep track of your application in the \"Applied\" tab of My Jobs')]",
            ]

            # Check if any of the elements are found
            submitted = any(
                self.browser.find_elements(By.XPATH, xpath) for xpath in xpath_checks
            )

            # If any checks are true, set submitted to True and break
            if submitted:
                return True

            if self.browser.find_elements(
                By.XPATH, "//*[contains(., 'Job search safety reminder')]"
            ):
                return False

            if self.browser.find_elements(
                By.XPATH, "//*[contains(., 'Wie gut beherrschen Sie Deutsch')]"
            ):
                return False

            button_found_from_enumeration: Optional[WebElement] = None

            if self.is_present(button_locator):
                button_found_from_enumeration: Optional[WebElement] = self.wait.until(
                    EC.element_to_be_clickable(button_locator)
                )

            if button_found_from_enumeration:
                # click it
                button_found_from_enumeration.click()

                time.sleep(2)
                if i in (3, 4):
                    return True
                if i != 2:
                    return False

        return False

    # @profile
    def send_resume(self) -> tuple[bool, bool]:
        have_numerical_fields_been_auto_filled: bool = False
        submitted: bool = False

        button: Optional[WebElement] = None

        question_elements: dict[str, bool] = {
            "//span[contains(text(), 'Will you now or in the future require sponsorship for employment visa status?')]": False,
            "//span[contains(text(), 'Are you authorized to work in the ')]": False,
            "//span[contains(text(), 'Are you comfortable commuting to this ')]": False,
            "//span[contains(text(), 'Are you comfortable working in a hybrid setting?')]": False,
            "//span[contains(text(), 'Are you comfortable working in an onsite setting?')]": False,
            "//span[contains(text(), 'Have you completed the following level of education: ')]": False,
            "//span[contains(text(), 'We must fill this position urgently. Can you start immediately?')]": False,
            "//span[contains(text(), 'Do you have the right to work in the UK without a VISA or sponsorship?')]": False,
            "//span[contains(text(), 'Do you live in the United Kingdom?')]": False,
            "//span[contains(text(), 'Are you comfortable working in a remote setting?')]": False,
        }

        next_locater = (
            By.CSS_SELECTOR,
            "button[aria-label='Continue to next step']",
        )
        review_locater = (
            By.CSS_SELECTOR,
            "button[aria-label='Review your application']",
        )
        submit_application_locator = (
            By.CSS_SELECTOR,
            "button[aria-label='Submit application']",
        )
        term_agree = (
            By.CSS_SELECTOR,
            "label[data-test-text-selectable-option__label='I Agree Terms & Conditions']",
        )
        cancel_button = (
            By.XPATH,
            "//span[contains(@class, 'artdeco-button__text') and normalize-space(text())='Cancel']",
        )
        phone_number_input_field = (
            By.XPATH,
            '//*[contains(@aria-describedby, "phoneNumber-nationalNumber")]',
        )

        # Click Next or submitt button if possible
        buttons: list = [
            next_locater,
            review_locater,
            submit_application_locator,
        ]

        self.check_if_phone_number_is_present_and_fill(phone_number_input_field)

        self.fill_numerical_fields()

        try:
            while True:
                if submitted:
                    break

                if self.browser.find_elements(
                    By.XPATH, "//*[contains(., 'Job search safety reminder')]"
                ):
                    break

                for item in {term_agree, cancel_button}:
                    if self.is_present(item):
                        if button := self.wait.until(EC.element_to_be_clickable(item)):
                            button.click()
                        time.sleep(2)

                for xpath in question_elements:
                    question_elements[xpath] = self.click_and_navigate(
                        question_elements[xpath], xpath  # send state  # send question
                    )

                have_numerical_fields_been_auto_filled: bool = (
                    self.fill_numerical_fields()
                )

                submitted = self.enumerate_over_buttons(buttons)

                if self.browser.find_elements(
                    By.XPATH, "//li-icon[@type='error-pebble-icon']"
                ):
                    # it would be good here to bring forward the window, or pause to fill it by hand #breakpoint, as that's where the unfilled field in underlined in red
                    break

        except Exception:
            log.exception("An error occurred:")
            log.info("cannot apply to this job")

        if submitted:
            self.num_successful_jobs_global_variable += 1
            log.info(
                "Application Submitted. Today you have applied to %d jobs",
                self.num_successful_jobs_global_variable,
            )
        time.sleep(2)

        return submitted, have_numerical_fields_been_auto_filled

    def get_scroll_count(self, element, position):
        number_of_results_on_page = self.get_number_of_results_on_page(element)

        return (
            min(25, number_of_results_on_page - position)
            if number_of_results_on_page > position + 25
            else number_of_results_on_page - position
        )

    # @profile
    def load_page(self, position) -> None:
        self.wait.until(
            lambda driver: self.browser.execute_script("return document.readyState")
            == "complete"
        )

        if "No matching jobs found" in self.browser.page_source:
            return

        try:
            scrollresults = self.browser.find_element(
                By.CLASS_NAME, "jobs-search-results-list"
            )
        except NoSuchElementException:
            log.exception("An error occurred:")
            self.browser.refresh()
            scrollresults = self.wait.until(
                EC.presence_of_element_located(
                    (By.CLASS_NAME, "jobs-search-results-list")
                )
            )

        # Locate the element and get the text
        try:
            element = self.browser.find_element(
                By.XPATH,
                '//*[@id="main"]/div/div[2]/div[1]/header/div[1]/small/div/span',
            )
        except NoSuchElementException:
            log.exception("An error occurred:")
            self.browser.refresh()
            element = self.wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//*[@id="main"]/div/div[2]/div[1]/header/div[1]/small/div/span',
                    )
                )
            )

        scroll_count = self.get_scroll_count(element, position)

        # Scroll only if there are more than 2 results
        if scroll_count > 2:
            for i in range(300, scroll_count * 150, 150):
                self.browser.execute_script(
                    "arguments[0].scrollTo(0, {})".format(i), scrollresults
                )
                time.sleep(0.3)  # Adjust the speed of scrolling

    def scroll_to_every_third_job(self):
        job_elements = self.browser.find_elements(
            By.CLASS_NAME, "scaffold-layout__list-item"
        )

        for i in range(0, len(job_elements), 3):
            if job_element := job_elements[i]:
                # Option 1: Direct scrollIntoView (may be inconsistent)
                self.browser.execute_script(
                    "arguments[0].scrollIntoView({ behavior: 'smooth' });",
                    job_element,
                )

                # # Option 2: Scroll to element's location (more reliable)
                # y_offset = job_element.location['y']
                # self.browser.execute_script(f"window.scrollTo(0, {y_offset});")

                time.sleep(1)  # Wait for 1 second

    # @profile
    def next_jobs_page(self, position, location, jobs_per_page):
        # "&f_AL=true" makes sure only easy apply jobs appear
        # "&sortBy=DD" sorts by the most recent
        job_url = f"https://www.linkedin.com/jobs/search/?f_LF=f_AL&keywords={position}{location}&sortBy=DD&start={jobs_per_page}&origin=JOBS_HOME_SEARCH_BUTTON&refresh=true"

        # Load the page and scroll the left pane with job results
        self.load_page_and_wait_until_it_stops_loading(job_url)

        if "No matching jobs found" in self.browser.page_source:
            return  # this will return to then do next combo

        while True:  # Keep trying until no placeholders are found
            self.wait.until(
                lambda driver: self.browser.execute_script("return document.readyState")
                == "complete"
            )  # Wait for full page load initially

            placeholder_elements = self.browser.find_elements(
                By.CLASS_NAME, "job-card-container__ghost-placeholder"
            )
            if not placeholder_elements:
                break

            log.debug("Placeholders found. Reloading page...")
            self.browser.refresh()
            time.sleep(5)  # Increased wait time after reload (adjust as needed)

        self.scroll_to_every_third_job()

    # @profile
    def load_page_and_wait_until_it_stops_loading(self, job_url):
        self.browser.get(job_url)
        self.wait.until(
            lambda driver: self.browser.execute_script("return document.readyState")
            == "complete"
        )
        # Page is now fully loaded and ready to be interacted with


if __name__ == "__main__":
    with open("config.yaml", "r", encoding="utf-8") as stream:
        try:
            parameters = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            log.exception("An error occurred:")
            raise exc

    del stream

    assert len(parameters["positions"]) > 0
    assert len(parameters["locations"]) > 0
    assert parameters["username"] is not None
    assert parameters["password"] is not None
    assert parameters["phoneNumber"] is not None

    log.info(
        {
            k: parameters[k]
            for k in parameters.keys()
            if k not in ["username", "password"]
        }
    )

    output_filename: str = next(
        (f for f in parameters.get("output_filename", ["output.csv"]) if f is not None),
        "output.csv",
    )
    blacklist = {
        phrase.lower() for phrase in parameters.get("blacklist", {})
    }  # set comprehension
    black_list_titles = {
        phrase.lower() for phrase in parameters.get("blackListTitles", {})
    }

    bot = EasyApplyBot(
        parameters["phoneNumber"],
        filename=output_filename,
        blacklist_param=blacklist,
        blacklist_titles_param=black_list_titles,
    )

    locations: list = [l for l in parameters["locations"] if l is not None]
    positions: list = [p for p in parameters["positions"] if p is not None]
    bot.start_apply(
        positions,
        locations,
        username=parameters["username"],
        password=parameters["password"],
    )

    del parameters

    log.debug(
        "controlled exit due to all job/location combos being processed successfully"
    )
    # Get the PID of the process with "cmd.exe" and "easyapplybot.py" in its name.
    if process_id is not None:
        terminate_process(process_id)
    sys.exit()  # just incase if running from the VSC, defensive programming.

# make it run headless unless last login attempt lead to captcha, as a setting in the config.yaml

# TODO: searching for jobs should happen in parrarel, in other tab, as you're applying to jobs in another tab, to make applying to jobs faster

# TODO: compare with the LineProfiler, how much faster a headless version would be.

# handle it in a specific way, but for other problems, do a timer/count number of tries, then first refresh, and if that fails, move onto the next job

# if "Tunnel Connection Failed" refresh the website

# right now, you're assesing how many applications applied to by one way of counting. Make sure for the script to be able to also pick up on other ways when for example easyapply button becomes grayed out due to applying to over 250 jobs/day. In those cases the script should exit both loops

# looking if first job is not "weeks" old, should be done before even scrolling down, and if so, move to the next combo, although that will require serious reorganization of the code, and the current code works well, it's just that sub functionality could be improved to gain a few seconds if the combo is early discarded
