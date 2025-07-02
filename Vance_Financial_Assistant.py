from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Define models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    bills = db.relationship('Bill', backref='owner', lazy=True)
    credit_cards = db.relationship('CreditCard', backref='owner', lazy=True)

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(50))
    is_paid = db.Column(db.Boolean, default=False)
    recurring = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
class CreditCard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    last_four = db.Column(db.String(4), nullable=False)
    limit = db.Column(db.Float)
    current_balance = db.Column(db.Float, default=0)
    payment_due_date = db.Column(db.Date, nullable=False)
    minimum_payment = db.Column(db.Float)
    interest_rate = db.Column(db.Float)
    is_paid = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Create the database tables
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    upcoming_bills = Bill.query.filter_by(user_id=user.id, is_paid=False).order_by(Bill.due_date).all()
    credit_cards = CreditCard.query.filter_by(user_id=user.id).all()
    
    # Calculate upcoming payments within 7 days
    today = datetime.now().date()
    upcoming_week = today + timedelta(days=7)
    urgent_bills = [bill for bill in upcoming_bills if bill.due_date <= upcoming_week]
    
    return render_template(
        'dashboard.html', 
        user=user, 
        bills=upcoming_bills, 
        credit_cards=credit_cards,
        urgent_bills=urgent_bills
    )

@app.route('/bills', methods=['GET', 'POST'])
def bills():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        amount = float(request.form.get('amount'))
        due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
        category = request.form.get('category')
        recurring = 'recurring' in request.form
        
        new_bill = Bill(
            name=name,
            amount=amount,
            due_date=due_date,
            category=category,
            recurring=recurring,
            user_id=session['user_id']
        )
        db.session.add(new_bill)
        db.session.commit()
        flash('Bill added successfully!', 'success')
        return redirect(url_for('bills'))
    
    user_bills = Bill.query.filter_by(user_id=session['user_id']).order_by(Bill.due_date).all()
    return render_template('bills.html', bills=user_bills)

@app.route('/credit-cards', methods=['GET', 'POST'])
def credit_cards():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        last_four = request.form.get('last_four')
        limit = float(request.form.get('limit')) if request.form.get('limit') else None
        current_balance = float(request.form.get('current_balance'))
        payment_due_date = datetime.strptime(request.form.get('payment_due_date'), '%Y-%m-%d').date()
        minimum_payment = float(request.form.get('minimum_payment')) if request.form.get('minimum_payment') else None
        interest_rate = float(request.form.get('interest_rate')) if request.form.get('interest_rate') else None
        
        new_card = CreditCard(
            name=name,
            last_four=last_four,
            limit=limit,
            current_balance=current_balance,
            payment_due_date=payment_due_date,
            minimum_payment=minimum_payment,
            interest_rate=interest_rate,
            user_id=session['user_id']
        )
        db.session.add(new_card)
        db.session.commit()
        flash('Credit card added successfully!', 'success')
        return redirect(url_for('credit_cards'))
    
    user_cards = CreditCard.query.filter_by(user_id=session['user_id']).all()
    return render_template('credit_cards.html', credit_cards=user_cards)

@app.route('/mark_paid/<string:bill_type>/<int:item_id>')
def mark_paid(bill_type, item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if bill_type == 'bill':
        bill = Bill.query.get_or_404(item_id)
        if bill.user_id != session['user_id']:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('dashboard'))
        bill.is_paid = True
        db.session.commit()
        flash('Bill marked as paid!', 'success')
        return redirect(url_for('bills'))
    elif bill_type == 'credit_card':
        card = CreditCard.query.get_or_404(item_id)
        if card.user_id != session['user_id']:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('dashboard'))
        card.is_paid = True
        db.session.commit()
        flash('Credit card payment marked as paid!', 'success')
        return redirect(url_for('credit_cards'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/edit/bill/<int:bill_id>', methods=['POST'])
def edit_bill(bill_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    bill = Bill.query.get_or_404(bill_id)
    if bill.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        bill.name = request.form.get('name')
        bill.amount = float(request.form.get('amount'))
        bill.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
        bill.category = request.form.get('category')
        bill.recurring = 'recurring' in request.form
        
        db.session.commit()
        flash('Bill updated successfully!', 'success')
        
    return redirect(url_for('dashboard'))

@app.route('/edit/card/<int:card_id>', methods=['POST'])
def edit_card(card_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    card = CreditCard.query.get_or_404(card_id)
    if card.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        card.name = request.form.get('name')
        card.last_four = request.form.get('last_four')
        card.limit = float(request.form.get('limit')) if request.form.get('limit') else None
        card.current_balance = float(request.form.get('current_balance'))
        card.payment_due_date = datetime.strptime(request.form.get('payment_due_date'), '%Y-%m-%d').date()
        card.interest_rate = float(request.form.get('interest_rate')) if request.form.get('interest_rate') else None
        
        db.session.commit()
        flash('Credit card updated successfully!', 'success')
        
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)  # Example to run on port 8080 instead
