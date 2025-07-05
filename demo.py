from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import shutil
import json
import tempfile
import calendar

# FORCE THE CORRECT WORKING DIRECTORY
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print(f"[SUCCESS] Working directory changed to: {script_dir}")
print(f"[SUCCESS] Current working directory is now: {os.getcwd()}")

# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = 'vance-financial-secret-key-change-this-in-production'  # Fixed secret key
# Use absolute path for database
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'finance_tracker.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print(f"[SUCCESS] Database will be created at: {db_path}")

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
    subscriptions = db.relationship('Subscription', backref='owner', lazy=True)
    loans = db.relationship('Loan', backref='owner', lazy=True)
    income_sources = db.relationship('IncomeSource', backref='owner', lazy=True)

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
    auto_pay_minimum = db.Column(db.Boolean, default=False)
    auto_payment_amount = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    billing_cycle = db.Column(db.String(20), nullable=False)  # Monthly, Yearly, Weekly
    next_billing_date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(50))  # Entertainment, Software, News, etc.
    is_active = db.Column(db.Boolean, default=True)
    auto_renew = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    loan_type = db.Column(db.String(50), nullable=False)  # Personal, Auto, Mortgage, Student
    principal_amount = db.Column(db.Float, nullable=False)
    current_balance = db.Column(db.Float, nullable=False)
    monthly_payment = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float)
    next_payment_date = db.Column(db.Date, nullable=False)
    term_months = db.Column(db.Integer)  # Loan term in months
    is_paid_off = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class IncomeSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "Your Salary", "Wife's Salary"
    amount = db.Column(db.Float, nullable=False)  # Per payment amount
    frequency = db.Column(db.String(20), nullable=False)  # 'bimonthly', 'biweekly'
    # For bimonthly (twice monthly): payment_day_1 and payment_day_2
    payment_day_1 = db.Column(db.Integer)  # e.g., 15
    payment_day_2 = db.Column(db.Integer)  # e.g., 30 (or last day of month)
    # For biweekly: next_payment_date and we calculate subsequent dates
    next_payment_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Function to backup database
