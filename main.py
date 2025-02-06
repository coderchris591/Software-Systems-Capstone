

from flask import Flask
import requests, my_secrets
import json

app = Flask(__name__)
            
    
headers = {
    "Host": my_secrets.host,
    "User-Agent": my_secrets.user_agent, 
    "Authorization-Key": my_secrets.auth_key  
}


@app.route("/")
def search():

    # Parameters for the API request
    # Keyword
    keywords = ""
    # PositionTitle
    position_title = ""
    # RemunerationMinimumAmount
    minimum_salary = ""
    # RemunerationMaximumAmount
    maximum_salary = ""
    # PayGradeHigh (0-15)
    pay_grade_high = ""
    # PayGradeLow (0-15)
    pay_grade_low = ""
    # JobCategoryCode (https://developer.usajobs.gov/API-Reference/GET-codelist-occupationalseries) 
    job_category_code = ""
    # LocationName (city, state)
    location_name = ""



    # Define the API endpoint
    url = "https://data.usajobs.gov/api/search?"

    # Make the GET request
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()  # Parse JSON response
        search_result = data.get('SearchResult')  # Get the 'SearchResult' object
        pretty_data = json.dumps(search_result, indent=4)  # Pretty print JSON
        print(pretty_data)  # Print or process the pretty data

    else:
        print(f"Error: {response.status_code} - {response.text}")


    return "<p>Hello, World!</p>"