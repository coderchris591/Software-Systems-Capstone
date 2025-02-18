from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
import requests, my_secrets, db
from db import get_db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from geopy.geocoders import Nominatim
import os
import functools

app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'work4gov.sqlite'),
    )
# ensure the instance folder exists
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

db.init_app(app)


geolocator = Nominatim(user_agent="work4gov")
            
    
headers = {
    "Host": my_secrets.host,
    "User-Agent": my_secrets.user_agent, 
    "Authorization-Key": my_secrets.auth_key  
}

@app.route('/position_titles')
def position_titles():
    return jsonify(my_secrets.position_titles)

@app.route('/government_organizations')
def government_organizations():
    return jsonify(my_secrets.government_organizations)

@app.route('/register', methods=('GET', 'POST'))
def register():

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        error = None

        if not email:
            error = 'Email is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            try:
                db.execute(
                    "INSERT INTO user (email, password, date_created) VALUES (?, ?, ?)",
                    (email, generate_password_hash(password), datetime.now()),
                )
                db.commit()
            except db.IntegrityError:
                error = f"User {email} is already registered."
            else:
                return redirect(url_for("questionnaire"))

        flash(error)

    return render_template('register.html')


@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM user WHERE email = ?', (email,)
        ).fetchone()

        if user is None:
            error = 'Incorrect email.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('search'))

        flash(error)

    return render_template('login.html')


@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM user WHERE id = ?', (user_id,)
        ).fetchone()


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))

        return view(**kwargs)

    return wrapped_view


@app.route("/", methods=['POST', 'GET'])
@login_required
def search():
    custom_url = request.args.get('custom_url')

    if custom_url:
        url = custom_url
    else:
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
            //url = "https://data.usajobs.gov/api/search"

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


@app.route('/questionnaire', methods=('GET', 'POST'))
@login_required
def questionnaire():

    questions = {
        0: "name",
        1: "position_title",
        2: "minimum_salary",
        3: "location",
        4: "organizations",
        5: "travel",
        6: "schedule_type",
        7: "willing_to_relocate",
        8: "security_clearance",
        9: "radius",
        10: "hiring_path",
        11: "position_sensitivity",
        12: "remote"
    }

    MAX_QUESTION_INDEX = 12
  
    if request.method == 'POST':
        question_index = request.form['question_index']
        current_answer = questions[int(question_index)]
        answer = request.form[current_answer]
        db = get_db()
        db.execute(
            "UPDATE user SET {} = ? WHERE id = ?".format(current_answer),
            (answer, g.user['id'])
        )
        db.commit()
        if int(question_index) == MAX_QUESTION_INDEX:
            user_answers = db.execute(
                "SELECT position_title, minimum_salary, location, organizations, travel, schedule_type, willing_to_relocate, security_clearance, radius, hiring_path, position_sensitivity, remote FROM user WHERE id = ?",
                (g.user['id'],)
            ).fetchone()

            custom_url = "https://data.usajobs.gov/api/Search?PositionTitle=" + user_answers['position_title'] + "&RemunerationMinimumAmount=" + user_answers['minimum_salary'] + "&LocationName=" + user_answers['location'] + "&Organizations=" + user_answers['organizations'] + "&TravelPercentage=" + user_answers['travel'] + "&PositionScheduleTypeCode=" + user_answers['schedule_type'] + "&RelocationFilter=" + user_answers['willing_to_relocate'] + "&SecurityClearanceRequired=" + user_answers['security_clearance'] + "&Radius=" + user_answers['radius'] + "&HiringPath=" + user_answers['hiring_path'] + "&PositionSensitivity=" + user_answers['position_sensitivity'] + "&RemoteIndicator=" + user_answers['remote']
            return redirect(url_for('search'), custom_url=custom_url)
        else:
            return render_template('questionnaire.html', question_index=int(question_index) + 1)
    else:
        return render_template('questionnaire.html', question_index=0)









