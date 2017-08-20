import os
import psycopg2
import requests
import time
from bs4 import BeautifulSoup
from constants import LOWEST_SCORE_MESSAGE, SCOREBOARD_URL, SIGNIN_URL
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from twilio.rest import Client
from urllib.parse import urlparse

client = Client(os.environ['TWILIO_ACCOUNT'], os.environ['TWILIO_TOKEN'])
url = urlparse(os.environ['DATABASE_URL'])
conn = psycopg2.connect(
    database=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)

def initiate_shame(league, year):
    # Specify the path to the Chrome binary
    chrome_options = Options()
    chrome_options.binary_location = os.environ['GOOGLE_CHROME']
    # Fire up Chrome and go to ESPN's signin page
    driver = webdriver.Chrome(chrome_options=chrome_options)
    driver.get(SIGNIN_URL)

    # Wait for the iframe with the signin form to appear
    WebDriverWait(driver, 1000).until(EC.presence_of_all_elements_located((By.XPATH,'(//iframe)')))
    frame = driver.find_element_by_id('disneyid-iframe')

    # Switch to the iframe
    driver.switch_to_frame(frame)
    time.sleep(2)

    # Fill in the form and submit it
    driver.find_element_by_xpath('(//input)[1]').send_keys(os.environ['ESPN_USERNAME'])
    driver.find_element_by_xpath('(//input)[2]').send_keys(os.environ['PASSWORD'])
    driver.find_element_by_class_name('btn-submit').click()
    driver.switch_to_default_content()
    time.sleep(4)

    # Create a `request` session and update it with the cookies from Selenium
    session = requests.session()
    for cookie in driver.get_cookies():
        c = {cookie['name']: cookie['value']}
        session.cookies.update(c)

    # Close Chrome
    driver.quit()

    # Get the Scoreboard URL page
    page = session.get(SCOREBOARD_URL.format(league=league, year=year))
    soup = BeautifulSoup(page.content, 'html.parser')

    # Select the matchup rows
    score_rows = soup.select('.matchup tr')

    # Create the scoring hash, e.g. {'name': 'John', 'score': 40}
    # Then, filter out any empty hashes
    scores = list(filter(lambda x: bool(x), map(score_hash, score_rows)))

    # Sort the scores from lowest to highest and grab the lowest
    sorted_scores = sorted(scores, key=lambda x: x['score'])
    lowest_scorer = sorted_scores[0]

    # Grab all the phone numbers from the DB
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM phone_numbers')
    records = cursor.fetchall()

    # Map over the results and just grab the phone number strings
    phone_numbers = list(map(lambda x: x[0], records))

    # Send a message to all of the phone numbers with the GoT "Shame" gif
    for number in phone_numbers:
        message = client.messages.create(
            to=number,
            from_=os.environ['TWILIO_PHONE_NUMBER'],
            media_url='https://media.giphy.com/media/vX9WcCiWwUF7G/giphy.gif',
            body=LOWEST_SCORE_MESSAGE.format(
                name=lowest_scorer['name'],
                score=lowest_scorer['score']
            )
        )

# If there isn't an "owner" in the row, then return an empty hash
def score_hash(row):
    if not bool(row.find(class_='owners')): return {}
    return {
        'name': row.find(class_='owners').get_text(),
        'score': float(row.find(class_='score').get_text())
    }
