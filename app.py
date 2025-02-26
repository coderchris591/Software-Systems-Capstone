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
                user = db.execute(
                    'SELECT * FROM user WHERE email = ?', (email,)
                ).fetchone()
                session.clear()
                session['user_id'] = user['id']
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
    jobs = []
    url = "https://data.usajobs.gov/api/search/ResultsPerPage=50"  # Default URL

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
            url = "https://data.usajobs.gov/api/Search?Keyword=" + keywords + "&ResultsPerPage=1000"
        elif location:
            # Define the API endpoint - all jobs with location
            url = "https://data.usajobs.gov/api/Search?LocationName=" + location
    else:
        custom_url = request.args.get('custom_url')
        if custom_url:
            url = custom_url

    # Make the GET request
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        print(url)
        data = response.json()  # Parse JSON response
        search_result = data.get('SearchResult')  # Get the 'SearchResult' object
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
        4: "travel",
        5: "schedule_type",
        6: "willing_to_relocate",
        7: "security_clearance",
        8: "radius",
        9: "hiring_path",
        10: "position_sensitivity",
    }

    MAX_QUESTION_INDEX = 10
  
    if request.method == 'POST':
        question_index = int(request.form['question_index'])
        current_answer = questions[question_index]
        answer = request.form.get(current_answer)
        
        if answer is None:
            flash(f"Please provide an answer for {current_answer.replace('_', ' ')}.")
            return render_template('questionnaire.html', question_index=question_index)
        if current_answer == "location":
            location_parts = answer.split(", ")
            if len(location_parts) >= 2:
                answer = f"{location_parts[-3]}, {location_parts[-2]}"
        db = get_db()
        db.execute(
            "UPDATE user SET {} = ? WHERE id = ?".format(current_answer),
            (answer, g.user['id'])
        )
        db.commit()

        # Construct the custom URL for the current answers
        user_answers = db.execute(
            "SELECT position_title, minimum_salary, location, travel, schedule_type, willing_to_relocate, security_clearance, radius, hiring_path, position_sensitivity FROM user WHERE id = ?",
            (g.user['id'],)
        ).fetchone()

        custom_url = "https://data.usajobs.gov/api/Search?"
        if user_answers['position_title']:
            custom_url += f"PositionTitle={user_answers['position_title']}&"
        if user_answers['minimum_salary']:
            custom_url += f"RemunerationMinimumAmount={user_answers['minimum_salary']}&"
        if user_answers['location']:
            custom_url += f"LocationName={user_answers['location']}&"
        if user_answers['travel']:
            custom_url += f"TravelPercentage={user_answers['travel']}&"
        if user_answers['schedule_type']:
            custom_url += f"PositionScheduleTypeCode={user_answers['schedule_type']}&"
        if user_answers['willing_to_relocate']:
            custom_url += f"RelocationFilter={user_answers['willing_to_relocate']}&"
        if user_answers['security_clearance']:
            custom_url += f"SecurityClearanceRequired={user_answers['security_clearance']}&"
        if user_answers['radius']:
            custom_url += f"Radius={user_answers['radius']}&"
        if user_answers['hiring_path']:
            custom_url += f"HiringPath={user_answers['hiring_path']}&"
        if user_answers['position_sensitivity']:
            custom_url += f"PositionSensitivity={user_answers['position_sensitivity']}&"

        # Make the GET request to get the number of jobs
        response = requests.get(custom_url, headers=headers)
        job_count = 0
        if response.status_code == 200:
            data = response.json()
            job_count = data.get('SearchResult', {}).get('SearchResultCount', 0)

        if question_index == MAX_QUESTION_INDEX:
            return redirect(url_for('search', custom_url=custom_url))
        else:
            return render_template('questionnaire.html', question_index=question_index + 1, job_count=job_count)
    else:
        return render_template('questionnaire.html', question_index=0)

@app.route('/account', methods=('GET', 'POST'))
@login_required
def account():
    db = get_db()
    user_answers = db.execute(
        "SELECT name, position_title, minimum_salary, location, travel, schedule_type, willing_to_relocate, security_clearance, radius, hiring_path, position_sensitivity FROM user WHERE id = ?",
        (g.user['id'],)
    ).fetchone()

    user_answers = dict(user_answers)  # Convert sqlite3.Row to dictionary

    dropdown_options = {
        "travel": ["Never", "Occasionally", "Some of the time", "Half the time", "More than half the time", "All the time"],
        "schedule_type": ["Full-Time", "Part-Time", "Shift Work", "Intermittent", "Job Sharing", "Multiple Schedules"],
        "willing_to_relocate": ["Yes", "No"],
        "security_clearance": ["Not Required", "Confidential", "Secret", "Top Secret", "Sensitive Compartmented Information", "Q Access Authorization", "L Access Authorization", "Other"],
        "radius": ["25 miles", "50 miles", "75 miles", "100 miles", "125 miles", "150 miles"],
        "hiring_path": ["Open to the public", "Recent graduates", "Students", "Veterans", "National Guard & Reserves", "Individuals with disabilities", "Native Americans", "Military spouses", "Peace Corps & AmeriCorps Vista", "Family of overseas employees", "Competitive service", "Career transition (CTAP, ICTAP, RPL)", "Land & base management"],
        "position_sensitivity": ["Non-sensitive - Low Risk", "Noncritical-Sensitive - Moderate Risk", "Critical-Sensitive - High Risk", "Special-Sensitive - High Risk", "Moderate Risk", "High Risk", "NCS - High Risk"]
    }

    if request.method == 'POST':
        for question in user_answers.keys():
            answer = request.form.getlist(question)
            answer = ';'.join(answer)
            db.execute(
                "UPDATE user SET {} = ? WHERE id = ?".format(question),
                (answer, g.user['id'])
            )
        db.commit()
        flash('Changes saved successfully.')
        return redirect(url_for('search'))

    return render_template('account.html', user_answers=user_answers, dropdown_options=dropdown_options)









