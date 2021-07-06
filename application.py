import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import time

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    person = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    tmpStockDict = db.execute("SELECT symbol, firmname, SUM(shares) FROM accounts WHERE user_id=:id GROUP BY symbol", id=session["user_id"])

    stockDict = []
    total = 0
    for stock in tmpStockDict:
        stockSymbol = stock["symbol"]
        stockNEWS = lookup(stock["symbol"]) # price, firmname, symbol
        total = total + stockNEWS["price"] * stock["SUM(shares)"]

        stock["total"] = usd(stock["SUM(shares)"]*stockNEWS["price"])
        stock["price"] = usd(stockNEWS["price"])

        stockDict.append(stock) # symbol, firmname, shares, price
    total = total + person[0]["cash"]

    return render_template("index.html", stockDict=stockDict, userCash=usd(person[0]["cash"]), total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # converting cash from list of dict into float when SELECT FROM finance.db
        tmpCash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        userCash = float(tmpCash[0]["cash"])
        # store the info of dict into a Dictionary
        stockDict = lookup(request.form.get("symbol"))

        # apologies
        if not request.form.get("symbol"):
            return apology("You cannot submit an empty stock's symbol")

        if not request.form.get("shares"):
            return apology("You cannot submit an empty quantity of shares")

        if not RepresentsInt(request.form.get("shares")):
            return apology("You have to input a positive integer of shares")

        if int(request.form.get("shares")) <= 0:
            return apology("You have to input a positive integer of shares")

        if not stockDict:
            return apology("Your input stock does not exist")

        # purchasing process
        price = float(stockDict["price"])
        cost = float(price) * float(request.form.get("shares"))
        if cost > userCash:
            return apology("You do not have enough money")
        else:
            # update user's cash
            userCash = userCash - cost
            localtime = time.asctime(time.localtime(time.time()))
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=userCash, id=session["user_id"])
            # update his stock account
            db.execute("INSERT INTO accounts (symbol, firmname, shares, user_id) VALUES (?,?,?,?)", stockDict["symbol"], stockDict["name"], request.form.get("shares"), session["user_id"])
            # update history
            db.execute("INSERT INTO history (user_id, symbol, price, shares, time) VALUES(?,?,?,?,?)", session["user_id"], stockDict["symbol"], usd(price), request.form.get("shares"), localtime)
            return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    histories = db.execute("SELECT symbol, shares, price, time FROM history WHERE user_id=:id", id=session["user_id"])
    return render_template("history.html", histories=histories)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST
    if request.method == "POST":
        stockDict = lookup(request.form.get("symbol"))
        if not stockDict:
            return apology("You must type the correct symbol of a stock.", 403)
        return render_template("quoted.html", name=stockDict["name"], symbol=stockDict["symbol"], price=usd(stockDict["price"]))

    # User reached route via GET
    if request.method == "GET":
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # Forget any user_id & pw
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        existedUsers = db.execute("SELECT username FROM users WHERE username = :username", username=request.form.get("username"))

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure confirmation password was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password again", 403)

        # Ensure it's the only username
        elif existedUsers:
            return apology("The username is used already. Try a new one.", 403)

        elif (request.form.get("confirmation") != request.form.get("password")):
            return apology("the confirmation password must be equal to password", 403)

        # Insert information to db
        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, hash, cash) VALUES(?, ?, ?)", username, hash, 10000)

        # Log in automatically after registered
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                           username=request.form.get("username"))
        session["user_id"] = rows[0]["id"]

        # Registered and loged into the mainpage ("/")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")



@app.route("/change", methods=["GET", "POST"])
@login_required
def change():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        user = db.execute("SELECT hash FROM users WHERE id = :id", id=session["user_id"])

        # Ensure current password was submitted
        if not request.form.get("password"):
            return apology("must provide current password", 403)

        # Ensure new password was submitted
        if not request.form.get("new"):
            return apology("must provide new password", 403)

        # check current pw
        if not check_password_hash(user[0]["hash"], request.form.get("password")):
            return apology("invalid password", 403)

        # check current pw and new pw
        if (request.form.get("confirmation") == request.form.get("password")):
            return apology("You cannot submit the same password", 403)

        # Insert new pw to db
        hash = generate_password_hash(request.form.get("new"))
        db.execute("UPDATE users SET hash=:hash WHERE id=:id", hash=hash, id=session["user_id"])

        # Registered and loged into the mainpage ("/")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("change.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # render apology if user doesnt make any choice or provide an empty number of shares/nonpositive number of shares
        if request.form.get("symbol") == "Symbol":
            return apology("You have to select a stock")
        if not request.form.get("shares"):
            return apology("You cannot leave the shares blank")

        if not RepresentsInt(request.form.get("shares")):
            return apology("You have to input a positive integer of shares")

        if int(request.form.get("shares")) <= 0:
            return apology("You have to input a positive integer of shares")

        # look for the price
        desiredStock = lookup(request.form.get("symbol")) # name symbol price
        desiredStockPrice = desiredStock["price"]

        # user's current cash
        user = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        userCash = user[0]["cash"]

        # user's current number of shares
        accountStockList = db.execute("SELECT symbol, SUM(shares), firmname FROM accounts WHERE user_id=:id GROUP BY symbol", id=session["user_id"])
        for stock in accountStockList:
            if request.form.get("symbol") == stock["symbol"]:
                userShares = stock["SUM(shares)"]
                firmname = stock["firmname"]

        # render apology if user doesnt have enough shares
        if int(request.form.get("shares")) > userShares:
            return apology("You don't have enough shares")

        # update cash & number of shares
        cost = desiredStockPrice * int(request.form.get("shares"))
        userCash = userCash + cost
        print((userShares - int(request.form.get("shares"))))
        userShares = userShares - int(request.form.get("shares"))
        histShares = "-"+request.form.get("shares")

        # transacted time
        localtime = time.asctime(time.localtime(time.time()))

        # update db
        if userShares == 0:
            # delete row where symbol = desired
            db.execute("DELETE FROM accounts WHERE symbol=:symbol AND user_id=:id", symbol=request.form.get("symbol"), id=session["user_id"])
            # update user's current cash
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=userCash, id=session["user_id"])
        else:
            db.execute("DELETE FROM accounts WHERE symbol=:symbol AND user_id=:id", symbol=request.form.get("symbol"), id=session["user_id"])
            db.execute("INSERT INTO accounts (symbol, firmname, shares, user_id) VALUES (?,?,?,?)", request.form.get("symbol"), firmname, userShares, session["user_id"])
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=userCash, id=session["user_id"])
        # update history
        db.execute("INSERT INTO history (user_id, symbol, price, shares, time) VALUES(?,?,?,?,?)", session["user_id"], request.form.get("symbol"), usd(desiredStockPrice), histShares, localtime)
        return redirect("/")

    else:
        stockDict = db.execute("SELECT symbol, SUM(shares) FROM accounts WHERE user_id=:id GROUP BY symbol", id=session["user_id"])
        stockSymbol = []
        for stock in stockDict:
            stockSymbol.append(stock["symbol"])
        return render_template("sell.html", symbols=stockSymbol)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

def RepresentsInt(s):
    try:
        int(s)
        return True
    except ValueError:
        return False