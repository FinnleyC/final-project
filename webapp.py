from flask import Flask, redirect, url_for, session, request, jsonify, render_template, flash, Markup
from flask_apscheduler import APScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from flask_oauthlib.client import OAuth
from bson.objectid import ObjectId

import pprint
import os
import time
import pymongo
import sys
 
app = Flask(__name__)

#initialize scheduler with your preferred timezone
scheduler = BackgroundScheduler({'apscheduler.timezone': 'America/Los_Angeles'})
scheduler.start()
 
app.secret_key = os.environ['SECRET_KEY'] #used to sign session cookies
oauth = OAuth(app)
oauth.init_app(app) #initialize the app to be able to make requests for user information

#Set up GitHub as OAuth provider
github = oauth.remote_app(
    'github',
    consumer_key=os.environ['GITHUB_CLIENT_ID'], #your web app's "username" for github's OAuth
    consumer_secret=os.environ['GITHUB_CLIENT_SECRET'],#your web app's "password" for github's OAuth
    request_token_params={'scope': 'user:email'}, #request read-only access to the user's email.  For a list of possible scopes, see developer.github.com/apps/building-oauth-apps/scopes-for-oauth-apps
    base_url='https://api.github.com/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://github.com/login/oauth/access_token',  
    authorize_url='https://github.com/login/oauth/authorize' #URL for github's OAuth login
)

#Connect to database
url = os.environ["MONGO_CONNECTION_STRING"]
client = pymongo.MongoClient(url)
db = client[os.environ["MONGO_DBNAME"]]
matches = db['Matches'] #TODO: put the name of the collection here
seasons = db['Seasons']

print("connected to db")

#context processors run before templates are rendered and add variable(s) to the template's context
#context processors must return a dictionary 
#this context processor adds the variable logged_in to the conext for all templates
@app.context_processor
def inject_logged_in():
    return {"logged_in":('github_token' in session)}

@app.route('/')
def home():
    return render_template('home.html')

#redirect to GitHub's OAuth page and confirm callback URL
@app.route('/login')
def login():   
    return github.authorize(callback=url_for('authorized', _external=True, _scheme='https')) #callback URL must match the pre-configured callback URL

@app.route('/logout')
def logout():
    session.clear()
    flash('You were logged out.')
    return redirect('/')

@app.route('/login/authorized')
def authorized():
    resp = github.authorized_response()
    if resp is None:
        session.clear()
        flash('Access denied: reason=' + request.args['error'] + ' error=' + request.args['error_description'] + ' full=' + pprint.pformat(request.args), 'error')      
    else:
        try:
            session['github_token'] = (resp['access_token'], '') #save the token to prove that the user logged in
            session['user_data']=github.get('user').data
            #pprint.pprint(vars(github['/email']))
            #pprint.pprint(vars(github['api/2/accounts/profile/']))
            flash('You were successfully logged in as ' + session['user_data']['login'] + '.')
        except Exception as inst:
            session.clear()
            print(inst)
            flash('Unable to login, please try again.', 'error')
    return redirect('/')


@app.route('/mdb')
def renderPage1():
    games = list(matches.find().sort("link", -1)) #sorts by link, highest to lowest; link represents most recent match
    noplayoff = 1
    gseason = ""
    gmap = ""
    gteam = ""
    gweek = ""
    if 'season' in request.args:
        gseason = request.args['season']   #DEBUG, will be user defined int()
        gmap = request.args['map']              #user defined dropdown for all maps
        gteam = request.args['team']            #user defined dropdown for all teams
        gweek = request.args['week']            #user defined text for week (MAKE NOT CASE SENSITIVE)
    gfinal = []
    for g in games:
        playoffbool = True
        seasonbool = True
        mapbool = True
        teambool = True
        weekbool = True
        if noplayoff == 1:
            if 'playoff' in g and g.get('playoff') == True:
                playoffbool = False
            #games where playoff != True
        if gseason != "":
            if g['season'] != int(gseason):
                seasonbool = False
            #games in season   
        if gmap != "":
            if gmap not in g['map1']:
                mapbool = False
            #games on map
        if gteam != "":
            if g['hteam'] != gteam and g['ateam'] != gteam:
                teambool = False
            #games with team
        if gweek != "":
            if gweek not in g['week']:
                weekbool = False
            #games in week
        if playoffbool and seasonbool and mapbool and teambool and weekbool == True:
            gfinal.append(g)
    #todo: commit to new branch and make load only table ajax load() (so options will stay after submit)
    htm = ""
    for g in gfinal:
            htm += Markup('<tr><td>'+str(g['season'])+'</td><td><a class="LN1 LN2 LN3 LN4 LN5" href="https://rgl.gg/Public/Match.aspx?&m='+str(g['link'])+'" target="_top">'+g['week']+'</td><td>'+g['hteam']+'</td><td>'+g['ateam']+'</td><td>'+g['map1']+'</td><td>')
            if 'log1' in g:
                htm += Markup('<a class="LN1 LN2 LN3 LN4 LN5" href="https://logs.tf/'+g['log1']+'" target="_top">'+g['log1'])
            elif 'ff' in g:
                htm += Markup('FORFEIT')
            if 'demo1' in g:
                htm += Markup('</td><td><a class="LN1 LN2 LN3 LN4 LN5" href="https://logs.tf/'+g['demo1']+'" target="_top">'+g['demo1']+'</td></tr>')
            elif 'ff' in g:
                htm += Markup('</td><td>FORFEIT</td></tr>')
            else:
                htm += Markup('</td><td></td></tr>')
    return render_template('mdb.html', htm = htm)

@app.route('/pview')
def renderPage2():
    return render_template('pview.html')

#the tokengetter is automatically called to check who is logged in.
@github.tokengetter
def get_github_oauth_token():
    return session['github_token']


if __name__ == '__main__':
    app.run()
