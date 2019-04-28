#Import Flask Library
from flask import Flask, flash, render_template, request, session, url_for, redirect
import pymysql.cursors
import os

import hashlib


salt = b"dankmemes"

def sha1Pass(password):
    m = hashlib.sha1()
    m.update(password)
    return m.hexdigest()

#Initialize the app from Flask
app = Flask(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

#Configure MySQL
conn = pymysql.connect(host='localhost',
                       port = 3306,
                       user='root',
                       #password='root',
                       db='finstagram',
                       charset='utf8mb4',
                       cursorclass=pymysql.cursors.DictCursor)

#Define a route to hello function
@app.route('/')
def hello():
    return render_template('index.html')

#Define route for login
@app.route('/login')
def login():
    return render_template('login.html')

#Define route for register
@app.route('/register')
def register():
    return render_template('register.html')

#Authenticates the login
@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
    #grabs information from the forms
    username = request.form['username']
    password = sha1Pass((request.form['password']).encode('utf-8') + salt)

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM Person WHERE username = %s and password = %s'
    cursor.execute(query, (username, password))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    cursor.close()
    error = None
    if(data):
        #creates a session for the the user
        #session is a built in
        session['username'] = username
        return redirect(url_for('home'))
    else:
        #returns an error message to the html page
        error = 'Invalid login or username'
        return render_template('login.html', error=error)

#Authenticates the register
@app.route('/registerAuth', methods=['GET', 'POST'])
def registerAuth():
    #grabs information from the forms
    username = request.form['username']
    password = sha1Pass((request.form['password']).encode('utf-8') + salt)
    fname = request.form['fname']
    lname = request.form['lname']

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (username))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    error = None
    if(data):
        #If the previous query returns data, then user exists
        error = "This user already exists"
        return render_template('register.html', error = error)
    else:
        ins = 'INSERT INTO Person VALUES(%s, %s, %s, %s, %s, %s, %s)'
        cursor.execute(ins, (username, password, fname, lname, None, None, True))
        conn.commit()
        cursor.close()
        return render_template('index.html')


@app.route('/home')
def home():
    user = session['username']
    cursor = conn.cursor()
    query = 'SELECT * FROM (SELECT * FROM Photo AS p WHERE p.photoID IN (SELECT photoID FROM Belong NATURAL JOIN Share WHERE username = %s) OR (allfollowers = 1 AND EXISTS (SELECT * FROM Follow WHERE followerUsername = %s and followeeUsername = p.photoOwner)) OR (p.photoOwner = %s)) AS temp1 LEFT JOIN (SELECT l.photoID, l.likeCount, r.ifLiked FROM (SELECT photoID, count(*) AS likeCount FROM Liked GROUP BY photoID) AS l LEFT JOIN (SELECT photoID, True AS ifLiked FROM Liked WHERE username = %s) AS r ON (l.photoID = r.photoID)) AS temp2 ON (temp1.photoID = temp2.photoID) ORDER BY timestamp DESC'
    cursor.execute(query, (user, user, user, user))
    data = cursor.fetchall()

    query = 'SELECT username, photoID, commentText, timestamp FROM Comment ORDER BY timestamp ASC'
    cursor.execute(query)
    commentsData = cursor.fetchall()
    #all groups user can post too
    query = 'SELECT * FROM Belong WHERE username = %s AND accepted = 1'
    cursor.execute(query, (user))
    groups = cursor.fetchall()
    length = [ i for i in range(len(groups)) ]

    #prob needs to be fixed
    query = "SELECT * FROM Tag WHERE acceptedTag = 1;"
    cursor.execute(query)
    tags = cursor.fetchall()

    #need natural join for photoid but can join in the last query to avoid errors
    query = 'SELECT * FROM Belong NATURAL JOIN SHARE WHERE username = %s'
    cursor.execute(query, (user))
    viewableGroups = cursor.fetchall()

    cursor.close()
    return render_template('home.html', username=user, posts=data, group = groups, length = length, comments = commentsData, tags = tags,viewableGroups=viewableGroups)