def backup_database():
    """Create a backup of the database"""
    try:
        # Get the directory where this Python file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backups_dir = os.path.join(current_dir, 'backups')
        
        # Create backups directory if it doesn't exist
        if not os.path.exists(backups_dir):
            os.makedirs(backups_dir)
            print(f"Created backups directory at: {backups_dir}")
            
        # Get the path to the database file in the current project directory
        db_path = os.path.join(current_dir, 'finance_tracker.db')
        print(f"Looking for database at: {db_path}")
        
        # Check if database file exists
        if os.path.exists(db_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"finance_tracker_backup_{timestamp}.db"
            backup_path = os.path.join(backups_dir, backup_filename)
            
            # Check if source file is readable
            if os.access(db_path, os.R_OK):
                shutil.copy2(db_path, backup_path)
                print(f"Database backed up to: {backup_path}")
                
                # Verify backup was created successfully
                if os.path.exists(backup_path) and os.path.getsize(backup_path) > 0:
                    print(f"Backup verified successfully, size: {os.path.getsize(backup_path)} bytes")
                    return True
                else:
                    print("Backup file was not created or is empty")
                    return False
            else:
                print("Database file exists but is not readable")
                return False
        else:
            print(f"Database file not found at: {db_path}")
            # During startup, this is normal, so don't treat as failure
            return True
            
    except Exception as e:
        print(f"Backup failed with error: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return False

# Function to safely migrate database
def safe_migrate_database():
    """Safely migrate database without losing data"""
    try:
        # Get the correct path to the database
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'finance_tracker.db')
        
        # Only attempt backup if database actually exists and has content
        if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
            print("Existing database found, creating backup before migration...")
            backup_database()
        else:
            print("No existing database found or database is empty, skipping backup")
        
        # Then try migration
        with db.engine.connect() as connection:
            # Check and add columns safely for credit card table
            result = connection.execute(db.text("PRAGMA table_info(credit_card)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'auto_pay_minimum' not in columns:
                connection.execute(db.text('ALTER TABLE credit_card ADD COLUMN auto_pay_minimum BOOLEAN DEFAULT 0'))
                print("Added auto_pay_minimum column")
                
            if 'auto_payment_amount' not in columns:
                connection.execute(db.text('ALTER TABLE credit_card ADD COLUMN auto_payment_amount REAL'))
                print("Added auto_payment_amount column")
            
            # Check if income_source table exists
            result = connection.execute(db.text("SELECT name FROM sqlite_master WHERE type='table' AND name='income_source'"))
            if not result.fetchone():
                print("Creating income_source table...")
                # The table will be created by db.create_all()
            
            connection.commit()
            print("Migration completed successfully")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        print(f"Migration traceback: {traceback.format_exc()}")

# Utility functions for income calculations
def calculate_monthly_income(user_id):
    """Calculate estimated monthly income for a user"""
    income_sources = IncomeSource.query.filter_by(user_id=user_id, is_active=True).all()
    monthly_total = 0
    
    for source in income_sources:
        if source.frequency == 'bimonthly':
            # Twice monthly = 24 payments per year
            monthly_total += source.amount * 2
        elif source.frequency == 'biweekly':
            # Every two weeks = 26 payments per year / 12 months
            monthly_total += source.amount * 26 / 12
    
    return monthly_total

def calculate_monthly_expenses(user_id):
    """Calculate estimated monthly expenses"""
    # Get recurring bills
    bills = Bill.query.filter_by(user_id=user_id, recurring=True).all()
    bill_total = sum(bill.amount for bill in bills)
    
    # Get monthly subscriptions
    subscriptions = Subscription.query.filter_by(user_id=user_id, is_active=True).all()
    subscription_total = 0
    for sub in subscriptions:
        if sub.billing_cycle == 'Monthly':
            subscription_total += sub.amount
        elif sub.billing_cycle == 'Yearly':
            subscription_total += sub.amount / 12
        elif sub.billing_cycle == 'Weekly':
            subscription_total += sub.amount * 4.33  # Average weeks per month
    
    # Get loan payments
    loans = Loan.query.filter_by(user_id=user_id, is_paid_off=False).all()
    loan_total = sum(loan.monthly_payment for loan in loans)
    
    # Get credit card minimum payments
    cards = CreditCard.query.filter_by(user_id=user_id).all()
    card_total = sum(card.minimum_payment for card in cards if card.minimum_payment)
    
    return {
        'bills': bill_total,
        'subscriptions': subscription_total,
        'loans': loan_total,
        'credit_cards': card_total,
        'total': bill_total + subscription_total + loan_total + card_total
    }

def get_future_income_dates(income_source, start_date, end_date):
    """Get list of income dates for a source between start and end dates"""
    dates = []
    current_date = start_date
    
    if income_source.frequency == 'bimonthly':
        # Payment on specific days of each month
        while current_date <= end_date:
            year = current_date.year
            month = current_date.month
            
            # First payment day
            if income_source.payment_day_1:
                try:
                    pay_date_1 = datetime(year, month, income_source.payment_day_1).date()
                    if start_date <= pay_date_1 <= end_date:
                        dates.append(pay_date_1)
                except ValueError:
                    # Handle invalid dates (e.g., Feb 30)
                    pass
            
            # Second payment day
            if income_source.payment_day_2:
                try:
                    if income_source.payment_day_2 == 31:
                        # Last day of month
                        last_day = calendar.monthrange(year, month)[1]
                        pay_date_2 = datetime(year, month, last_day).date()
                    else:
                        pay_date_2 = datetime(year, month, income_source.payment_day_2).date()
                    
                    if start_date <= pay_date_2 <= end_date:
                        dates.append(pay_date_2)
                except ValueError:
                    pass
            
            # Move to next month
            if month == 12:
                current_date = datetime(year + 1, 1, 1).date()
            else:
                current_date = datetime(year, month + 1, 1).date()
    
    elif income_source.frequency == 'biweekly':
        # Every two weeks from next_payment_date
        if income_source.next_payment_date:
            pay_date = income_source.next_payment_date
            while pay_date <= end_date:
                if pay_date >= start_date:
                    dates.append(pay_date)
                pay_date += timedelta(days=14)
    
    return sorted(dates)

# Add this helper function near the top of your file, after the imports and before the routes

def add_months(date, months):
    """Safely add months to a date, handling month-end edge cases"""
    import calendar
    
    # Calculate target year and month
    total_months = date.month + months
    target_year = date.year + (total_months - 1) // 12
    target_month = ((total_months - 1) % 12) + 1
    
    # Get the last day of the target month
    last_day_of_target_month = calendar.monthrange(target_year, target_month)[1]
    
    # Use the minimum of current day or last day of target month
    target_day = min(date.day, last_day_of_target_month)
    
    return date.replace(year=target_year, month=target_month, day=target_day)

# Add these demo functions after your existing utility functions

def create_demo_data():
    """Create comprehensive demo data for showcase"""
    from werkzeug.security import generate_password_hash
    
    # Create demo user
    demo_user = User(
        username='demo_user',
        email='demo@vancefinancial.com',
        password_hash=generate_password_hash('demo123')
    )
    
    try:
        # Check if demo user already exists
        existing_demo = User.query.filter_by(username='demo_user').first()
        if existing_demo:
            # Clear existing demo data
            Bill.query.filter_by(user_id=existing_demo.id).delete()
            CreditCard.query.filter_by(user_id=existing_demo.id).delete()
            Subscription.query.filter_by(user_id=existing_demo.id).delete()
            Loan.query.filter_by(user_id=existing_demo.id).delete()
            IncomeSource.query.filter_by(user_id=existing_demo.id).delete()
            demo_user_id = existing_demo.id
        else:
            db.session.add(demo_user)
            db.session.flush()
            demo_user_id = demo_user.id
        
        # Today's date for realistic demo data
        today = datetime.now().date()
        
        # Create Income Sources
        income_sources = [
            IncomeSource(
                name="Your Salary (Software Engineer)",
                amount=3250.00,  # Bi-monthly
                frequency='bimonthly',
                payment_day_1=15,
                payment_day_2=30,
                is_active=True,
                user_id=demo_user_id
            ),
            IncomeSource(
                name="Spouse's Salary (Teacher)",
                amount=1850.00,  # Bi-weekly
                frequency='biweekly',
                next_payment_date=today + timedelta(days=3),  # Next Friday
                is_active=True,
                user_id=demo_user_id
            )
        ]
        
        # Create Bills
        bills = [
            Bill(
                name="Mortgage Payment",
                amount=2150.00,
                due_date=today.replace(day=1) + timedelta(days=32),
                category="Housing",
                is_paid=False,
                recurring=True,
                user_id=demo_user_id
            ),
            Bill(
                name="Electric Bill",
                amount=145.50,
                due_date=today + timedelta(days=8),
                category="Utilities",
                is_paid=False,
                recurring=True,
                user_id=demo_user_id
            ),
            Bill(
                name="Water & Sewer",
                amount=89.25,
                due_date=today + timedelta(days=12),
                category="Utilities",
                is_paid=False,
                recurring=True,
                user_id=demo_user_id
            ),
            Bill(
                name="Internet Service",
                amount=79.99,
                due_date=today + timedelta(days=5),
                category="Utilities",
                is_paid=False,
                recurring=True,
                user_id=demo_user_id
            ),
            Bill(
                name="Car Insurance",
                amount=165.00,
                due_date=today + timedelta(days=18),
                category="Insurance",
                is_paid=False,
                recurring=True,
                user_id=demo_user_id
            ),
            Bill(
                name="Health Insurance",
                amount=425.00,
                due_date=today + timedelta(days=25),
                category="Insurance",
                is_paid=False,
                recurring=True,
                user_id=demo_user_id
            )
        ]
        
        # Create Credit Cards
        credit_cards = [
            CreditCard(
                name="Chase Freedom Unlimited",
                last_four="4892",
                limit=15000.00,
                current_balance=2845.67,
                payment_due_date=today + timedelta(days=14),
                minimum_payment=85.00,
                interest_rate=18.99,
                is_paid=False,
                auto_pay_minimum=True,
                user_id=demo_user_id
            ),
            CreditCard(
                name="Capital One Venture",
                last_four="7251",
                limit=8500.00,
                current_balance=1256.34,
                payment_due_date=today + timedelta(days=21),
                minimum_payment=35.00,
                interest_rate=21.49,
                is_paid=False,
                auto_pay_minimum=False,
                auto_payment_amount=200.00,
                user_id=demo_user_id
            ),
            CreditCard(
                name="Amazon Prime Rewards",
                last_four="9834",
                limit=5000.00,
                current_balance=687.92,
                payment_due_date=today + timedelta(days=9),
                minimum_payment=25.00,
                interest_rate=24.74,
                is_paid=False,
                auto_pay_minimum=True,
                user_id=demo_user_id
            )
        ]
        
        # Create Subscriptions
        subscriptions = [
            Subscription(
                name="Netflix Premium",
                amount=15.99,
                billing_cycle="Monthly",
                next_billing_date=today + timedelta(days=6),
                category="Entertainment",
                is_active=True,
                auto_renew=True,
                user_id=demo_user_id
            ),
            Subscription(
                name="Spotify Family",
                amount=15.99,
                billing_cycle="Monthly",
                next_billing_date=today + timedelta(days=11),
                category="Entertainment",
                is_active=True,
                auto_renew=True,
                user_id=demo_user_id
            ),
            Subscription(
                name="Adobe Creative Cloud",
                amount=52.99,
                billing_cycle="Monthly",
                next_billing_date=today + timedelta(days=19),
                category="Software",
                is_active=True,
                auto_renew=True,
                user_id=demo_user_id
            ),
            Subscription(
                name="Amazon Prime",
                amount=139.00,
                billing_cycle="Yearly",
                next_billing_date=today + timedelta(days=95),
                category="Shopping",
                is_active=True,
                auto_renew=True,
                user_id=demo_user_id
            ),
            Subscription(
                name="Office 365 Family",
                amount=99.99,
                billing_cycle="Yearly",
                next_billing_date=today + timedelta(days=203),
                category="Software",
                is_active=True,
                auto_renew=True,
                user_id=demo_user_id
            ),
            Subscription(
                name="Gym Membership",
                amount=45.00,
                billing_cycle="Monthly",
                next_billing_date=today + timedelta(days=7),
                category="Health",
                is_active=True,
                auto_renew=True,
                user_id=demo_user_id
            )
        ]
        
        # Create Loans
        loans = [
            Loan(
                name="Honda Civic Car Loan",
                loan_type="Auto",
                principal_amount=28500.00,
                current_balance=18750.00,
                monthly_payment=485.00,
                interest_rate=3.99,
                next_payment_date=today + timedelta(days=16),
                term_months=60,
                is_paid_off=False,
                user_id=demo_user_id
            ),
            Loan(
                name="Student Loan - Federal",
                loan_type="Student",
                principal_amount=45000.00,
                current_balance=32100.00,
                monthly_payment=325.00,
                interest_rate=4.53,
                next_payment_date=today + timedelta(days=23),
                term_months=120,
                is_paid_off=False,
                user_id=demo_user_id
            )
        ]
        
        # Add all demo data to session
        for income in income_sources:
            db.session.add(income)
        for bill in bills:
            db.session.add(bill)
        for card in credit_cards:
            db.session.add(card)
        for sub in subscriptions:
            db.session.add(sub)
        for loan in loans:
            db.session.add(loan)
        
        db.session.commit()
        return demo_user_id
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating demo data: {e}")
        return None

@app.route('/demo')
def demo_page():
    """Demo page showing off the application features"""
    return render_template('demo.html')

@app.route('/demo/login')
def demo_login():
    """Automatically log in as demo user"""
    try:
        # Create or refresh demo data
        demo_user_id = create_demo_data()
        
        if demo_user_id:
            # Log in as demo user
            session['user_id'] = demo_user_id
            session['demo_mode'] = True  # Flag to indicate demo mode
            flash('Welcome to the Vance Finance Demo!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Error setting up demo. Please try again.', 'danger')
            return redirect(url_for('demo_page'))
            
    except Exception as e:
        flash(f'Demo setup error: {str(e)}', 'danger')
        return redirect(url_for('demo_page'))

@app.route('/demo/reset')
def demo_reset():
    """Reset demo data to original state"""
    if 'demo_mode' in session:
        try:
            demo_user_id = create_demo_data()
            if demo_user_id:
                flash('Demo data has been reset to original state!', 'info')
            else:
                flash('Error resetting demo data.', 'danger')
        except Exception as e:
            flash(f'Error resetting demo: {str(e)}', 'danger')
    else:
        flash('Demo reset is only available in demo mode.', 'warning')
    
    return redirect(url_for('dashboard'))

@app.route('/demo/exit')
def demo_exit():
    """Exit demo mode"""
    session.pop('user_id', None)
    session.pop('demo_mode', None)
    flash('You have exited demo mode.', 'info')
    return redirect(url_for('demo_page'))

# Create the database tables and migrate
with app.app_context():
    db.create_all()
    safe_migrate_database()

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('demo_page'))  # Changed from login to demo_page
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"Login attempt - Username: {username}")  # Debug
        
        user = User.query.filter_by(username=username).first()
        print(f"User found: {user is not None}")  # Debug
        
        if user:
            password_valid = check_password_hash(user.password_hash, password)
            print(f"Password check: {password_valid}")  # Debug
            
            if password_valid:
                session['user_id'] = user.id
                print(f"Session set: {session.get('user_id')}")  # Debug
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
        
        print(f"Registration attempt - Username: {username}, Email: {email}")  # Debug
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        # Backup before creating new user
        backup_database()
        
        # Create new user
        password_hash = generate_password_hash(password)
        print(f"Created password hash: {password_hash[:50]}...")  # Debug (first 50 chars)
        
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            print(f"User created successfully with ID: {new_user.id}")  # Debug
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Error creating user: {e}")  # Debug
            db.session.rollback()
            flash('Error creating account. Please try again.', 'danger')
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        flash('User not found. Please log in again.', 'danger')
        return redirect(url_for('login'))
    
    upcoming_bills = Bill.query.filter_by(user_id=user.id, is_paid=False).order_by(Bill.due_date).all()
    credit_cards = CreditCard.query.filter_by(user_id=user.id).all()
    
    # Calculate upcoming payments within 7 days
    today = datetime.now().date()
    upcoming_week = today + timedelta(days=7)
    urgent_bills = [bill for bill in upcoming_bills if bill.due_date <= upcoming_week]
    
    # Calculate financial summary
    monthly_income = calculate_monthly_income(user.id)
    monthly_expenses = calculate_monthly_expenses(user_id=user.id)
    
    # Calculate debt-to-income ratio
    debt_to_income_ratio = 0
    if monthly_income > 0:
        debt_to_income_ratio = (monthly_expenses['total'] / monthly_income) * 100
    
    # Get income sources for next payment info
    income_sources = IncomeSource.query.filter_by(user_id=user.id, is_active=True).all()
    next_income_dates = []
    for source in income_sources:
        future_dates = get_future_income_dates(source, today, today + timedelta(days=30))
        if future_dates:
            next_date = future_dates[0]
            days_away = (next_date - today).days
            next_income_dates.append({
                'source': source.name,
                'amount': source.amount,
                'date': next_date,
                'days_away': days_away
            })
    
    # Sort by date
    next_income_dates.sort(key=lambda x: x['date'])
    
    return render_template(
        'dashboard.html', 
        user=user, 
        bills=upcoming_bills, 
        credit_cards=credit_cards,
        urgent_bills=urgent_bills,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        debt_to_income_ratio=debt_to_income_ratio,
        next_income_dates=next_income_dates[:5],  # Show next 5 payments
        today=today  # Keep this for any other template usage
    )

@app.route('/income', methods=['GET', 'POST'])
def income():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        backup_database()
        
        name = request.form.get('name')
        amount = float(request.form.get('amount'))
        frequency = request.form.get('frequency')
        
        new_income = IncomeSource(
            name=name,
            amount=amount,
            frequency=frequency,
            user_id=session['user_id']
        )
        
        if frequency == 'bimonthly':
            new_income.payment_day_1 = int(request.form.get('payment_day_1'))
            new_income.payment_day_2 = int(request.form.get('payment_day_2'))
        elif frequency == 'biweekly':
            new_income.next_payment_date = datetime.strptime(request.form.get('next_payment_date'), '%Y-%m-%d').date()
        
        try:
            db.session.add(new_income)
            db.session.commit()
            flash('Income source added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error adding income source. Please try again.', 'danger')
            print(f"Error adding income: {e}")
        
        return redirect(url_for('income'))
    
    user_income = IncomeSource.query.filter_by(user_id=session['user_id']).all()
    
    # Calculate future income dates for each source
    today = datetime.now().date()
    end_date = today + timedelta(days=90)  # Next 3 months
    
    for source in user_income:
        source.future_dates = get_future_income_dates(source, today, end_date)[:6]  # Next 6 payments
    
    return render_template('income.html', income_sources=user_income)

@app.route('/overview')
def overview():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get date range from request or default to next 3 months
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=90)
    
    # Get all income sources
    income_sources = IncomeSource.query.filter_by(user_id=session['user_id'], is_active=True).all()
    
    # Get all recurring expenses
    bills = Bill.query.filter_by(user_id=session['user_id'], recurring=True).all()
    subscriptions = Subscription.query.filter_by(user_id=session['user_id'], is_active=True).all()
    loans = Loan.query.filter_by(user_id=session['user_id'], is_paid_off=False).all()
    credit_cards = CreditCard.query.filter_by(user_id=session['user_id']).all()
    
    # Build comprehensive timeline
    timeline = []
    
    # Add income events
    for source in income_sources:
        income_dates = get_future_income_dates(source, start_date, end_date)
        for date in income_dates:
            timeline.append({
                'date': date,
                'type': 'income',
                'description': source.name,
                'amount': source.amount,
                'category': 'Income'
            })
    
    # Add bill expenses (recurring)
    for bill in bills:
        current_date = start_date
        while current_date <= end_date:
            # For simplicity, assume monthly bills
            if current_date >= bill.due_date or current_date.day == bill.due_date.day:
                timeline.append({
                    'date': current_date,
                    'type': 'expense',
                    'description': bill.name,
                    'amount': -bill.amount,
                    'category': 'Bills'
                })
            
            # Move to next month using safe helper function
            current_date = add_months(current_date, 1)
    
    # Add subscription expenses
    for sub in subscriptions:
        current_date = sub.next_billing_date
        interval_days = 30 if sub.billing_cycle == 'Monthly' else (365 if sub.billing_cycle == 'Yearly' else 7)
        
        while current_date <= end_date:
            if current_date >= start_date:
                timeline.append({
                    'date': current_date,
                    'type': 'expense',
                    'description': sub.name,
                    'amount': -sub.amount,
                    'category': 'Subscriptions'
                })
            current_date += timedelta(days=interval_days)
    
    # Add loan payments
    for loan in loans:
        current_date = loan.next_payment_date
        while current_date <= end_date:
            if current_date >= start_date:
                timeline.append({
                    'date': current_date,
                    'type': 'expense',
                    'description': f"{loan.name} Payment",
                    'amount': -loan.monthly_payment,
                    'category': 'Loans'
                })
            
            # Move to next month using safe helper function
            current_date = add_months(current_date, 1)
    
    # Add credit card minimum payments
    for card in credit_cards:
        if card.minimum_payment:
            current_date = card.payment_due_date
            while current_date <= end_date:
                if current_date >= start_date:
                    timeline.append({
                        'date': current_date,
                        'type': 'expense',
                        'description': f"{card.name} Min Payment",
                        'amount': -card.minimum_payment,
                        'category': 'Credit Cards'
                    })
                
                # Move to next month using safe helper function
                current_date = add_months(current_date, 1)
    
    # Sort timeline by date
    timeline.sort(key=lambda x: x['date'])
    
    # Calculate running balance
    running_balance = 0
    for item in timeline:
        running_balance += item['amount']
        item['running_balance'] = running_balance
    
    # Calculate summary stats
    total_income = sum(item['amount'] for item in timeline if item['type'] == 'income')
    total_expenses = sum(-item['amount'] for item in timeline if item['type'] == 'expense')
    net_income = total_income - total_expenses
    
    return render_template('overview.html',
                         timeline=timeline,
                         start_date=start_date,
                         end_date=end_date,
                         total_income=total_income,
                         total_expenses=total_expenses,
                         net_income=net_income)

