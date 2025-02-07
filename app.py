

from flask import Flask, render_template, request
import requests, my_secrets
from datetime import datetime
from geopy.geocoders import Nominatim

app = Flask(__name__)
geolocator = Nominatim(user_agent="work4gov")
            
    
headers = {
    "Host": my_secrets.host,
    "User-Agent": my_secrets.user_agent, 
    "Authorization-Key": my_secrets.auth_key  
}


@app.route("/", methods=['POST', 'GET'])
def search():

    # INFO from: https://developer.usajobs.gov/api-reference/get-api-search

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
    # Organizations (https://developer.usajobs.gov/API-Reference/GET-codelist-agencysubelements)
    organization = ""
    # PositionOfferingTypeCode
    work_type = ""
    # TravelPercentage
    travel_percentage = "" # (0-8)
    # PositionScheduleTypeCode
    position_schedule_type_code = "" # (1-6)
    # RelocationFilter
    willing_to_relocate = "" # (T/F)
    # SecurityClearanceRequired
    level_of_security_clearance = "" # (0-8)
    # SupervisoryStatus
    supervisory_status = ""
    # DatePosted
    date_posted = "" # integers (0-60) days ago
    # JobGradeCode
    job_grade_code = ""
    # SortField
    sort_field = ""
    # SortDirection
    sort_direction = "" # (Asc/Dec)
    # Page
    page = ""
    # ResultsPerPage
    results_per_page = "" # (0-500)
    # WhoMayApply
    who_may_apply = "" # (All, Public, Status) Note: All and Status require specific authorization
    # Radius
    radius = "" # Used along with LocationName, will expand locations based on given radius
    # Fields
    fields = "" # (Min, Full)
    # SalaryBucket
    salary_bucket = "" # Ex: 25 = $25,000 - $49,000
    # GradeBucket
    grade_bucket = ""
    # HiringPath
    hiring_path = "" # i.e. public, vet, nguard, disability, native, student, ses, graduates
    # MissionCriticalTags
    mission_critical_tags = ""
    # PositionSensitivity
    position_sensitivity = "" # (0 (Low Risk) - 7 (High Risk))
    #RemoteIndicator 
    remote_indicator = "" # (True/False)

    # An example using multiple parameters:
    # https://data.usajobs.gov/api/Search?Keyword=nurse&JobCategoryCode=2210&WhoMayApply=public&fields=all


    if request.method == 'POST':
        # Get user keywords
        keywords = request.form.get('keywords', "")
        location = geolocator.geocode(request.form.get('location', ""))
        if location: 
            location = location.address
            location = location.split(", ")
            location = location[-4] + ", " + location[-2]
       

        if location and keywords:
            url = "https://data.usajobs.gov/api/Search?Keyword=" + keywords + "&LocationName=" + location
        elif keywords:
            # Define the API endpoint - all jobs with keywords
            url = "https://data.usajobs.gov/api/Search?Keyword=" + keywords
        elif location:
            # Define the API endpoint - all jobs with location
            url = "https://data.usajobs.gov/api/Search?LocationName=" + location
    else:
        # Define the API endpoint - all jobs
        url = "https://data.usajobs.gov/api/search"

    # Make the GET request
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        print(url)
        data = response.json()  # Parse JSON response
        search_result = data.get('SearchResult')  # Get the 'SearchResult' object
        jobs = []
        for job in search_result['SearchResultItems']:
            job_info = {
                            'position_title': job['MatchedObjectDescriptor']['PositionTitle'],
                            'location_name': job['MatchedObjectDescriptor']['PositionLocation'][0]['LocationName'],
                            'organization': job['MatchedObjectDescriptor']['OrganizationName'],
                            'date_posted': datetime.strptime(job['MatchedObjectDescriptor']['PublicationStartDate'], '%Y-%m-%dT%H:%M:%S.%f').strftime('%B %d, %Y'),
                            'pay_grade_min': f"${float(job['MatchedObjectDescriptor']['PositionRemuneration'][0]['MinimumRange']):,.2f}",
                            'pay_grade_max': f"${float(job['MatchedObjectDescriptor']['PositionRemuneration'][0]['MaximumRange']):,.2f}",
                            'qualifications_summary': job['MatchedObjectDescriptor'].get('UserArea', {}).get('Details', {}).get('MajorDuties', 'N/A'),
                            'job_uri': job['MatchedObjectDescriptor']['PositionURI']
                        }    
            
            jobs.append(job_info)
    else:
        print(f"Error: {response.status_code} - {response.text}")

    return render_template("search.html", results=jobs)








