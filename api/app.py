from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

# --- Basic Flask App Setup ---
app = Flask(__name__)
# Enable CORS to allow requests from your HTML file
CORS(app)

def scrape_panchang_for_day(date_obj, location_str):
    """
    Scrapes drikpanchang.com for a single day's panchang details.

    Args:
        date_obj: A datetime.date object for the desired day.
        location_str: The location string (e.g., "New Delhi, India").

    Returns:
        A dictionary containing the scraped panchang data, or None if scraping fails.
    """
    # Format the date into DD/MM/YYYY for the URL
    date_str_for_url = date_obj.strftime('%d/%m/%Y')
    
    # --- IMPORTANT NOTE ON LOCATION ---
    # Drik Panchang's location handling is complex. For this code to work reliably,
    # we are using a simplified method. A full implementation would require a 
    # more advanced setup to find the correct city ID for every possible location.
    # We will use a geoname-id for New Delhi as a default for this example.
    # The user's location input is received but not fully used in this simplified version.
    geoname_id = "1261481" # This is the ID for New Delhi, India
    
    url = f"https://www.drikpanchang.com/panchang/day-panchang.html?geoname-id={geoname_id}&date={date_str_for_url}"
    
    print(f"Attempting to scrape URL: {url}")

    try:
        # We must send a 'User-Agent' header to mimic a real browser visit
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        # This line will raise an error if the website couldn't be reached (e.g., 404 Not Found)
        response.raise_for_status()

        # Use BeautifulSoup to parse the HTML content of the page
        soup = BeautifulSoup(response.text, 'html.parser')

        # --- Finding the Data ---
        # We find the main table containing the panchang details.
        # NOTE: These selectors are based on the website's structure as of July 2025.
        # If the website changes its design, these selectors will need to be updated.
        panchang_table = soup.find('div', class_='dpPanchang')
        
        if not panchang_table:
            print(f"Could not find the main panchang table on the page for {date_str_for_url}.")
            return None

        # The data is in rows. We find all rows.
        rows = panchang_table.find_all(class_='dpRow')
        
        data = {'date': date_obj.strftime('%Y-%m-%d')}
        
        # A helper function to safely get text from a row
        def get_value_from_row(row_name):
            for row in rows:
                label_element = row.find(class_='dpLabel')
                if label_element and row_name in label_element.text:
                    value_element = row.find(class_='dpValue')
                    return value_element.text.strip() if value_element else "Not Found"
            return "Not Found"

        # Extract each piece of data
        data['sunrise'] = get_value_from_row('Sunrise')
        data['sunset'] = get_value_from_row('Sunset')
        data['tithi'] = get_value_from_row('Tithi')
        data['nakshatra'] = get_value_from_row('Nakshatra')
        data['yoga'] = get_value_from_row('Yoga')
        data['karana'] = get_value_from_row('Karana')

        return data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return None
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return None


@app.route('/panchang', methods=['GET'])
def get_panchang():
    """
    API endpoint that receives the request from the frontend,
    loops through dates, scrapes data for each, and returns the result.
    """
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    location = request.args.get('location')

    if not all([start_date_str, end_date_str, location]):
        return jsonify({"error": "Missing required parameters"}), 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    all_panchang_data = []
    current_date = start_date
    
    # Loop from the start date to the end date
    while current_date <= end_date:
        print(f"Scraping data for {current_date.strftime('%Y-%m-%d')}...")
        day_data = scrape_panchang_for_day(current_date, location)
        
        if day_data:
            all_panchang_data.append(day_data)
        else:
            # If scraping fails for one day, we can add an error entry
            all_panchang_data.append({
                "date": current_date.strftime('%Y-%m-%d'),
                "error": "Failed to retrieve data for this day."
            })
        
        # Move to the next day
        current_date += timedelta(days=1)

    return jsonify({"panchang": all_panchang_data})


# --- How to Run This Server ---
if __name__ == '__main__':
    # 1. Make sure you have Python installed on your computer.
    # 2. Open a terminal or command prompt.
    # 3. Install the necessary libraries by typing these commands and pressing Enter:
    #    pip install Flask Flask-CORS requests beautifulsoup4
    # 4. Save this code in a file named `app.py`.
    # 5. In your terminal, navigate to the folder where you saved the file.
    # 6. Run the server by typing this command and pressing Enter:
    #    python app.py
    # 7. The terminal will show that the server is running on http://127.0.0.1:5000.
    #    Leave this terminal window open!
    # 8. Now, you can open the HTML file in your browser, and it will be able to
    #    communicate with this backend server.
    app.run(debug=True)