@app.route('/bills', methods=['GET', 'POST'])
def bills():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Backup before adding new bill
        backup_database()
        
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
        
        try:
            db.session.add(new_bill)
            db.session.commit()
            flash('Bill added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error adding bill. Please try again.', 'danger')
            print(f"Error adding bill: {e}")
            
        return redirect(url_for('bills'))
    
    # Get all bills and separate by category
    user_bills = Bill.query.filter_by(user_id=session['user_id']).order_by(Bill.due_date).all()
    user_subscriptions = Subscription.query.filter_by(user_id=session['user_id'], is_active=True).order_by(Subscription.next_billing_date).all()
    user_loans = Loan.query.filter_by(user_id=session['user_id'], is_paid_off=False).order_by(Loan.next_payment_date).all()
    
    return render_template('bills.html', bills=user_bills, subscriptions=user_subscriptions, loans=user_loans)

@app.route('/subscriptions', methods=['GET', 'POST'])
def subscriptions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Backup before adding new subscription
        backup_database()
        
        name = request.form.get('name')
        amount = float(request.form.get('amount'))
        billing_cycle = request.form.get('billing_cycle')
        next_billing_date = datetime.strptime(request.form.get('next_billing_date'), '%Y-%m-%d').date()
        category = request.form.get('category')
        auto_renew = 'auto_renew' in request.form
        
        new_subscription = Subscription(
            name=name,
            amount=amount,
            billing_cycle=billing_cycle,
            next_billing_date=next_billing_date,
            category=category,
            auto_renew=auto_renew,
            user_id=session['user_id']
        )
        
        try:
            db.session.add(new_subscription)
            db.session.commit()
            flash('Subscription added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error adding subscription. Please try again.', 'danger')
            print(f"Error adding subscription: {e}")
            
        return redirect(url_for('subscriptions'))
    
    user_subscriptions = Subscription.query.filter_by(user_id=session['user_id']).order_by(Subscription.next_billing_date).all()
    return render_template('subscriptions.html', subscriptions=user_subscriptions)

