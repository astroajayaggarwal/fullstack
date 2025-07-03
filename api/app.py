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
    
    # Using a fixed geoname-id for New Delhi.
    # If you need to support other locations, you'd need a mechanism to find their geoname-id.
    geoname_id = "1261481" # This is the ID for New Delhi, India
    
    url = f"https://www.drikpanchang.com/panchang/day-panchang.html?geoname-id={geoname_id}&date={date_str_for_url}"
    
    print(f"Attempting to scrape URL: {url} for date {date_str_for_url}")

    try:
        # We must send a 'User-Agent' header to mimic a real browser visit
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

        # Use BeautifulSoup to parse the HTML content of the page
        soup = BeautifulSoup(response.text, 'html.parser')
        print(f"Successfully fetched HTML content for {date_str_for_url}. Response status: {response.status_code}")

        # --- Finding the Data ---
        # First, try to find the main panchang card using its primary class
        panchang_card = soup.find('div', class_='dpPanchangCard')
        
        # If dpPanchangCard is not found, log the received HTML snippet for debugging
        if not panchang_card:
            print(f"WARNING: 'div.dpPanchangCard' not found for {date_str_for_url}.")
            print(f"DEBUG: First 1000 characters of received HTML: {response.text[:1000]}") # Print snippet
            print(f"DEBUG: Total length of received HTML: {len(response.text)} bytes") # Print total length

            # Fallback: Try to find a div that contains the 'Sunrise' dpTableKey, and then its parent
            sunrise_key_element = soup.find('div', class_='dpTableKey', string='Sunrise')
            if sunrise_key_element:
                # Find the closest common ancestor that likely wraps all panchang data
                # We'll traverse up the parent chain until we find a div that contains at least 5 dpTableKey elements.
                current_parent = sunrise_key_element.find_parent('div')
                while current_parent:
                    if len(current_parent.find_all('div', class_='dpTableKey')) >= 5: # Assuming at least 5 keys (Sunrise, Sunset, Tithi, Nakshatra, Yoga, Karana)
                        panchang_card = current_parent
                        print(f"DEBUG: Fallback found a suitable parent div with multiple 'dpTableKey' elements. Using this as panchang_card.")
                        break
                    current_parent = current_parent.find_parent('div')
                
                if not panchang_card: # If loop finishes without finding a suitable parent
                    print(f"WARNING: Fallback could not find a parent div containing at least 5 'dpTableKey' elements for {date_str_for_url}.")
                    # As a last resort, use the direct parent of the sunrise key element
                    panchang_card = sunrise_key_element.find_parent('div')
                    print(f"DEBUG: Using direct parent of 'Sunrise' key as panchang_card as a last resort (may result in partial data).")
            else:
                print(f"ERROR: Could not find 'div.dpPanchangCard' and no 'div.dpTableKey' for 'Sunrise' found on the page for {date_str_for_url}. Website structure has likely changed significantly or content is missing.")
                return None

        if not panchang_card: # Final check after all attempts
            print(f"CRITICAL ERROR: Panchang card could not be identified for {date_str_for_day} after all attempts.")
            return None
        else:
            print(f"DEBUG: Panchang card identified. Attempting to extract data from it.")

        data = {'date': date_obj.strftime('%Y-%m-%d')}
        
        # Helper function to get value from the new table structure
        def get_value_from_table(key_name):
            try:
                # Find all potential key elements within the identified panchang_card
                key_elements = panchang_card.find_all('div', class_='dpTableKey')
                
                for key_element in key_elements:
                    # Check if the stripped text of the key element contains the key_name
                    # This makes it more robust against minor text variations (e.g., extra spaces, hidden characters)
                    if key_name.lower() in ' '.join(key_element.stripped_strings).strip().lower():
                        # The value is in the next sibling div with class 'dpTableValue'
                        value_element = key_element.find_next_sibling('div', class_='dpTableValue')
                        if value_element:
                            return ' '.join(value_element.stripped_strings).strip()
                        else:
                            print(f"WARNING: Could not find 'dpTableValue' sibling for key '{key_name}' (matched via '{' '.join(key_element.stripped_strings).strip()}') on {date_str_for_url}.")
                            return "Not Found" # Return Not Found if value element is missing
                
                print(f"WARNING: Could not find 'dpTableKey' element containing text '{key_name}' on {date_str_for_url}.")
            except Exception as e:
                print(f"ERROR: Exception while extracting '{key_name}' for {date_str_for_url}: {e}")
            return "Not Found"

        # Extract each piece of data using the new helper
        data['sunrise'] = get_value_from_table('Sunrise')
        data['sunset'] = get_value_from_table('Sunset')
        data['tithi'] = get_value_from_table('Tithi')
        data['nakshatra'] = get_value_from_table('Nakshatra')
        data['yoga'] = get_value_from_table('Yoga')
        data['karana'] = get_value_from_table('Karana')

        # If any of the main values are not found, it's a failure for that day's data
        if "Not Found" in [data['sunrise'], data['sunset'], data['tithi'], data['nakshatra'], data['yoga'], data['karana']]:
            print(f"WARNING: One or more core data points (Sunrise, Tithi, etc.) could not be found for {date_str_for_url}. Returning partial data.")
            # Return whatever was found, and let the frontend handle "Not Found" values
            return data 
        
        print(f"Successfully scraped data for {date_str_for_url}: {data}")
        return data

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed for URL {url}: {e}")
        return None
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during scraping for {date_str_for_url}: {e}")
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
        print("ERROR: Missing required parameters in request.")
        return jsonify({"error": "Missing required parameters (start_date, end_date, location)."}), 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        print(f"ERROR: Invalid date format received: start_date={start_date_str}, end_date={end_date_str}")
        return jsonify({"error": "Invalid date format. Use THAT-MM-DD."}), 400

    all_panchang_data = []
    current_date = start_date
      
    # Loop from the start date to the end date
    while current_date <= end_date:
        print(f"Processing data for {current_date.strftime('%Y-%m-%d')}...")
        day_data = scrape_panchang_for_day(current_date, location)
        
        if day_data:
            all_panchang_data.append(day_data)
        else:
            # If scraping fails for one day, we can add an error entry
            print(f"Failed to scrape data for {current_date.strftime('%Y-%m-%d')}. Adding error entry.")
            all_panchang_data.append({
                "date": current_date.strftime('%Y-%m-%d'),
                "error": "Failed to retrieve complete data for this day. Check backend logs for details."
            })
            
        # Move to the next day
        current_date += timedelta(days=1)

    print(f"Finished processing dates. Returning {len(all_panchang_data)} entries.")
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