@app.route('/post', methods=['GET', 'POST'])
def post():
    username = session['username']
    cursor = conn.cursor()
    pic = request.files['pic']
    extension = os.path.splitext(pic.filename)[1]
    caption = None if len(request.form['caption']) == 0 else request.form['caption']
    allFollowers = True if request.form['allFollowers'] == "true" else False

    target = os.path.join(APP_ROOT, 'uploads/')

    query = 'INSERT INTO Photo (photoOwner, timestamp, caption, allFollowers) VALUES(%s, NOW(), %s, %s)'
    cursor.execute(query, (username, caption, allFollowers))
    conn.commit()

    query = 'SELECT photoID FROM Photo WHERE photoOwner = %s ORDER BY timestamp DESC'
    cursor.execute(query, (username))
    data = cursor.fetchone()
    # print(data)
    # print(extension)

    file_name = str(data['photoID']) + extension
    pic.save("/".join([APP_ROOT, "static/uploads", file_name]))

    query = 'UPDATE Photo SET filePath = %s WHERE photoID = %s'
    cursor.execute(query, (file_name, data['photoID']))
    conn.commit()

    if not allFollowers:
        groupName = dict()
        groupOwner = dict()
        for key in request.form:
            split = key.split(",")
            if "groupName" == split[0]:
                groupName[int(split[1])] = request.form[key]
            elif "groupOwner" == split[0]:
                groupOwner[int(split[1])] = request.form[key]

        for key in groupName:
            query = "INSERT INTO Share VALUES(%s, %s, %s)"
            cursor.execute(query, (groupName[key], groupOwner[key], data['photoID']))
            conn.commit()

    cursor.close()
    return redirect(url_for('home'))

@app.route("/comment/<photoID>", methods=['GET', 'POST'])
def comment(photoID):
    username = session['username']
    cursor = conn.cursor()
    comment = None if len(request.form['myComment']) == 0 else request.form['myComment']
    query = 'INSERT INTO Comment (username, photoID, commentText, timestamp) VALUES(%s, %s, %s, NOW())'
    cursor.execute(query, (username, photoID, comment))
    conn.commit()
    cursor.close()
    return redirect(url_for('home'))

@app.route("/like/<photoID>", methods=['GET', 'POST'])
def like(photoID):
    username = session['username']
    cursor = conn.cursor()
    query = 'INSERT INTO Liked (username, photoID, timestamp) VALUES(%s, %s, NOW())'
    cursor.execute(query, (username, photoID))
    conn.commit()
    cursor.close()
    return redirect(url_for('home'))

@app.route("/unlike/<photoID>", methods=['GET', 'POST'])
def unlike(photoID):
    username = session['username']
    cursor = conn.cursor()
    query = 'DELETE FROM Liked WHERE username = %s AND photoID = %s'
    cursor.execute(query, (username, photoID))
    conn.commit()
    cursor.close()
    return redirect(url_for('home'))

@app.route('/select_blogger')
def select_blogger():
    #check that user is logged in
    #username = session['username']
    #should throw exception if username not found

    cursor = conn.cursor();
    # query = 'SELECT DISTINCT username FROM blog'
    cursor.execute(query)
    data = cursor.fetchall()
    cursor.close()
    return render_template('select_blogger.html', user_list=data)

@app.route('/send_follow', methods = ["GET", "POST"])
def send_follow():
    #reloads page but sends follow to user specified
    username = session['username']
    toFollow = request.form['toFollow']
    cursor = conn.cursor()
    #prior to following, followee msut exist - will need to check
    query = 'SELECT Count(*) as count FROM Person WHERE username = %s;'
    cursor.execute(query, (toFollow))
    data = cursor.fetchall()
    if data[0]['count'] == 1:
        query = 'SELECT Count(*) as count FROM Follow WHERE followerUsername = %s AND followeeUsername = %s;'
        cursor.execute(query, (username, toFollow))
        data = cursor.fetchall()
        if data[0]['count'] == 1:
            flash("You're already following " + toFollow)
        else:
            query  = "INSERT INTO `follow`(`followerUsername`, `followeeUsername`, `acceptedfollow`) VALUES (%s,%s,%s)"
            #print(request.form['toFollow'])
            cursor.execute(query, (username, toFollow, False))
            conn.commit()
    else:
        flash(toFollow + " does not exist!")
    cursor.close()
    return redirect(url_for('follow'))

@app.route('/accept_follow/<follower>')
def accept_follow(follower):
    cursor = conn.cursor()
    query = 'UPDATE Follow SET acceptedfollow = 1 WHERE followerUsername = %s AND followeeUsername = %s'
    cursor.execute(query, (follower, session['username']))
    conn.commit()
    cursor.close()
    return redirect(url_for('follow'))