@app.route('/loans', methods=['GET', 'POST'])
def loans():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Backup before adding new loan
        backup_database()
        
        name = request.form.get('name')
        loan_type = request.form.get('loan_type')
        principal_amount = float(request.form.get('principal_amount'))
        current_balance = float(request.form.get('current_balance'))
        monthly_payment = float(request.form.get('monthly_payment'))
        interest_rate = float(request.form.get('interest_rate')) if request.form.get('interest_rate') else None
        next_payment_date = datetime.strptime(request.form.get('next_payment_date'), '%Y-%m-%d').date()
        term_months = int(request.form.get('term_months')) if request.form.get('term_months') else None
        
        new_loan = Loan(
            name=name,
            loan_type=loan_type,
            principal_amount=principal_amount,
            current_balance=current_balance,
            monthly_payment=monthly_payment,
            interest_rate=interest_rate,
            next_payment_date=next_payment_date,
            term_months=term_months,
            user_id=session['user_id']
        )
        
        try:
            db.session.add(new_loan)
            db.session.commit()
            flash('Loan added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error adding loan. Please try again.', 'danger')
            print(f"Error adding loan: {e}")
            
        return redirect(url_for('loans'))
    
    user_loans = Loan.query.filter_by(user_id=session['user_id']).order_by(Loan.next_payment_date).all()
    return render_template('loans.html', loans=user_loans)

