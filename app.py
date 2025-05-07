from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
import requests, my_secrets, db
from db import get_db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
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
    return jsonify(my_secrets.government_organizations())

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
                return redirect(url_for("search"))

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
    keywords = None
    location = None

    if request.method == 'POST':
        keywords = request.form.get('keywords', '')
        location = request.form.get('location', '')
        return redirect(url_for('search', keywords=keywords, location=location))

    # GET method — full query param support
    keywords = request.args.get('keywords', '')
    location = request.args.get('location', '')
    position_title = request.args.get('position_title')
    minimum_salary = request.args.get('minimum_salary')
    hiring_path = request.args.get('hiring_path')
    remote = request.args.get('remote')

    print("keywords: " + keywords)
    print("location: " + location)
    if location:
        location = location.replace(" ", "")

    db = get_db()
    # Fetch the current user data from the database
    user_data = db.execute(
        "SELECT position_title, minimum_salary, location, hiring_path, remote FROM user WHERE id=?",
        (g.user['id'],)
    ).fetchone()

    position_title_preference = user_data['position_title']
    minimum_salary_preference = user_data['minimum_salary']
    location_preference = user_data['location']
    hiring_path_preference = user_data['hiring_path']
    remote_preference = user_data['remote']

    url = "https://data.usajobs.gov/api/Search?ResultsPerPage=500&"


    if position_title_preference:
        position_title = position_title_preference
    if minimum_salary_preference:
        minimum_salary = minimum_salary_preference
    if location_preference:
        location = location_preference
    if hiring_path_preference:
        hiring_path = hiring_path_preference
    if remote_preference:
        remote = remote_preference


    # Build URL
    if keywords: 
        if keywords:
            url += f"Keyword={keywords}&"
    else:
        if location:
            url += f"LocationName={location}&SortField=location&RemoteIndicator=False&"
        if position_title:
            url += f"PositionTitle={position_title}&"
        if minimum_salary:
            url += f"RemunerationMinimumAmount={minimum_salary}&"
        if hiring_path:
            url += f"HiringPath={hiring_path}&"
        if remote:
            url += f"Remote={remote}&"

    print("url: " + url)
    if url.endswith('&'):
        url = url[:-1]  # Remove trailing '&' if present
    print("url: " + url)
    # Fetch jobs, parse response...
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        search_result = data.get('SearchResult')  # Get the 'SearchResult' object
        pages = search_result.get('pages', 0)  # Get the number of pages
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

    return render_template("search.html", results=jobs, pages=pages)


# @app.route('/questionnaire', methods=('GET', 'POST'))
# @login_required
# def questionnaire():
#     questions = {
#         0: "name",
#         1: "position_title",
#         2: "minimum_salary",
#         3: "location",
#         4: "travel",
#         5: "schedule_type",
#         6: "willing_to_relocate",
#         7: "security_clearance",
#         8: "radius",
#         9: "hiring_path",
#         10: "remote",
#         11: "position_sensitivity",
#     }

#     MAX_QUESTION_INDEX = 11

#     if request.method == 'POST':
#         question_index = int(request.form['question_index'])
#         current_answer = questions[question_index]
#         print("current_answer: " + current_answer)
#         answer = request.form.get(current_answer)
#         print("answer: " + answer)

#         # Handle position_title specifically for multiple values
#         if current_answer == "position_title":
#             answer = request.form.get("position_title", "").strip()
#             if not answer:
#                 flash("Please select at least one position title.")
#                 return render_template('questionnaire.html', question_index=question_index)
#             answer = ";".join([title.strip() for title in answer.split(";") if title.strip()])

#         if not answer:
#             flash(f"Please provide an answer for {current_answer.replace('_', ' ')}.")
#             return render_template('questionnaire.html', question_index=question_index)

#         db = get_db()
#         db.execute(
#             "UPDATE user SET {} = ? WHERE id = ?".format(current_answer),
#             (answer, g.user['id'])
#         )
#         db.commit()

#         # Construct the custom URL for the current answers
#         user_answers = db.execute(
#             "SELECT position_title, minimum_salary, location, travel, schedule_type, willing_to_relocate, security_clearance, radius, hiring_path, remote, position_sensitivity FROM user WHERE id = ?",
#             (g.user['id'],)
#         ).fetchone()

