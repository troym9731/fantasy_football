import os
import requests
import time
from bs4 import BeautifulSoup
from constants import SCOREBOARD_URL, SIGNIN_URL
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from twilio.rest import Client

client = Client(os.environ['TWILIO_ACCOUNT'], os.environ['TWILIO_TOKEN'])

def scrape(league, year):
    # Fire up Chrome and go to ESPN signin page
    driver = webdriver.Chrome()
    driver.get(SIGNIN_URL)

    # Wait for the iframe with the signin form to appear
    WebDriverWait(driver, 1000).until(EC.presence_of_all_elements_located((By.XPATH,'(//iframe)')))
    frame = driver.find_element_by_id('disneyid-iframe')

    # Switch to the iframe
    driver.switch_to_frame(frame)
    time.sleep(2)

    # Fill in the form and submit it
    driver.find_element_by_xpath('(//input)[1]').send_keys(os.environ['USERNAME'])
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

    page = session.get(SCOREBOARD_URL.format(league=league, year=year))
    soup = BeautifulSoup(page.content, 'html.parser')
    score_rows = soup.select('.matchup tr')
    scores = list(filter(lambda x: bool(x), map(score_hash, score_rows)))
    sorted_scores = sorted(scores, key=lambda x: x['score'])
    lowest_scorer = sorted_scores[0]
    body = 'The bottom feeder of the week is {name} with {score} points'

    message = client.messages.create(
        to='',
        from_='',
        media_url='https://media.giphy.com/media/vX9WcCiWwUF7G/giphy.gif',
        body=body.format(
            name=lowest_scorer['name'],
            score=lowest_scorer['score']
        )
    )

def score_hash(row):
    if not bool(row.find(class_='owners')): return {}
    return {
        'name': row.find(class_='owners').get_text(),
        'score': float(row.find(class_='score').get_text())
    }