@app.route('/credit-cards', methods=['GET', 'POST'])
def credit_cards():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Backup before adding new credit card
        backup_database()
        
        name = request.form.get('name')
        last_four = request.form.get('last_four')
        limit = float(request.form.get('limit')) if request.form.get('limit') else None
        current_balance = float(request.form.get('current_balance'))
        interest_rate = float(request.form.get('interest_rate')) if request.form.get('interest_rate') else None
        minimum_payment = float(request.form.get('minimum_payment')) if request.form.get('minimum_payment') else None
        auto_pay_minimum = ('auto_pay_minimum' in request.form)
        auto_payment_amount = float(request.form.get('auto_payment_amount')) if request.form.get('auto_payment_amount') and not auto_pay_minimum else None
        
        # Handle the due day
        if 'due_day' in request.form:
            due_day = int(request.form.get('due_day'))
            # Calculate the next occurrence of this day
            today = datetime.now().date()
            current_year = today.year
            current_month = today.month
            
            # Try to set for current month first
            try:
                payment_due_date = datetime(current_year, current_month, due_day).date()
            except ValueError:
                # Handle invalid day for month (e.g., February 30)
                # Set to last day of the month
                if current_month == 12:
                    next_month = 1
                    next_year = current_year + 1
                else:
                    next_month = current_month + 1
                    next_year = current_year
                
                payment_due_date = datetime(next_year, next_month, 1).date() - timedelta(days=1)
            
            # If the day has already passed this month, move to next month
            if payment_due_date < today:
                if current_month == 12:
                    payment_due_date = datetime(current_year + 1, 1, due_day).date()
                else:
                    try:
                        payment_due_date = datetime(current_year, current_month + 1, due_day).date()
                    except ValueError:
                        # Handle invalid day for next month
                        if current_month + 1 == 12:
                            next_month = 1
                            next_year = current_year + 1
                        else:
                            next_month = current_month + 2
                            next_year = current_year
                        
                        payment_due_date = datetime(next_year, next_month, 1).date() - timedelta(days=1)
        else:
            # If no due_day provided, use the payment_due_date from form (backwards compatibility)
            payment_due_date = datetime.strptime(request.form.get('payment_due_date'), '%Y-%m-%d').date()
        
        new_card = CreditCard(
            name=name,
            last_four=last_four,
            limit=limit,
            current_balance=current_balance,
            payment_due_date=payment_due_date,
            interest_rate=interest_rate,
            minimum_payment=minimum_payment,
            auto_pay_minimum=auto_pay_minimum,
            auto_payment_amount=auto_payment_amount,
            user_id=session['user_id']
        )
        
        try:
            db.session.add(new_card)
            db.session.commit()
            flash('Credit card added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error adding credit card. Please try again.', 'danger')
            print(f"Error adding credit card: {e}")
            
        return redirect(url_for('credit_cards'))
    
    user_cards = CreditCard.query.filter_by(user_id=session['user_id']).all()
    
    # Calculate summary statistics
    total_limit = sum(card.limit for card in user_cards if card.limit)
    total_balance = sum(card.current_balance for card in user_cards if card.current_balance)
    total_available = total_limit - total_balance
    total_min_payments = sum(card.minimum_payment for card in user_cards if card.minimum_payment)
    cards_with_rate = [card for card in user_cards if card.interest_rate]
    avg_interest_rate = sum(card.interest_rate for card in cards_with_rate) / len(cards_with_rate) if cards_with_rate else 0
    
    # Calculate overall utilization
    overall_utilization = (total_balance / total_limit * 100) if total_limit > 0 else 0
    
    return render_template('credit_cards.html', 
                         credit_cards=user_cards,
                         total_limit=total_limit,
                         total_balance=total_balance,
                         total_available=total_available,
                         total_min_payments=total_min_payments,
                         avg_interest_rate=avg_interest_rate,
                         overall_utilization=overall_utilization)

@app.route('/mark_paid/<string:bill_type>/<int:item_id>')
def mark_paid(bill_type, item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Backup before marking as paid
    backup_database()
    
    if bill_type == 'bill':
        bill = Bill.query.get_or_404(item_id)
        if bill.user_id != session['user_id']:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('dashboard'))
        
        try:
            bill.is_paid = True
            db.session.commit()
            flash('Bill marked as paid!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating bill. Please try again.', 'danger')
            print(f"Error marking bill as paid: {e}")
            
        return redirect(url_for('bills'))
        
    elif bill_type == 'credit_card':
        card = CreditCard.query.get_or_404(item_id)
        if card.user_id != session['user_id']:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('dashboard'))
        
        try:
            card.is_paid = True
            db.session.commit()
            flash('Credit card payment marked as paid!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating credit card. Please try again.', 'danger')
            print(f"Error marking credit card as paid: {e}")
            
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
        # Backup before editing
        backup_database()
        
        try:
            bill.name = request.form.get('name')
            bill.amount = float(request.form.get('amount'))
            bill.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
            bill.category = request.form.get('category')
            bill.recurring = 'recurring' in request.form
            
            db.session.commit()
            flash('Bill updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating bill. Please try again.', 'danger')
            print(f"Error editing bill: {e}")
        
    return redirect(url_for('dashboard'))

