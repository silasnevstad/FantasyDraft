from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd

# Set up the Selenium WebDriver (Chrome in headless mode)
options = webdriver.ChromeOptions()
# options.add_argument('--headless')  # Run in headless mode
driver = webdriver.Chrome(options=options)

# Replace with the actual URL
url = 'https://fantasy.espn.com/basketball/players/projections?leagueFormatId=2'
driver.get(url)

# Wait object
wait = WebDriverWait(driver, 10)

# Press this button first: "Button Button--filter player--filters__projections-button"
button = wait.until(EC.element_to_be_clickable(
    (By.CSS_SELECTOR, 'button.Button.Button--filter.player--filters__projections-button')))
button.click()

# List to hold all scraped data
all_data = []

for page_number in range(1, 22):  # Pages 1 to 21
    print(f"Scraping page {page_number}...")

    # Wait until the tables are present
    try:
        players_table = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'table.Table.Table--align-right.Table--fixed.Table--fixed-left')))
        stats_table = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'table.Table.Table--align-right:not(.Table--fixed)')))
        fantasy_table = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'table.Table.Table--align-right.Table--fixed.Table--fixed-right')))
    except Exception as e:
        print(f"Error locating tables on page {page_number}: {e}")
        break

    # Extract data from the players table
    players_rows = players_table.find_elements(By.CSS_SELECTOR, 'tbody tr')
    stats_rows = stats_table.find_elements(By.CSS_SELECTOR, 'tbody tr')
    fantasy_rows = fantasy_table.find_elements(By.CSS_SELECTOR, 'tbody tr')

    # Ensure all tables have the same number of rows
    num_rows = min(len(players_rows), len(stats_rows), len(fantasy_rows))

    for i in range(num_rows):
        # Extract cells from each row
        player_cells = players_rows[i].find_elements(By.TAG_NAME, 'td')
        stats_cells = stats_rows[i].find_elements(By.TAG_NAME, 'td')
        fantasy_cells = fantasy_rows[i].find_elements(By.TAG_NAME, 'td')

        # Extract text from each cell
        player_data = [cell.text for cell in player_cells]
        stats_data = [cell.text for cell in stats_cells]
        fantasy_data = [cell.text for cell in fantasy_cells]

        # Combine data from all tables
        combined_data = player_data + stats_data + fantasy_data
        all_data.append(combined_data)

    # Click the "Next" button if not on the last page
    if page_number < 21:
        try:
            next_button = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'button.Pagination__Button--next')))
            next_button.click()
            time.sleep(2)  # Wait for the page to load
        except Exception as e:
            print(f"Failed to click 'Next' on page {page_number}: {e}")
            break

# Close the WebDriver
driver.quit()

# Convert the data to a DataFrame and save to CSV
df = pd.DataFrame(all_data)
df.to_csv('players_data.csv', index=False)
print("Data saved to players_data.csv")