@app.route('/reject_follow/<follower>')
def reject_follow(follower):
    cursor = conn.cursor()
    query = 'DELETE FROM Follow WHERE followerUsername = %s AND followeeUsername = %s'
    cursor.execute(query, (follower, session['username']))
    conn.commit()
    cursor.close()
    return redirect(url_for('follow'))

@app.route('/follow')
def follow():
    user = session['username']
    data = []
    cursor = conn.cursor();
    #get users who are still pending
    query = 'SELECT followerUsername FROM Follow WHERE followeeUsername = %s AND acceptedfollow = 0'
    cursor.execute(query, (user))
    data.append(cursor.fetchall())
    #get users who were accepted

    # get following (double check)
    query = 'SELECT followeeUsername FROM Follow WHERE followerUsername = %s AND acceptedfollow = 1'
    cursor.execute(query, (user))
    data.append(cursor.fetchall())


    query = 'SELECT followerUsername FROM Follow WHERE followeeUsername = %s AND acceptedfollow = 1'
    cursor.execute(query, (user))
    data.append(cursor.fetchall())
    cursor.close()
    return render_template('follow.html', requests = data)

@app.route('/follower_unfollow/<followee>')
def follower_unfollow(followee):
    cursor = conn.cursor()
    query = 'DELETE FROM Follow WHERE followeeUsername = %s AND followerUsername = %s'
    cursor.execute(query, (followee, session['username']))
    conn.commit()
    query = 'DELETE FROM Tag WHERE username = %s AND photoID IN (SELECT photoID FROM Photo WHERE photoOwner = %s) '
    cursor.execute(query, (session['username'], followee))
    conn.commit()
    cursor.close()
    return redirect(url_for('follow'))

@app.route('/followee_unfollow/<follower>')
def followee_unfollow(follower):
    cursor = conn.cursor()
    query = 'DELETE FROM Follow WHERE followerUsername = %s AND followeeUsername = %s'
    cursor.execute(query, (follower, session['username']))
    conn.commit()
    query = 'DELETE FROM Tag WHERE username = %s AND photoID IN (SELECT photoID FROM Photo WHERE photoOwner = %s) '
    cursor.execute(query, (follower, session['username']))
    conn.commit()
    cursor.close()
    return redirect(url_for('follow'))

@app.route('/group')
def group():
    user = session['username']
    cursor = conn.cursor()
    query = 'SELECT groupName, groupOwner, accepted FROM Belong WHERE username = %s and accepted = True'
    cursor.execute(query, (user))
    data = cursor.fetchall()

    pendingQry = 'SELECT groupName, groupOwner, accepted FROM Belong WHERE username = %s and accepted = False'
    cursor.execute(pendingQry,(user))
    pendingdata = cursor.fetchall()

    cursor.close()
    return render_template('group.html', request = data, pending = pendingdata)

@app.route('/create_group',  methods = ["GET", "POST"])
def create_group():
    user = session['username']
    group_name = request.form["createGroup"]
    cursor = conn.cursor();
    #check if user already owns a
    query = 'SELECT Count(*) as count FROM closefriendgroup WHERE groupName = %s AND groupOwner = %s;'
    cursor.execute(query,(group_name, user))
    data = cursor.fetchall()
    print(data[0]['count'])
    if data[0]['count'] == 1:
        #print("I already own a group with this name")
        flash('You already own a group with name:' + group_name)
    else:
        #create a group if user does not currently own a group
        query = 'INSERT INTO closefriendgroup (groupName, groupOwner) VALUES (%s,%s);'
        cursor.execute(query, (group_name, user))
        query = 'INSERT INTO belong (groupName, groupOwner, username, accepted) VALUES (%s,%s,%s, True);'
        cursor.execute(query, (group_name, user, user))

        #double check was removed
        conn.commit()
        cursor.close()

    return redirect(url_for('group'))

@app.route('/manage_group/<group>/<group_owner>', methods = ["GET", "POST"])
def manage_group(group,group_owner):
    user = session['username']
    groupName = group
    cursor = conn.cursor()
    query = "SELECT groupName, groupOwner, username FROM belong WHERE groupName = %s and groupOwner = %s and accepted = True"
    cursor.execute(query, (group,group_owner))
    data = cursor.fetchall()
    cursor.close()
    return render_template('manage_groups.html', data = data)