@app.route('/edit/bill_page/<int:bill_id>', methods=['POST'])
def edit_bill_page(bill_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    bill = Bill.query.get_or_404(bill_id)
    if bill.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('bills'))
    
    if request.method == 'POST':
        # Backup before editing
        backup_database()
        
        try:
            bill.name = request.form.get('name')
            bill.amount = float(request.form.get('amount'))
            bill.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
            bill.category = request.form.get('category')
            bill.recurring = 'recurring' in request.form
            
            db.session.commit()
            flash('Bill updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating bill. Please try again.', 'danger')
            print(f"Error editing bill: {e}")
        
    return redirect(url_for('bills'))

@app.route('/edit/subscription/<int:subscription_id>', methods=['POST'])
def edit_subscription(subscription_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    subscription = Subscription.query.get_or_404(subscription_id)
    if subscription.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('bills'))
    
    if request.method == 'POST':
        # Backup before editing
        backup_database()
        
        try:
            subscription.name = request.form.get('name')
            subscription.amount = float(request.form.get('amount'))
            subscription.billing_cycle = request.form.get('billing_cycle')
            subscription.next_billing_date = datetime.strptime(request.form.get('next_billing_date'), '%Y-%m-%d').date()
            subscription.category = request.form.get('category')
            subscription.auto_renew = 'auto_renew' in request.form
            
            db.session.commit()
            flash('Subscription updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating subscription. Please try again.', 'danger')
            print(f"Error editing subscription: {e}")
        
    return redirect(url_for('bills'))

@app.route('/edit/loan/<int:loan_id>', methods=['POST'])
def edit_loan(loan_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    loan = Loan.query.get_or_404(loan_id)
    if loan.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('bills'))
    
    if request.method == 'POST':
        # Backup before editing
        backup_database()
        
        try:
            loan.name = request.form.get('name')
            loan.loan_type = request.form.get('loan_type')
            loan.principal_amount = float(request.form.get('principal_amount'))
            loan.current_balance = float(request.form.get('current_balance'))
            loan.monthly_payment = float(request.form.get('monthly_payment'))
            loan.interest_rate = float(request.form.get('interest_rate')) if request.form.get('interest_rate') else None
            loan.next_payment_date = datetime.strptime(request.form.get('next_payment_date'), '%Y-%m-%d').date()
            loan.term_months = int(request.form.get('term_months')) if request.form.get('term_months') else None
            
            db.session.commit()
            flash('Loan updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating loan. Please try again.', 'danger')
            print(f"Error editing loan: {e}")
        
    return redirect(url_for('bills'))