#         custom_url = "https://data.usajobs.gov/api/Search?"
#         if user_answers['position_title']:
#             custom_url += f"PositionTitle={user_answers['position_title']}&"
#         if user_answers['minimum_salary']:
#             custom_url += f"RemunerationMinimumAmount={user_answers['minimum_salary']}&"
#         if user_answers['location']:
#             custom_url += f"LocationName={user_answers['location']}&"
#         if user_answers['travel']:
#             custom_url += f"TravelPercentage={user_answers['travel']}&"
#         if user_answers['schedule_type']:
#             custom_url += f"PositionScheduleTypeCode={user_answers['schedule_type']}&"
#         if user_answers['willing_to_relocate']:
#             custom_url += f"RelocationFilter={user_answers['willing_to_relocate']}&"
#         if user_answers['security_clearance']:
#             custom_url += f"SecurityClearanceRequired={user_answers['security_clearance']}&"
#         if user_answers['radius']:
#             custom_url += f"Radius={user_answers['radius']}&"
#         if user_answers['hiring_path']:
#             custom_url += f"HiringPath={user_answers['hiring_path']}&"
#         if user_answers['remote']:
#             custom_url += f"Remote={user_answers['remote']}&"
#         if user_answers['position_sensitivity']:
#             custom_url += f"PositionSensitivity={user_answers['position_sensitivity']}&"

#         # Make the GET request to get the number of jobs
#         response = requests.get(custom_url, headers=headers)
#         job_count = 0
#         if response.status_code == 200:
#             data = response.json()
#             job_count = data.get('SearchResult', {}).get('SearchResultCount', 0)

#         if question_index == MAX_QUESTION_INDEX:
#             return redirect(url_for('search', custom_url=custom_url))
#         else:
#             return render_template('questionnaire.html', question_index=question_index + 1, job_count=job_count)
#     else:
#         return render_template('questionnaire.html', question_index=0)

@app.route('/filter', methods=('GET', 'POST'))
@login_required
def filter():
    if request.method == 'POST':
        # Get the selected position titles from the form
        position_title = request.form.get('position_title', '')
        minimum_salary = request.form.get('minimum_salary', '')
        location = request.form.get('location', '')
        hiring_path = request.form.get('hiring_path', '')
        remote = request.form.get('remote', '')
        
        return redirect(url_for('search', position_title=position_title, minimum_salary=minimum_salary, location=location, hiring_path=hiring_path, remote=remote))
    else:
        return render_template('filter.html', position_titles=my_secrets.position_titles)
 

@app.route('/account', methods=('GET', 'POST'))
@login_required
def account():
    if request.method == 'POST':
        # Get the submitted form values
        position_title = request.form.get('position_title')
        minimum_salary = request.form.get('minimum_salary')
        location = request.form.get('location')
        hiring_path = request.form.get('hiring_path')
        remote = request.form.get('remote')

        # Fetch the current user data from the database
        db = get_db()
        user_data = db.execute(
            "SELECT position_title, minimum_salary, location, hiring_path, remote FROM user WHERE id=?",
            (g.user['id'],)
        ).fetchone()

        # Prepare the update query dynamically
        update_fields = []
        update_values = []

        if position_title and position_title != user_data['position_title']:
            update_fields.append("position_title=?")
            update_values.append(position_title)

        if minimum_salary and minimum_salary != user_data['minimum_salary']:
            update_fields.append("minimum_salary=?")
            update_values.append(minimum_salary)

        if location and location != user_data['location']:
            update_fields.append("location=?")
            update_values.append(location)

        if hiring_path and hiring_path != user_data['hiring_path']:
            update_fields.append("hiring_path=?")
            update_values.append(hiring_path)

        if remote and remote != str(user_data['remote']):  # Convert remote to string for comparison
            update_fields.append("remote=?")
            update_values.append(remote)

        # Only execute the update query if there are changes
        if update_fields:
            update_query = f"UPDATE user SET {', '.join(update_fields)} WHERE id=?"
            update_values.append(g.user['id'])  # Add the user ID to the values
            db.execute(update_query, update_values)
            db.commit()
            flash("Account updated successfully.", 'success')
        else:
            flash("No changes were made.", 'info')

        return redirect(url_for('account'))
    else:

        reset = request.args.get('reset', '')
        if reset == 'true':
            # Reset the user data to default values
            db = get_db()
            db.execute(
                "UPDATE user SET position_title=?, minimum_salary=?, location=?, hiring_path=?, remote=? WHERE id=?",
                (None, None, None, None, None, g.user['id'])
            )
            db.commit()
            flash("Account reset successfully.", 'success')
            return redirect(url_for('account'))
        else:
            # Fetch the current user data for the GET request
            db = get_db()
            user_data = db.execute(
                "SELECT position_title, minimum_salary, location, hiring_path, remote FROM user WHERE id=?",
                (g.user['id'],)
            ).fetchone()

            if user_data:
                return render_template('account.html', user_data=user_data, position_titles=my_secrets.position_titles)
            else:
                flash("User not found.", 'error')
                return redirect(url_for('login'))
 