@app.route('/kick_member/<group>/<username>', methods = ["GET","POST"])
def kick_member(group,username):
    groupName = group
    toKick = username
    cursor = conn.cursor()
    query = "DELETE FROM belong WHERE `groupName` = %s AND `groupOwner` = %s AND `username` = %s;"
    print(query, (group,session["username"],toKick))
    cursor.execute(query, (group,session["username"],toKick))

    query = "SELECT groupName, groupOwner, username FROM belong WHERE groupName = %s and groupOwner = %s"
    cursor.execute(query, (group,session["username"]))
    data = cursor.fetchall()
    cursor.close()
    return render_template('manage_groups.html', data = data)


@app.route('/accept_group/<group>/<group_owner>')
def accept_group(group,group_owner):
    user = session['username']
    cursor = conn.cursor()
    query = 'UPDATE belong SET accepted = True WHERE groupName = %s AND groupOwner = %s AND username = %s;'
    cursor.execute(query, (group,group_owner,user))
    conn.commit()
    cursor.close()
    return redirect(url_for('group'))

@app.route('/decline_group/<group>/<group_owner>')
def decline_group(group, group_owner):
    user = session['username']
    cursor = conn.cursor()
    query = 'DELETE FROM belong WHERE groupName = %s AND groupOwner = %s AND username = %s;'
    cursor.execute(query, (group,group_owner,user))
    conn.commit()
    cursor.close()
    return redirect(url_for('group'))

@app.route('/leave_group/<group>/<group_owner>')
def leave_group(group,group_owner):
    print(group, group_owner)
    cursor = conn.cursor()
    query = "DELETE FROM belong WHERE `groupName` = %s AND `groupOwner` = %s AND `username` = %s;"
    cursor.execute(query, (group, group_owner, session["username"]))
    cursor.close()
    return redirect(url_for('group'))

@app.route('/close_group/<group>/<group_owner>')
def close_group(group,group_owner):
    print(group,group_owner)
    cursor = conn.cursor()

    #remove everyone from the group
    query = "DELETE FROM belong WHERE `groupName` = %s AND `groupOwner` = %s;"
    cursor.execute(query, (group,group_owner))

    #kill the group
    query = "DELETE FROM closefriendgroup WHERE `groupName` = %s AND `groupOwner` = %s;"
    cursor.execute(query, (group,group_owner))
    cursor.close()
    return redirect(url_for('group'))

@app.route('/add_friend', methods = ["GET", "POST"])
def add_friend():
    user = session['username']
    group_name = request.form["group_name"]
    to_add = request.form["toAdd"]
    cursor = conn.cursor();

    #find if group exists and you are the owner
    query = 'SELECT Count(*) as count FROM closefriendgroup WHERE groupName = %s AND groupOwner = %s;'
    cursor.execute(query,(group_name, user))
    data = cursor.fetchall()
    if data[0]['count'] == 1:
        #check if user you are adding is already in the group
        query = 'SELECT Count(*) as count FROM belong WHERE groupName = %s AND groupOwner = %s AND username = %s;'
        cursor.execute(query, (group_name, user, to_add))
        data = cursor.fetchall()
        if data[0]['count'] > 0:
            #to_add already in group
            flash(to_add + " is already in " + group_name)
        else:
            query = 'SELECT Count(*) as count FROM Person WHERE username = %s;'
            cursor.execute(query,(to_add))
            data = cursor.fetchall()
            if data[0]['count'] == 1:
                query = 'INSERT INTO belong (groupName, groupOwner, username, accepted) VALUES (%s,%s,%s, False);'
                cursor.execute(query, (group_name, user, to_add))
                conn.commit()
            else:
                flash(to_add + " does not exist!")
    else:
        #to_add already in group
        flash("You need to be the owner of " + group_name)
    cursor.close()
    return redirect(url_for('group'))

@app.route("/tag/<photoID>")
def tag(photoID):
    cursor = conn.cursor();
    query = 'SELECT filePath FROM Photo WHERE photoID = %s;'
    cursor.execute(query, (photoID))
    filePath = cursor.fetchall()[0]["filePath"]
    query = 'SELECT * FROM Tag NATURAL JOIN Photo WHERE username = %s AND acceptedTag <> 1;'
    cursor.execute(query, (session["username"]))
    data = cursor.fetchall()
    # print(data)
    cursor.close()
    return render_template("add_tag.html", photoID = photoID, filePath = filePath, requests = data)