@app.route('/edit/card/<int:card_id>', methods=['POST'])
def edit_card(card_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    card = CreditCard.query.get_or_404(card_id)
    if card.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Backup before editing
        backup_database()
        
        try:
            card.name = request.form.get('name')
            card.last_four = request.form.get('last_four')
            card.limit = float(request.form.get('limit')) if request.form.get('limit') else None
            card.current_balance = float(request.form.get('current_balance'))
            card.interest_rate = float(request.form.get('interest_rate')) if request.form.get('interest_rate') else None
            card.minimum_payment = float(request.form.get('minimum_payment')) if request.form.get('minimum_payment') else None
            card.auto_pay_minimum = ('auto_pay_minimum' in request.form)
            card.auto_payment_amount = float(request.form.get('auto_payment_amount')) if request.form.get('auto_payment_amount') and not card.auto_pay_minimum else None
            
            # Handle the due day
            if 'due_day' in request.form:
                due_day = int(request.form.get('due_day'))
                # Calculate the next occurrence of this day
                today = datetime.now().date()
                current_year = today.year
                current_month = today.month
                
                # Try to set for current month first
                try:
                    payment_due_date = datetime(current_year, current_month, due_day).date()
                except ValueError:
                    # Handle invalid day for month (e.g., February 30)
                    # Set to last day of the month
                    if current_month == 12:
                        next_month = 1
                        next_year = current_year + 1
                    else:
                        next_month = current_month + 1
                        next_year = current_year
                    
                    payment_due_date = datetime(next_year, next_month, 1).date() - timedelta(days=1)
                
                # If the day has already passed this month, move to next month
                if payment_due_date < today:
                    if current_month == 12:
                        payment_due_date = datetime(current_year + 1, 1, due_day).date()
                    else:
                        try:
                            payment_due_date = datetime(current_year, current_month + 1, due_day).date()
                        except ValueError:
                            # Handle invalid day for next month
                            if current_month + 1 == 12:
                                next_month = 1
                                next_year = current_year + 1
                            else:
                                next_month = current_month + 2
                                next_year = current_year
                            
                            payment_due_date = datetime(next_year, next_month, 1).date() - timedelta(days=1)
                
                card.payment_due_date = payment_due_date
            else:
                # If no due_day provided, use the payment_due_date from form (backwards compatibility)
                card.payment_due_date = datetime.strptime(request.form.get('payment_due_date'), '%Y-%m-%d').date()
            
            db.session.commit()
            flash('Credit card updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating credit card. Please try again.', 'danger')
            print(f"Error editing credit card: {e}")
        
    return redirect(url_for('dashboard'))

@app.route('/backup/export')
def export_backup():
    """Export all user data to JSON format"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        user = User.query.get(session['user_id'])
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('dashboard'))
        
        # Gather all user data
        backup_data = {
            'user_info': {
                'username': user.username,
                'email': user.email,
                'export_date': datetime.now().isoformat()
            },
            'bills': [],
            'credit_cards': [],
            'subscriptions': [],
            'loans': [],
            'income_sources': []
        }
        
        # Export bills
        bills = Bill.query.filter_by(user_id=user.id).all()
        for bill in bills:
            backup_data['bills'].append({
                'name': bill.name,
                'amount': bill.amount,
                'due_date': bill.due_date.isoformat(),
                'category': bill.category,
                'is_paid': bill.is_paid,
                'recurring': bill.recurring
            })
        
        # Export credit cards
        credit_cards = CreditCard.query.filter_by(user_id=user.id).all()
        for card in credit_cards:
            backup_data['credit_cards'].append({
                'name': card.name,
                'last_four': card.last_four,
                'limit': card.limit,
                'current_balance': card.current_balance,
                'payment_due_date': card.payment_due_date.isoformat(),
                'minimum_payment': card.minimum_payment,
                'interest_rate': card.interest_rate,
                'is_paid': card.is_paid,
                'auto_pay_minimum': card.auto_pay_minimum,
                'auto_payment_amount': card.auto_payment_amount
            })
        
        # Export subscriptions
        subscriptions = Subscription.query.filter_by(user_id=user.id).all()
        for subscription in subscriptions:
            backup_data['subscriptions'].append({
                'name': subscription.name,
                'amount': subscription.amount,
                'billing_cycle': subscription.billing_cycle,
                'next_billing_date': subscription.next_billing_date.isoformat(),
                'category': subscription.category,
                'is_active': subscription.is_active,
                'auto_renew': subscription.auto_renew
            })
        
        # Export loans
        loans = Loan.query.filter_by(user_id=user.id).all()
        for loan in loans:
            backup_data['loans'].append({
                'name': loan.name,
                'loan_type': loan.loan_type,
                'principal_amount': loan.principal_amount,
                'current_balance': loan.current_balance,
                'monthly_payment': loan.monthly_payment,
                'interest_rate': loan.interest_rate,
                'next_payment_date': loan.next_payment_date.isoformat(),
                'term_months': loan.term_months,
                'is_paid_off': loan.is_paid_off
            })
        
        # Export income sources
        income_sources = IncomeSource.query.filter_by(user_id=user.id).all()
        for income in income_sources:
            backup_data['income_sources'].append({
                'name': income.name,
                'amount': income.amount,
                'frequency': income.frequency,
                'payment_day_1': income.payment_day_1,
                'payment_day_2': income.payment_day_2,
                'next_payment_date': income.next_payment_date.isoformat() if income.next_payment_date else None,
                'is_active': income.is_active
            })
        
        # Create a temporary file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"vance_financial_backup_{user.username}_{timestamp}.json"
        
        # Create the response
        json_str = json.dumps(backup_data, indent=2, default=str)
        
        # Return as downloadable file
        return app.response_class(
            json_str,
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        
    except Exception as e:
        flash(f'Error creating backup: {str(e)}', 'danger')
        print(f"Backup error: {e}")
        return redirect(url_for('dashboard'))

@app.route('/backup/import', methods=['GET', 'POST'])
def import_backup():
    """Import data from JSON backup file"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'backup_file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(url_for('import_backup'))
        
        file = request.files['backup_file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('import_backup'))
        
        if file and file.filename.endswith('.json'):
            try:
                # Backup current database before import
                backup_database()
                
                # Read and parse the JSON file
                backup_data = json.load(file)
                user_id = session['user_id']
                
                # Clear existing data if requested
                if 'clear_existing' in request.form:
                    Bill.query.filter_by(user_id=user_id).delete()
                    CreditCard.query.filter_by(user_id=user_id).delete()
                    Subscription.query.filter_by(user_id=user_id).delete()
                    Loan.query.filter_by(user_id=user_id).delete()
                    IncomeSource.query.filter_by(user_id=user_id).delete()
                
                # Import bills
                for bill_data in backup_data.get('bills', []):
                    bill = Bill(
                        name=bill_data['name'],
                        amount=bill_data['amount'],
                        due_date=datetime.fromisoformat(bill_data['due_date']).date(),
                        category=bill_data.get('category'),
                        is_paid=bill_data.get('is_paid', False),
                        recurring=bill_data.get('recurring', False),
                        user_id=user_id
                    )
                    db.session.add(bill)
                
                # Import credit cards
                for card_data in backup_data.get('credit_cards', []):
                    card = CreditCard(
                        name=card_data['name'],
                        last_four=card_data['last_four'],
                        limit=card_data.get('limit'),
                        current_balance=card_data.get('current_balance', 0),
                        payment_due_date=datetime.fromisoformat(card_data['payment_due_date']).date(),
                        minimum_payment=card_data.get('minimum_payment'),
                        interest_rate=card_data.get('interest_rate'),
                        is_paid=card_data.get('is_paid', False),
                        auto_pay_minimum=card_data.get('auto_pay_minimum', False),
                        auto_payment_amount=card_data.get('auto_payment_amount'),
                        user_id=user_id
                    )
                    db.session.add(card)
                
                # Import subscriptions
                for sub_data in backup_data.get('subscriptions', []):
                    subscription = Subscription(
                        name=sub_data['name'],
                        amount=sub_data['amount'],
                        billing_cycle=sub_data['billing_cycle'],
                        next_billing_date=datetime.fromisoformat(sub_data['next_billing_date']).date(),
                        category=sub_data.get('category'),
                        is_active=sub_data.get('is_active', True),
                        auto_renew=sub_data.get('auto_renew', True),
                        user_id=user_id
                    )
                    db.session.add(subscription)
                
                # Import loans
                for loan_data in backup_data.get('loans', []):
                    loan = Loan(
                        name=loan_data['name'],
                        loan_type=loan_data['loan_type'],
                        principal_amount=loan_data['principal_amount'],
                        current_balance=loan_data['current_balance'],
                        monthly_payment=loan_data['monthly_payment'],
                        interest_rate=loan_data.get('interest_rate'),
                        next_payment_date=datetime.fromisoformat(loan_data['next_payment_date']).date(),
                        term_months=loan_data.get('term_months'),
                        is_paid_off=loan_data.get('is_paid_off', False),
                        user_id=user_id
                    )
                    db.session.add(loan)
                
                # Import income sources
                for income_data in backup_data.get('income_sources', []):
                    income = IncomeSource(
                        name=income_data['name'],
                        amount=income_data['amount'],
                        frequency=income_data['frequency'],
                        payment_day_1=income_data.get('payment_day_1'),
                        payment_day_2=income_data.get('payment_day_2'),
                        next_payment_date=datetime.fromisoformat(income_data['next_payment_date']).date() if income_data.get('next_payment_date') else None,
                        is_active=income_data.get('is_active', True),
                        user_id=user_id
                    )
                    db.session.add(income)
                
                db.session.commit()
                flash('Data imported successfully!', 'success')
                return redirect(url_for('dashboard'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error importing backup: {str(e)}', 'danger')
                print(f"Import error: {e}")
        else:
            flash('Please select a valid JSON backup file', 'danger')
    
    return render_template('import_backup.html')

@app.route('/backup/manual')
def manual_backup():
    """Create a manual database backup"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    success = backup_database()
    if success:
        flash('Database backup created successfully!', 'success')
    else:
        flash('Failed to create database backup', 'danger')
    
    return redirect(url_for('dashboard'))

# Add this route after your other routes, before the if __name__ == '__main__': line

@app.route('/test/backup')
def test_backup():
    """Test backup functionality - remove this in production"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        print("=== TESTING BACKUP FUNCTION ===")
        
        # Check if database exists
        db_path = os.path.abspath('finance_tracker.db')
        print(f"Database path: {db_path}")
        print(f"Database exists: {os.path.exists(db_path)}")
        
        if os.path.exists(db_path):
            print(f"Database size: {os.path.getsize(db_path)} bytes")
            print(f"Database readable: {os.access(db_path, os.R_OK)}")
        
        # Check backups directory
        backup_dir = os.path.abspath('backups')
        print(f"Backup directory: {backup_dir}")
        print(f"Backup directory exists: {os.path.exists(backup_dir)}")
        
        if os.path.exists(backup_dir):
            backup_files = os.listdir(backup_dir)
            print(f"Existing backup files: {backup_files}")
        
        # Test the backup function
        success = backup_database()
        print(f"Backup function result: {success}")
        
        if success:
            flash('Backup test successful! Check console for details.', 'success')
        else:
            flash('Backup test failed! Check console for error details.', 'danger')
            
        print("=== END BACKUP TEST ===")
        
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        print(f"Test backup error: {e}")
        import traceback
        print(f"Test backup traceback: {traceback.format_exc()}")
        flash(f'Backup test error: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/backup/manage')
def manage_backups():
    """View and manage backup files"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        # Get the correct backup directory path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backup_dir = os.path.join(current_dir, 'backups')
        backup_files = []
        total_size = 0
        
        if os.path.exists(backup_dir):
            for filename in os.listdir(backup_dir):
                if filename.endswith('.db'):
                    file_path = os.path.join(backup_dir, filename)
                    file_stats = os.stat(file_path)
                    file_size = file_stats.st_size
                    file_date = datetime.fromtimestamp(file_stats.st_mtime)
                    
                    backup_files.append({
                        'filename': filename,
                        'size': file_size,
                        'size_mb': round(file_size / (1024 * 1024), 2),
                        'date': file_date,
                        'date_str': file_date.strftime('%Y-%m-%d %H:%M:%S')
                    })
                    total_size += file_size
            
            # Sort by date (newest first)
            backup_files.sort(key=lambda x: x['date'], reverse=True)
        
        return render_template('manage_backups.html', 
                             backup_files=backup_files,
                             backup_dir=backup_dir,
                             total_size_mb=round(total_size / (1024 * 1024), 2),
                             backup_count=len(backup_files))
        
    except Exception as e:
        flash(f'Error accessing backup directory: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/backup/download/<filename>')
def download_backup(filename):
    """Download a specific backup file"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backup_dir = os.path.join(current_dir, 'backups')
        file_path = os.path.join(backup_dir, filename)
        
        # Security check - ensure file is in backups directory and is a .db file
        if not file_path.startswith(backup_dir) or not filename.endswith('.db'):
            flash('Invalid backup file', 'danger')
            return redirect(url_for('manage_backups'))
        
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            flash('Backup file not found', 'danger')
            return redirect(url_for('manage_backups'))
            
    except Exception as e:
        flash(f'Error downloading backup: {str(e)}', 'danger')
        return redirect(url_for('manage_backups'))

@app.route('/backup/delete/<filename>')
def delete_backup(filename):
    """Delete a specific backup file"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backup_dir = os.path.join(current_dir, 'backups')
        file_path = os.path.join(backup_dir, filename)
        
        # Security check - ensure file is in backups directory and is a .db file
        if not file_path.startswith(backup_dir) or not filename.endswith('.db'):
            flash('Invalid backup file', 'danger')
            return redirect(url_for('manage_backups'))
        
        if os.path.exists(file_path):
            os.remove(file_path)
            flash(f'Backup file {filename} deleted successfully!', 'success')
        else:
            flash('Backup file not found', 'danger')
            
    except Exception as e:
        flash(f'Error deleting backup: {str(e)}', 'danger')
    
    return redirect(url_for('manage_backups'))

@app.route('/debug/paths')
def debug_paths():
    """Debug route to show all relevant paths - remove in production"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        import sys
        
        # Get current working directory and file paths
        current_dir = os.path.dirname(os.path.abspath(__file__))
        working_dir = os.getcwd()
        backup_dir = os.path.join(current_dir, 'backups')
        db_path = os.path.join(current_dir, 'finance_tracker.db')
        
        path_info = {
            'Python File Location': current_dir,
            'Current Working Directory': working_dir,
            'Database Path': db_path,
            'Backup Directory': backup_dir,
            'Database Exists': os.path.exists(db_path),
            'Backup Dir Exists': os.path.exists(backup_dir),
            'Python Executable': sys.executable,
            'Script Name': __file__
        }
        
        # Print to console
        print("=== PATH DEBUG INFO ===")
        for key, value in path_info.items():
            print(f"{key}: {value}")
        print("======================")
        
        # Create HTML response
        html = "<h2>Path Debug Information</h2><table border='1' style='border-collapse: collapse;'>"
        for key, value in path_info.items():
            html += f"<tr><td><strong>{key}</strong></td><td>{value}</td></tr>"
        html += "</table>"
        html += f"<br><a href='{url_for('dashboard')}'>Back to Dashboard</a>"
        
        return html
        
    except Exception as e:
        return f"Error getting path info: {str(e)}"

@app.route('/debug/users')
def debug_users():
    """Debug route to show all users - remove in production"""
    try:
        users = User.query.all()
        
        print("=== USER DEBUG INFO ===")
        print(f"Total users in database: {len(users)}")
        
        if users:
            for user in users:
                print(f"User ID: {user.id}")
                print(f"Username: {user.username}")
                print(f"Email: {user.email}")
                print(f"Password Hash: {user.password_hash[:50]}...")
                print("---")
        else:
            print("No users found in database")
        print("=====================")
        
        # Create HTML response
        html = "<h2>User Debug Information</h2>"
        if users:
            html += "<table border='1' style='border-collapse: collapse;'>"
            html += "<tr><th>ID</th><th>Username</th><th>Email</th><th>Password Hash (first 50 chars)</th></tr>"
            for user in users:
                html += f"<tr><td>{user.id}</td><td>{user.username}</td><td>{user.email}</td><td>{user.password_hash[:50]}...</td></tr>"
            html += "</table>"
        else:
            html += "<p>No users found in database. You may need to register a new account.</p>"
        
        html += f"<br><a href='{url_for('register')}'>Register New Account</a>"
        html += f"<br><a href='{url_for('login')}'>Back to Login</a>"
        
        return html
        
    except Exception as e:
        return f"Error getting user info: {str(e)}"

# THIS IS THE CRUCIAL PART THAT WAS MISSING!
if __name__ == '__main__':
    app.run(debug=True, port=5001)