# @app.route('/update', methods=('GET', 'POST'))
# @login_required
# def update():
#     question_index = int(request.args.get('question_index', 0))
#     questions = {
#         0: "name",
#         1: "position_title",
#         2: "minimum_salary",
#         3: "location",
#         4: "travel",
#         5: "schedule_type",
#         6: "willing_to_relocate",
#         7: "security_clearance",
#         8: "radius",
#         9: "hiring_path",
#         10: "remote",
#         11: "position_sensitivity",
#     }

#     if request.method == 'POST':
#         current_answer = questions[question_index]
#         answer = request.form.get(current_answer)
        
#         if answer is None:
#             flash(f"Please provide an answer for {current_answer.replace('_', ' ')}.")
#             return render_template('update.html', question_index=question_index)
        
#         if current_answer == "location":
#             location_parts = answer.split(", ")
#             if len(location_parts) >= 2:
#                 answer = f"{location_parts[-3]}, {location_parts[-2]}"
        
#         db = get_db()
#         db.execute(
#             "UPDATE user SET {} = ? WHERE id = ?".format(current_answer),
#             (answer, g.user['id'])
#         )
#         db.commit()

#         flash(f"{current_answer.replace('_', ' ').capitalize()} updated successfully.", 'success')
#         return redirect(url_for('account'))
    
#     db = get_db()
#     if question_index == 0:
#         data = db.execute("SELECT name FROM user WHERE id = ?", (g.user['id'],)).fetchone()
#         data = data['name']
#     elif question_index == 1:
#         data = db.execute("SELECT position_title FROM user WHERE id = ?", (g.user['id'],)).fetchone()
#         data = data['position_title']
#     elif question_index == 2:
#         data = db.execute("SELECT minimum_salary FROM user WHERE id = ?", (g.user['id'],)).fetchone()
#         data = data['minimum_salary']
#     elif question_index == 3:
#         data = db.execute("SELECT location FROM user WHERE id = ?", (g.user['id'],)).fetchone()
#         data = data['location']
#         print("location: " + data)
#     elif question_index == 4:
#         data = db.execute("SELECT travel FROM user WHERE id = ?", (g.user['id'],)).fetchone()
#     elif question_index == 5:
#         data = db.execute("SELECT schedule_type FROM user WHERE id = ?", (g.user['id'],)).fetchone()
#     elif question_index == 6:   
#         data = db.execute("SELECT willing_to_relocate FROM user WHERE id = ?", (g.user['id'],)).fetchone()
#     elif question_index == 7:
#         data = db.execute("SELECT security_clearance FROM user WHERE id = ?", (g.user['id'],)).fetchone()
#     elif question_index == 8:
#         data = db.execute("SELECT radius FROM user WHERE id = ?", (g.user['id'],)).fetchone()
#     elif question_index == 9:
#         data = db.execute("SELECT hiring_path FROM user WHERE id = ?", (g.user['id'],)).fetchone()
#     elif question_index == 10:
#         data = db.execute("SELECT remote FROM user WHERE id = ?", (g.user['id'],)).fetchone()
#         data = data['remote']
#     elif question_index == 11:
#         data = db.execute("SELECT position_sensitivity FROM user WHERE id = ?", (g.user['id'],)).fetchone()

    

        

#     return render_template('update.html', question_index=question_index, data=data)