@app.route("/add_tag", methods = ["GET", "POST"])
def add_tag():
    username = session["username"]
    tagee = request.form["toTag"]
    photoID = request.form["photoID"]
    cursor = conn.cursor();

    #check if user you are adding is already being tagged
    query = 'SELECT Count(*) as count FROM Tag WHERE username = %s AND photoID = %s;'
    cursor.execute(query, (tagee, photoID))
    data = cursor.fetchall()
    print(data)
    if data[0]['count'] == 0:
        added = True if username == tagee else False
        query = 'INSERT INTO Tag(username, photoID, acceptedTag) VALUES (%s, %s, %s);'
        cursor.execute(query, (tagee, photoID, added))
        conn.commit()
    else:
        #to_add already in group
        flash(tagee + " is already being tagged")
    cursor.close()
    return redirect(url_for('tag', photoID = photoID))

@app.route('/accept_tag/<tagee>/<photoID>')
def accept_tag(tagee, photoID):
    cursor = conn.cursor()
    query = 'UPDATE Tag SET acceptedTag = 1 WHERE username = %s AND photoID = %s;'
    cursor.execute(query, (tagee, photoID))
    conn.commit()
    cursor.close()
    return redirect(url_for('tag', photoID = photoID))

@app.route('/reject_tag/<tagee>/<photoID>')
def reject_tag(tagee, photoID):
    cursor = conn.cursor()
    query = 'DELETE FROM Tag WHERE username = %s AND photoID = %s;'
    cursor.execute(query, (tagee, photoID))
    conn.commit()
    cursor.close()
    return redirect(url_for('tag', photoID = photoID))

@app.route('/search_tag')
def search_tag(user = session["username"], data = [], comments = [], likes = [], tages = [], viewableGroups = []):
    return render_template('search_tag.html', username=user, posts=data, comments = commentsData, likes = likes, tags = tags, viewableGroups=viewableGroups)

@app.route('/get_tag')
def get_tag():
    user = session['username']
    tag = request.form["tag_name"]
    cursor = conn.cursor()

    

    query = 'SELECT * FROM Photo NATURAL JOIN Tag WHERE username = %s AND photoID IN (SELECT photoID FROM Photo AS p WHERE p.photoID IN (SELECT photoID FROM Belong NATURAL JOIN Share WHERE username = %s) OR (allfollowers = 1 AND EXISTS (SELECT * FROM Follow WHERE followerUsername = %s and followeeUsername = p.photoOwner)) OR (p.photoOwner = %s) ORDER BY timestamp DESC)'
    cursor.execute(query, (tag, user, user, user))
    data = cursor.fetchall()

    query = "SELECT photoID, Count(*) AS count FROM Liked GROUP BY photoID"
    cursor.execute(query)
    likes = cursor.fetchall()

    query = 'SELECT username, photoID, commentText, timestamp FROM Comment ORDER BY timestamp ASC'
    cursor.execute(query)
    commentsData = cursor.fetchall()
    #all groups user can post too
    query = 'SELECT * FROM Belong WHERE username = %s AND accepted = 1'
    cursor.execute(query, (user))
    groups = cursor.fetchall()
    length = [ i for i in range(len(groups)) ]

    #prob needs to be fixed
    query = "SELECT * FROM Tag WHERE acceptedTag = 1;"
    cursor.execute(query)
    tags = cursor.fetchall()

    #need natural join for photoid but can join in the last query to avoid errors
    query = 'SELECT * FROM Belong NATURAL JOIN SHARE WHERE username = %s'
    cursor.execute(query, (user))
    viewableGroups = cursor.fetchall()

    cursor.close()
    return redirect(url_for('search_tag', user = user, data = [], comments = [], likes = [], tages = [], viewableGroups = []))

@app.route('/logout')
def logout():
    session.pop('username')
    return redirect('/')

app.secret_key = 'some key that you will never guess'
#Run the app on localhost port 5000
#debug = True -> you don't have to restart flask
#for changes to go through, TURN OFF FOR PRODUCTION
if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug = True)
