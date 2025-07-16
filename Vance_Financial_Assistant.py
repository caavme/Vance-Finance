import os
import secrets
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import shutil
import json 
import tempfile
import calendar
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFProtect
from flask_wtf.csrf import generate_csrf

# Initialize Flask application
app = Flask(__name__)

# Trust proxy headers from Nginx - ADD THIS RIGHT AFTER CREATING APP
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Add CSRF protection
csrf = CSRFProtect(app)

# Configuration that works for both local development and deployment
class Config:
    # Generate a secure secret key if none provided
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Database configuration - works for both local and deployed
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_URL = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(BASE_DIR, "finance_tracker.db")}'
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEVELOPMENT_MODE = os.environ.get('DEVELOPMENT_MODE', 'true').lower() == 'true'

app.config.from_object(Config)

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
    
    # Add these new budget relationships:
    budget_categories = db.relationship('BudgetCategory', backref='owner', lazy=True)
    budget_periods = db.relationship('BudgetPeriod', backref='owner', lazy=True)
    budget_items = db.relationship('BudgetItem', backref='owner', lazy=True)
    budget_transactions = db.relationship('BudgetTransaction', backref='owner', lazy=True)
    budget_goals = db.relationship('BudgetGoal', backref='owner', lazy=True)

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(50))
    is_paid = db.Column(db.Boolean, default=False)
    recurring = db.Column(db.Boolean, default=False)
    include_in_calculations = db.Column(db.Boolean, default=True)  # NEW FIELD
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
    include_in_calculations = db.Column(db.Boolean, default=True)  # NEW FIELD
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
    include_in_calculations = db.Column(db.Boolean, default=True)  # NEW FIELD
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
    include_in_calculations = db.Column(db.Boolean, default=True)  # NEW FIELD
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    income_type = db.Column(db.String(20), default='Employment')  # <-- Add this line
class IncomeSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)  # Per payment amount
    frequency = db.Column(db.String(20), nullable=False)  # 'weekly', 'biweekly', 'monthly', 'bimonthly', 'quarterly', 'annually', 'onetime'
    # For bimonthly (twice monthly): payment_day_1 and payment_day_2
    payment_day_1 = db.Column(db.Integer)  # e.g., 15
    payment_day_2 = db.Column(db.Integer)  # e.g., 30 (or last day of month)
    # For biweekly, weekly, quarterly, annually: next_payment_date and we calculate subsequent dates
    next_payment_date = db.Column(db.Date)
    # For weekly payments: day of the week
    day_of_week = db.Column(db.String(10))  # 'Monday', 'Tuesday', etc.
    # For one-time income: specific date when income was/will be received
    one_time_date = db.Column(db.Date)  # NEW FIELD for one-time income
    is_active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class BudgetCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    color = db.Column(db.String(7), default='#667eea')  # Hex color code
    icon = db.Column(db.String(50), default='bi-wallet2')  # Bootstrap icon class
    is_active = db.Column(db.Boolean, default=True)
    is_income = db.Column(db.Boolean, default=False)  # True for income categories, False for expense
    sort_order = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    budget_items = db.relationship('BudgetItem', backref='category', lazy=True, cascade='all, delete-orphan')

class BudgetPeriod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "January 2025", "Q1 2025"
    period_type = db.Column(db.String(20), nullable=False)  # 'monthly', 'quarterly', 'yearly', 'custom'
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    auto_rollover = db.Column(db.Boolean, default=False)  # Auto-create next period
    notes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    budget_items = db.relationship('BudgetItem', backref='period', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('BudgetTransaction', backref='period', lazy=True, cascade='all, delete-orphan')

class BudgetItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('budget_category.id'), nullable=False)
    period_id = db.Column(db.Integer, db.ForeignKey('budget_period.id'), nullable=False)
    planned_amount = db.Column(db.Float, nullable=False, default=0.0)
    actual_amount = db.Column(db.Float, default=0.0)  # Auto-calculated from transactions
    notes = db.Column(db.Text)
    alert_threshold = db.Column(db.Float)  # Alert when % of budget is reached (0.8 = 80%)
    is_rollover = db.Column(db.Boolean, default=False)  # Unused budget rolls to next period
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BudgetTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('budget_category.id'), nullable=False)
    period_id = db.Column(db.Integer, db.ForeignKey('budget_period.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.Date, nullable=False)
    transaction_type = db.Column(db.String(20), default='manual')  # 'manual', 'bill', 'subscription', 'loan'
    reference_id = db.Column(db.Integer)  # ID of linked bill/subscription/loan
    receipt_url = db.Column(db.String(255))  # Optional receipt/proof
    tags = db.Column(db.String(255))  # Comma-separated tags
    notes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to category
    category = db.relationship('BudgetCategory', backref='transactions')

class BudgetGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    target_date = db.Column(db.Date)
    category = db.Column(db.String(50))  # 'emergency', 'vacation', 'purchase', 'debt_payoff'
    priority = db.Column(db.String(20), default='medium')  # 'low', 'medium', 'high'
    is_active = db.Column(db.Boolean, default=True)
    is_achieved = db.Column(db.Boolean, default=False)
    auto_contribute = db.Column(db.Float, default=0.0)  # Automatic monthly contribution
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Updated backup function to work in any environment
def backup_database():
    """Create a backup of the database"""
    try:
        # Use app's instance path or current directory
        if hasattr(app, 'instance_path'):
            base_dir = app.instance_path
        else:
            base_dir = os.path.abspath(os.path.dirname(__file__))
            
        backups_dir = os.path.join(base_dir, 'backups')
        
        # Create backups directory if it doesn't exist
        os.makedirs(backups_dir, exist_ok=True)
        
        # Get database file path
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
            if not os.path.isabs(db_path):
                db_path = os.path.join(base_dir, db_path)
        else:
            # For non-SQLite databases, skip file backup
            print("Non-SQLite database detected, skipping file backup")
            return True
            
        if os.path.exists(db_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"finance_tracker_backup_{timestamp}.db"
            backup_path = os.path.join(backups_dir, backup_filename)
            
            if os.access(db_path, os.R_OK):
                shutil.copy2(db_path, backup_path)
                print(f"Database backed up to: {backup_path}")
                
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
            return True
            
    except Exception as e:
        print(f"Backup failed with error: {type(e).__name__}: {str(e)}")
        return False

# Updated safe migration function
def safe_migrate_database():
    """Safely migrate database without losing data"""
    try:
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        
        # Only backup for SQLite databases
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
            if not os.path.isabs(db_path):
                base_dir = os.path.abspath(os.path.dirname(__file__))
                db_path = os.path.join(base_dir, db_path)
            
            if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
                print("Existing database found, creating backup before migration...")
                backup_database()
            else:
                print("No existing database found or database is empty, skipping backup")
        
        # Migration logic for existing tables
        with db.engine.connect() as connection:
            # Check for credit card columns
            result = connection.execute(db.text("PRAGMA table_info(credit_card)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'auto_pay_minimum' not in columns:
                connection.execute(db.text('ALTER TABLE credit_card ADD COLUMN auto_pay_minimum BOOLEAN DEFAULT 0'))
                print("Added auto_pay_minimum column")
                
            if 'auto_payment_amount' not in columns:
                connection.execute(db.text('ALTER TABLE credit_card ADD COLUMN auto_payment_amount REAL'))
                print("Added auto_payment_amount column")
            
            # Add include_in_calculations columns for all models
            if 'include_in_calculations' not in columns:
                connection.execute(db.text('ALTER TABLE credit_card ADD COLUMN include_in_calculations BOOLEAN DEFAULT 1'))
                print("Added include_in_calculations column to credit_card")
            
            # Check bills table
            result = connection.execute(db.text("PRAGMA table_info(bill)"))
            bill_columns = [row[1] for row in result.fetchall()]
            if 'include_in_calculations' not in bill_columns:
                connection.execute(db.text('ALTER TABLE bill ADD COLUMN include_in_calculations BOOLEAN DEFAULT 1'))
                print("Added include_in_calculations column to bill")
            
            # Check subscriptions table
            result = connection.execute(db.text("PRAGMA table_info(subscription)"))
            sub_columns = [row[1] for row in result.fetchall()]
            if 'include_in_calculations' not in sub_columns:
                connection.execute(db.text('ALTER TABLE subscription ADD COLUMN include_in_calculations BOOLEAN DEFAULT 1'))
                print("Added include_in_calculations column to subscription")
            
            # Check loans table
            result = connection.execute(db.text("PRAGMA table_info(loan)"))
            loan_columns = [row[1] for row in result.fetchall()]
            if 'income_type' not in loan_columns:
                connection.execute(db.text("ALTER TABLE loan ADD COLUMN income_type VARCHAR(20) DEFAULT 'Employment'"))
                print("Added income_type column to loan")
            
            # Check for income_source table and add new column
            result = connection.execute(db.text("SELECT name FROM sqlite_master WHERE type='table' AND name='income_source'"))
            if result.fetchone():
                # Table exists, check for new column
                result = connection.execute(db.text("PRAGMA table_info(income_source)"))
                income_columns = [row[1] for row in result.fetchall()]
                
                if 'day_of_week' not in income_columns:
                    connection.execute(db.text('ALTER TABLE income_source ADD COLUMN day_of_week VARCHAR(10)'))
                    print("Added day_of_week column to income_source")
            else:
                print("Creating income_source table...")
            
            # Check for budget tables
            budget_tables = ['budget_category', 'budget_period', 'budget_item', 'budget_transaction', 'budget_goal']
            for table in budget_tables:
                result = connection.execute(db.text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"))
                if not result.fetchone():
                    print(f"Budget table {table} will be created...")
            
            # Check for income_source table and add one_time_date column if needed
            result = connection.execute(db.text("SELECT name FROM sqlite_master WHERE type='table' AND name='income_source'"))
            if result.fetchone():
                # Table exists, check for new column
                result = connection.execute(db.text("PRAGMA table_info(income_source)"))
                income_columns = [row[1] for row in result.fetchall()]
                
                if 'one_time_date' not in income_columns:
                    connection.execute(db.text('ALTER TABLE income_source ADD COLUMN one_time_date DATE'))
                    print("Added one_time_date column to income_source")
            # Inside safe_migrate_database(), after other migrations
            result = connection.execute(db.text("PRAGMA table_info(income_source)"))
            income_columns = [row[1] for row in result.fetchall()]
            if 'income_type' not in income_columns:
                connection.execute(db.text("ALTER TABLE income_source ADD COLUMN income_type VARCHAR(20) DEFAULT 'Employment'"))
                print("Added income_type column to income_source") 
                
            connection.commit()
            print("Migration completed successfully")
            
    except Exception as e:
        print(f"Migration failed: {e}")

# Utility functions for income calculations
def calculate_monthly_income(user_id):
    """Calculate estimated monthly income for a user"""
    income_sources = IncomeSource.query.filter_by(user_id=user_id, is_active=True).all()
    monthly_total = 0
    
    for source in income_sources:
        if source.frequency == 'weekly':
            # Weekly = 52 payments per year / 12 months
            monthly_total += source.amount * 52 / 12
        elif source.frequency == 'biweekly':
            # Every two weeks = 26 payments per year / 12 months
            monthly_total += source.amount * 26 / 12
        elif source.frequency == 'monthly':
            # Once monthly = 12 payments per year / 12 months
            monthly_total += source.amount
        elif source.frequency == 'bimonthly':
            # Twice monthly = 24 payments per year / 12 months
            monthly_total += source.amount * 2
        elif source.frequency == 'quarterly':
            # Quarterly = 4 payments per year / 12 months
            monthly_total += source.amount / 3
        elif source.frequency == 'annually':
            # Annually = 1 payment per year / 12 months
            monthly_total += source.amount / 12
        elif source.frequency == 'onetime':
            # One-time income: don't include in monthly recurring calculation
            # This could be included in specific month calculations if needed
            pass
    
    return monthly_total

def calculate_monthly_expenses(user_id, include_excluded=False):
    """Calculate estimated monthly expenses"""
    # Get recurring bills (only include those marked for calculations unless explicitly requested)
    if include_excluded:
        bills = Bill.query.filter_by(user_id=user_id, recurring=True).all()
    else:
        bills = Bill.query.filter_by(user_id=user_id, recurring=True, include_in_calculations=True).all()
    bill_total = sum(bill.amount for bill in bills)
    
    # Get monthly subscriptions (only include those marked for calculations unless explicitly requested)
    if include_excluded:
        subscriptions = Subscription.query.filter_by(user_id=user_id, is_active=True).all()
    else:
        subscriptions = Subscription.query.filter_by(user_id=user_id, is_active=True, include_in_calculations=True).all()
    
    subscription_total = 0
    for sub in subscriptions:
        if sub.billing_cycle == 'Monthly':
            subscription_total += sub.amount
        elif sub.billing_cycle == 'Yearly':
            subscription_total += sub.amount / 12
        elif sub.billing_cycle == 'Weekly':
            subscription_total += sub.amount * 4.33  # Average weeks per month
    
    # Get loan payments (only include those marked for calculations unless explicitly requested)
    if include_excluded:
        loans = Loan.query.filter_by(user_id=user_id, is_paid_off=False).all()
    else:
        loans = Loan.query.filter_by(user_id=user_id, is_paid_off=False, include_in_calculations=True).all()
    loan_total = sum(loan.monthly_payment for loan in loans)
    
    # Get credit card minimum payments (only include those marked for calculations unless explicitly requested)
    if include_excluded:
        cards = CreditCard.query.filter_by(user_id=user_id).all()
    else:
        cards = CreditCard.query.filter_by(user_id=user_id, include_in_calculations=True).all()
    card_total = sum(card.minimum_payment for card in cards if card.minimum_payment)
    
    # Calculate excluded amounts for transparency
    excluded_total = 0
    if not include_excluded:
        excluded_bills = Bill.query.filter_by(user_id=user_id, recurring=True, include_in_calculations=False).all()
        excluded_subscriptions = Subscription.query.filter_by(user_id=user_id, is_active=True, include_in_calculations=False).all()
        excluded_loans = Loan.query.filter_by(user_id=user_id, is_paid_off=False, include_in_calculations=False).all()
        excluded_cards = CreditCard.query.filter_by(user_id=user_id, include_in_calculations=False).all()
        
        excluded_total += sum(bill.amount for bill in excluded_bills)
        
        for sub in excluded_subscriptions:
            if sub.billing_cycle == 'Monthly':
                excluded_total += sub.amount
            elif sub.billing_cycle == 'Yearly':
                excluded_total += sub.amount / 12
            elif sub.billing_cycle == 'Weekly':
                excluded_total += sub.amount * 4.33
        
        excluded_total += sum(loan.monthly_payment for loan in excluded_loans)
        excluded_total += sum(card.minimum_payment for card in excluded_cards if card.minimum_payment)
    
    return {
        'bills': bill_total,
        'subscriptions': subscription_total,
        'loans': loan_total,
        'credit_cards': card_total,
        'total': bill_total + subscription_total + loan_total + card_total,
        'excluded_total': excluded_total
    }

def get_future_income_dates(income_source, start_date, end_date):
    """Get list of income dates for a source between start and end dates"""
    dates = []
    current_date = start_date
    
    if income_source.frequency == 'onetime':
        # One-time income: only show if the date falls within the range
        if income_source.one_time_date and start_date <= income_source.one_time_date <= end_date:
            dates.append(income_source.one_time_date)
    elif income_source.frequency == 'weekly':
        # Weekly payments on specific day of week
        if income_source.next_payment_date:
            pay_date = income_source.next_payment_date
            while pay_date <= end_date:
                if pay_date >= start_date:
                    dates.append(pay_date)
                pay_date += timedelta(days=7)
    
    elif income_source.frequency == 'biweekly':
        # Every two weeks from next_payment_date
        if income_source.next_payment_date:
            pay_date = income_source.next_payment_date
            while pay_date <= end_date:
                if pay_date >= start_date:
                    dates.append(pay_date)
                pay_date += timedelta(days=14)
    
    elif income_source.frequency == 'monthly':
        # Monthly payment on specific day
        while current_date <= end_date:
            year = current_date.year
            month = current_date.month
            
            if income_source.payment_day_1:
                try:
                    if income_source.payment_day_1 == 31:
                        # Last day of month
                        last_day = calendar.monthrange(year, month)[1]
                        pay_date = datetime(year, month, last_day).date()
                    else:
                        pay_date = datetime(year, month, income_source.payment_day_1).date()
                    
                    if start_date <= pay_date <= end_date:
                        dates.append(pay_date)
                except ValueError:
                    # Handle invalid dates (e.g., Feb 30)
                    pass
            
            # Move to next month
            if month == 12:
                current_date = datetime(year + 1, 1, 1).date()
            else:
                current_date = datetime(year, month + 1, 1).date()
    
    elif income_source.frequency == 'bimonthly':
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
    
    elif income_source.frequency == 'quarterly':
        # Quarterly payments
        if income_source.next_payment_date:
            pay_date = income_source.next_payment_date
            while pay_date <= end_date:
                if pay_date >= start_date:
                    dates.append(pay_date)
                # Add 3 months for next quarterly payment
                pay_date = add_months(pay_date, 3)
    
    elif income_source.frequency == 'annually':
        # Annual payments
        if income_source.next_payment_date:
            pay_date = income_source.next_payment_date
            while pay_date <= end_date:
                if pay_date >= start_date:
                    dates.append(pay_date)
                # Add 12 months for next annual payment
                pay_date = add_months(pay_date, 12)
    
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

# Add this function before your routes (around line 340)
def create_demo_data():
    """Create comprehensive demo data for showcase"""
    from werkzeug.security import generate_password_hash
    
    # Create demo user
    demo_user = User(
        username='demo_user',
        email='demo@vancefinance.com',  # Updated email
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
        
        # Create Income Sources with various frequencies
        income_sources = [
            IncomeSource(
                name="Primary Salary",
                amount=3250.00,  # Bi-monthly
                frequency='bimonthly',
                payment_day_1=15,
                payment_day_2=30,
                is_active=True,
                user_id=demo_user_id
            ),
            IncomeSource(
                name="Secondary Salary",
                amount=1850.00,  # Bi-weekly
                frequency='biweekly',
                next_payment_date=today + timedelta(days=3),  # Next Friday
                is_active=True,
                user_id=demo_user_id
            ),
            IncomeSource(
                name="Freelance Work",
                amount=1200.00,  # Monthly
                frequency='monthly',
                payment_day_1=25,  # 25th of each month
                is_active=True,
                user_id=demo_user_id
            ),
            IncomeSource(
                name="Part-time Job",
                amount=400.00,  # Weekly
                frequency='weekly',
                day_of_week='Saturday',
                next_payment_date=today + timedelta(days=(5-today.weekday()) % 7 + 1),  # Next Saturday
                is_active=True,
                user_id=demo_user_id
            ),
            IncomeSource(
                name="Quarterly Bonus",
                amount=2500.00,  # Quarterly
                frequency='quarterly',
                next_payment_date=datetime(today.year, ((today.month-1)//3 + 1)*3 + 1, 1).date(),  # Next quarter
                is_active=True,
                user_id=demo_user_id
            ),
            IncomeSource(
                name="Tax Refund",
                amount=2100.00,  # One-time
                frequency='onetime',
                one_time_date=today + timedelta(days=45),  # Tax season
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
        create_demo_budget_data(demo_user_id)
        return demo_user_id
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating demo data: {e}")
        return None

# Add this function after the create_demo_data function

def create_demo_budget_data(demo_user_id):
    """Create demo budget data for the demo user"""
    try:
        # Clear existing budget data for demo user
        BudgetCategory.query.filter_by(user_id=demo_user_id).delete()
        BudgetPeriod.query.filter_by(user_id=demo_user_id).delete()
        BudgetItem.query.filter_by(user_id=demo_user_id).delete()
        BudgetTransaction.query.filter_by(user_id=demo_user_id).delete()
        BudgetGoal.query.filter_by(user_id=demo_user_id).delete()
        
        # Create default budget categories
        create_default_budget_categories(demo_user_id)
        
        # Create current month budget period
        current_period = create_current_budget_period(demo_user_id)
        
        # Get categories for budget items
        categories = BudgetCategory.query.filter_by(user_id=demo_user_id).all()
        
        # Create some budget items
        budget_items_data = [
            # Income categories
            ('Salary', 6500.00, True),
            ('Side Income', 1200.00, True),
            # Expense categories
            ('Housing', 2150.00, False),
            ('Transportation', 650.00, False),
            ('Food & Groceries', 800.00, False),
            ('Healthcare', 425.00, False),
            ('Entertainment', 300.00, False),
            ('Savings', 1000.00, False),
            ('Debt Payments', 810.00, False),
        ]
        
        for cat_name, planned_amount, is_income in budget_items_data:
            category = next((c for c in categories if c.name == cat_name and c.is_income == is_income), None)
            if category:
                budget_item = BudgetItem(
                    category_id=category.id,
                    period_id=current_period.id,
                    planned_amount=planned_amount,
                    user_id=demo_user_id
                )
                db.session.add(budget_item)
        
        # Create some demo transactions
        today = datetime.now().date()
        transactions_data = [
            ('Salary', 3250.00, today - timedelta(days=15), True),
            ('Freelance Work', 600.00, today - timedelta(days=10), True),
            ('Grocery Shopping', -120.50, today - timedelta(days=5), False),
            ('Gas Station', -45.00, today - timedelta(days=3), False),
            ('Restaurant', -67.80, today - timedelta(days=2), False),
            ('Emergency Fund', -500.00, today - timedelta(days=1), False),
        ]
        
        for desc, amount, trans_date, is_income in transactions_data:
            # Find appropriate category
            category = None
            if is_income:
                if 'Salary' in desc:
                    category = next((c for c in categories if c.name == 'Salary'), None)
                else:
                    category = next((c for c in categories if c.name == 'Side Income'), None)
            else:
                if 'Grocery' in desc or 'Restaurant' in desc:
                    category = next((c for c in categories if c.name == 'Food & Groceries'), None)
                elif 'Gas' in desc:
                    category = next((c for c in categories if c.name == 'Transportation'), None)
                elif 'Emergency' in desc:
                    category = next((c for c in categories if c.name == 'Savings'), None)
                else:
                    category = next((c for c in categories if c.name == 'Miscellaneous'), None)
            
            if category:
                transaction = BudgetTransaction(
                    category_id=category.id,
                    period_id=current_period.id,
                    description=desc,
                    amount=amount,
                    transaction_date=trans_date,
                    user_id=demo_user_id
                )
                db.session.add(transaction)
        
        # Create some demo goals
        goals_data = [
            ('Emergency Fund', 'Build 6-month emergency fund', 15000.00, today + timedelta(days=365), 'emergency', 'high', 2500.00),
            ('Vacation Fund', 'Save for Europe trip', 5000.00, today + timedelta(days=180), 'vacation', 'medium', 500.00),
            ('Car Down Payment', 'Save for new car down payment', 8000.00, today + timedelta(days=270), 'purchase', 'medium', 0.00),
        ]
        
        for title, desc, target, target_date, category, priority, current in goals_data:
            goal = BudgetGoal(
                title=title,
                description=desc,
                target_amount=target,
                current_amount=current,
                target_date=target_date,
                category=category,
                priority=priority,
                auto_contribute=target/12,  # Auto-contribute 1/12 of target monthly
                user_id=demo_user_id
            )
            db.session.add(goal)
        
        db.session.commit()
        print("Demo budget data created successfully")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating demo budget data: {e}")

def get_user_loans():
    if 'user_id' not in session:
        return []
    loans = Loan.query.filter_by(user_id=session['user_id'], is_paid_off=False, include_in_calculations=True).all()
    return [{'name': loan.name, 'min_payment': loan.monthly_payment} for loan in loans]

def get_user_credit_cards():
    if 'user_id' not in session:
        return []
    cards = CreditCard.query.filter_by(user_id=session['user_id'], include_in_calculations=True).all()
    return [{'name': card.name, 'min_payment': card.minimum_payment or 0, 'balance': card.current_balance or 0} for card in cards]

def plan_budget_framework(user_id, period_type='monthly'):
    from datetime import date
    today = date.today()
    period_name = today.strftime("%B %Y")
    period = BudgetPeriod.query.filter_by(user_id=user_id, name=period_name, period_type=period_type).first()
    if not period:
        return {'categories': []}

    categories = BudgetCategory.query.filter_by(user_id=user_id, is_active=True).all()
    results = []

    # Get all income sources
    income_sources = IncomeSource.query.filter_by(user_id=user_id, is_active=True).all()

    # Get all bills, subscriptions, loans, credit cards
    bills = Bill.query.filter_by(user_id=user_id, recurring=True, include_in_calculations=True).all()
    subscriptions = Subscription.query.filter_by(user_id=user_id, is_active=True, include_in_calculations=True).all()
    loans = Loan.query.filter_by(user_id=user_id, is_paid_off=False, include_in_calculations=True).all()
    cards = CreditCard.query.filter_by(user_id=user_id, include_in_calculations=True).all()

    for category in categories:
        planned_amount = 0.0

        if category.is_income:
            # Only sum relevant income sources for each income category
            if category.name.lower() == 'salary':
                planned_amount = sum(
                    calculate_monthly_income(src.user_id)
                    for src in income_sources
                    if 'salary' in src.name.lower()
                )
            elif category.name.lower() == 'side income':
                planned_amount = sum(
                    calculate_monthly_income(src.user_id)
                    for src in income_sources
                    if any(x in src.name.lower() for x in ['freelance', 'side', 'part-time'])
                )
            elif category.name.lower() == 'investment income':
                planned_amount = sum(
                    calculate_monthly_income(src.user_id)
                    for src in income_sources
                    if 'investment' in src.name.lower()
                )
            else:
                planned_amount = 0.0
        else:
            # Assign expenses based on category name
            if category.name.lower() == 'housing':
                planned_amount = sum(bill.amount for bill in bills if bill.category and 'housing' in bill.category.lower())
            elif category.name.lower() == 'transportation':
                planned_amount = sum(bill.amount for bill in bills if bill.category and 'transportation' in bill.category.lower())
                planned_amount += sum(loan.monthly_payment for loan in loans if loan.loan_type and 'auto' in loan.loan_type.lower())
            elif category.name.lower() == 'food & groceries':
                planned_amount = 0.0
            elif category.name.lower() == 'healthcare':
                planned_amount = sum(bill.amount for bill in bills if bill.category and 'health' in bill.category.lower())
            elif category.name.lower() == 'insurance':
                planned_amount = sum(bill.amount for bill in bills if bill.category and 'insurance' in bill.category.lower())
            elif category.name.lower() == 'entertainment':
                planned_amount = sum(sub.amount for sub in subscriptions if sub.category and 'entertainment' in sub.category.lower())
            elif category.name.lower() == 'shopping':
                planned_amount = 0.0
            elif category.name.lower() == 'savings':
                planned_amount = 0.0
            elif category.name.lower() == 'debt payments':
                planned_amount = sum(loan.monthly_payment for loan in loans)
                planned_amount += sum(card.minimum_payment for card in cards if card.minimum_payment)
            else:
                planned_amount = 0.0

        results.append({'category': category, 'planned_amount': round(planned_amount, 2)})

    return {'categories': results}

# Create the database tables and migrate
def run_safe_migrations():
    """Safely migrate the database schema by adding missing columns only."""
    with app.app_context():
        db.create_all()  # Only creates missing tables, never drops or alters existing ones

        # List of migrations: table, column, SQL type, default value (if any)
        migrations = [
            # (table, column, SQL type, default SQL)
            ('credit_card', 'auto_pay_minimum', 'BOOLEAN', 'DEFAULT 0'),
            ('credit_card', 'auto_payment_amount', 'REAL', ''),
            ('credit_card', 'include_in_calculations', 'BOOLEAN', 'DEFAULT 1'),
            ('bill', 'include_in_calculations', 'BOOLEAN', 'DEFAULT 1'),
            ('subscription', 'include_in_calculations', 'BOOLEAN', 'DEFAULT 1'),
            ('loan', 'include_in_calculations', 'BOOLEAN', 'DEFAULT 1'),
            ('loan', 'income_type', 'VARCHAR(20)', "DEFAULT 'Employment'"),
            ('income_source', 'day_of_week', 'VARCHAR(10)', ''),
            ('income_source', 'one_time_date', 'DATE', ''),
            ('income_source', 'income_type', 'VARCHAR(20)', "DEFAULT 'Employment'"),
        ]

        for table, column, coltype, default in migrations:
            # Check if column exists
            result = db.session.execute(db.text(f"PRAGMA table_info({table})"))
            columns = [row[1] for row in result.fetchall()]
            if column not in columns:
                try:
                    db.session.execute(
                        db.text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype} {default}")
                    )
                    print(f"Added column '{column}' to '{table}'")
                except Exception as e:
                    print(f"Could not add column '{column}' to '{table}': {e}")

        db.session.commit()
        print("Safe migrations complete.")

# Routes
@app.before_request
def log_request_info():
    print(f"[REQUEST] {request.method} {request.path} | session: {dict(session)}")

@app.route('/')
def index():
    print("[DEBUG] Entered /dashboard route")
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

    from datetime import datetime, timedelta
   
    # Dashboard variables
    upcoming_bills = Bill.query.filter_by(user_id=user.id, is_paid=False).order_by(Bill.due_date).all()
    credit_cards = CreditCard.query.filter_by(user_id=user.id).all()
    today = datetime.now().date()
    upcoming_week = today + timedelta(days=7)
    urgent_bills = [bill for bill in upcoming_bills if bill.due_date <= upcoming_week]
    monthly_income = calculate_monthly_income(user.id)
    monthly_expenses = calculate_monthly_expenses(user_id=user.id, include_excluded=False)
    monthly_expenses_all = calculate_monthly_expenses(user_id=user.id, include_excluded=True)
    debt_to_income_ratio = 0
    if monthly_income > 0:
        debt_to_income_ratio = (monthly_expenses['total'] / monthly_income) * 100
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
    next_income_dates.sort(key=lambda x: x['date'])

    # --- NEW: Handle overview query parameters ---

    # Get date range from request or default to next 3 months
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    include_excluded_str = request.args.get('include_excluded', 'false')
    include_excluded = include_excluded_str.lower() == 'true'

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except Exception:
            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=90)
    else:
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=90)

    # Get all income sources (income always included)
    income_sources_ov = IncomeSource.query.filter_by(user_id=user.id, is_active=True).all()
    if include_excluded:
        bills_ov = Bill.query.filter_by(user_id=user.id, recurring=True).all()
        subscriptions_ov = Subscription.query.filter_by(user_id=user.id, is_active=True).all()
        loans_ov = Loan.query.filter_by(user_id=user.id, is_paid_off=False).all()
        credit_cards_ov = CreditCard.query.filter_by(user_id=user.id).all()
    else:
        bills_ov = Bill.query.filter_by(user_id=user.id, recurring=True, include_in_calculations=True).all()
        subscriptions_ov = Subscription.query.filter_by(user_id=user.id, is_active=True, include_in_calculations=True).all()
        loans_ov = Loan.query.filter_by(user_id=user.id, is_paid_off=False, include_in_calculations=True).all()
        credit_cards_ov = CreditCard.query.filter_by(user_id=user.id, include_in_calculations=True).all()

    # Build timeline
    timeline = []
    # Income events
    for source in income_sources_ov:
        income_dates = get_future_income_dates(source, start_date, end_date)
        for date in income_dates:
            timeline.append({
                'date': date,
                'type': 'income',
                'description': source.name,
                'amount': source.amount,
                'category': 'Income',
                'excluded': False
            })
    # Bill expenses
    for bill in bills_ov:
        current_date = start_date
        while current_date <= end_date:
            if current_date >= bill.due_date or current_date.day == bill.due_date.day:
                timeline.append({
                    'date': current_date,
                    'type': 'expense',
                    'description': bill.name,
                    'amount': -bill.amount,
                    'category': 'Bills',
                    'excluded': not getattr(bill, 'include_in_calculations', True)
                })
            current_date = add_months(current_date, 1)
    # Subscription expenses
    for sub in subscriptions_ov:
        current_date = sub.next_billing_date
        interval_days = 30 if sub.billing_cycle == 'Monthly' else (365 if sub.billing_cycle == 'Yearly' else 7)
        while current_date <= end_date:
            if current_date >= start_date:
                timeline.append({
                    'date': current_date,
                    'type': 'expense',
                    'description': sub.name,
                    'amount': -sub.amount,
                    'category': 'Subscriptions',
                    'excluded': not getattr(sub, 'include_in_calculations', True)
                })
            current_date += timedelta(days=interval_days)
    # Loan payments
    for loan in loans_ov:
        current_date = loan.next_payment_date
        while current_date <= end_date:
            if current_date >= start_date:
                timeline.append({
                    'date': current_date,
                    'type': 'expense',
                    'description': f"{loan.name} Payment",
                    'amount': -loan.monthly_payment,
                    'category': 'Loans',
                    'excluded': not getattr(loan, 'include_in_calculations', True)
                })
            current_date = add_months(current_date, 1)
    # Credit card minimum payments
    for card in credit_cards_ov:
        if card.minimum_payment:
            current_date = card.payment_due_date
            while current_date <= end_date:
                if current_date >= start_date:
                    timeline.append({
                        'date': current_date,
                        'type': 'expense',
                        'description': f"{card.name} Min Payment",
                        'amount': -card.minimum_payment,
                        'category': 'Credit Cards',
                        'excluded': not getattr(card, 'include_in_calculations', True)
                    })
                current_date = add_months(current_date, 1)
    # Sort timeline by date
    timeline.sort(key=lambda x: x['date'])
    # Calculate running balance
    running_balance = 0
    for item in timeline:
        if include_excluded or not item.get('excluded', False):
            running_balance += item['amount']
        item['running_balance'] = running_balance
    # Summary stats
    if include_excluded:
        total_income = sum(item['amount'] for item in timeline if item['type'] == 'income')
        total_expenses = sum(-item['amount'] for item in timeline if item['type'] == 'expense')
    else:
        total_income = sum(item['amount'] for item in timeline if item['type'] == 'income')
        total_expenses = sum(-item['amount'] for item in timeline if item['type'] == 'expense' and not item.get('excluded', False))
    net_income = total_income - total_expenses
    excluded_expenses = sum(-item['amount'] for item in timeline if item['type'] == 'expense' and item.get('excluded', False))

    return render_template(
        'dashboard.html',
        user=user,
        bills=upcoming_bills,
        credit_cards=credit_cards,
        urgent_bills=urgent_bills,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        monthly_expenses_all=monthly_expenses_all,
        debt_to_income_ratio=debt_to_income_ratio,
        next_income_dates=next_income_dates[:5],
        today=today,
        # Overview variables:
        timeline=timeline,
        start_date=start_date,
        end_date=end_date,
        total_income=total_income,
        total_expenses=total_expenses,
        net_income=net_income,
        excluded_expenses=excluded_expenses,
        include_excluded=include_excluded,
        current_page='dashboard'
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
        income_type = request.form.get('income_type', 'Employment')
        
        new_income = IncomeSource(
            name=name,
            amount=amount,
            frequency=frequency,
            user_id=session['user_id'],
            income_type=income_type
        )
        
        # Handle different frequency types
        if frequency == 'weekly':
            new_income.day_of_week = request.form.get('day_of_week')
            new_income.next_payment_date = datetime.strptime(request.form.get('next_payment_date'), '%Y-%m-%d').date()
        elif frequency == 'biweekly':
            new_income.next_payment_date = datetime.strptime(request.form.get('next_payment_date'), '%Y-%m-%d').date()
        elif frequency == 'monthly':
            new_income.payment_day_1 = int(request.form.get('payment_day_1'))
        elif frequency == 'bimonthly':
            new_income.payment_day_1 = int(request.form.get('payment_day_1'))
            new_income.payment_day_2 = int(request.form.get('payment_day_2'))
        elif frequency in ['quarterly', 'annually']:
            new_income.next_payment_date = datetime.strptime(request.form.get('next_payment_date'), '%Y-%m-%d').date()
        elif frequency == 'onetime':
            new_income.one_time_date = datetime.strptime(request.form.get('one_time_date'), '%Y-%m-%d').date()
        
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
    
    return render_template('income.html', income_sources=user_income, current_page='income')

# @app.route('/overview')
# def overview():
#     if 'user_id' not in session:
#         return redirect(url_for('login'))
    
#     # Get date range from request or default to next 3 months
#     start_date_str = request.args.get('start_date')
#     end_date_str = request.args.get('end_date')
#     include_excluded_str = request.args.get('include_excluded', 'false')
#     include_excluded = include_excluded_str.lower() == 'true'
    
#     if start_date_str and end_date_str:
#         start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
#         end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
#     else:
#         start_date = datetime.now().date()
#         end_date = start_date + timedelta(days=90)
    
#     # Get all income sources (income always included)
#     income_sources = IncomeSource.query.filter_by(user_id=session['user_id'], is_active=True).all()
    
#     # Get all recurring expenses - filter based on include_excluded setting
#     if include_excluded:
#         bills = Bill.query.filter_by(user_id=session['user_id'], recurring=True).all()
#         subscriptions = Subscription.query.filter_by(user_id=session['user_id'], is_active=True).all()
#         loans = Loan.query.filter_by(user_id=session['user_id'], is_paid_off=False).all()
#         credit_cards = CreditCard.query.filter_by(user_id=session['user_id']).all()
#     else:
#         bills = Bill.query.filter_by(user_id=session['user_id'], recurring=True, include_in_calculations=True).all()
#         subscriptions = Subscription.query.filter_by(user_id=session['user_id'], is_active=True, include_in_calculations=True).all()
#         loans = Loan.query.filter_by(user_id=session['user_id'], is_paid_off=False, include_in_calculations=True).all()
#         credit_cards = CreditCard.query.filter_by(user_id=session['user_id'], include_in_calculations=True).all()
    
#     # Build comprehensive timeline
#     timeline = []
    
#     # Add income events
#     for source in income_sources:
#         income_dates = get_future_income_dates(source, start_date, end_date)
#         for date in income_dates:
#             timeline.append({
#                 'date': date,
#                 'type': 'income',
#                 'description': source.name,
#                 'amount': source.amount,
#                 'category': 'Income',
#                 'excluded': False
#             })
    
#     # Add bill expenses (recurring)
#     for bill in bills:
#         current_date = start_date
#         while current_date <= end_date:
#             # For simplicity, assume monthly bills
#             if current_date >= bill.due_date or current_date.day == bill.due_date.day:
#                 timeline.append({
#                     'date': current_date,
#                     'type': 'expense',
#                     'description': bill.name,
#                     'amount': -bill.amount,
#                     'category': 'Bills',
#                     'excluded': not getattr(bill, 'include_in_calculations', True)
#                 })
            
#             # Move to next month using safe helper function
#             current_date = add_months(current_date, 1)
    
#     # Add subscription expenses
#     for sub in subscriptions:
#         current_date = sub.next_billing_date
#         interval_days = 30 if sub.billing_cycle == 'Monthly' else (365 if sub.billing_cycle == 'Yearly' else 7)
        
#         while current_date <= end_date:
#             if current_date >= start_date:
#                 timeline.append({
#                     'date': current_date,
#                     'type': 'expense',
#                     'description': sub.name,
#                     'amount': -sub.amount,
#                     'category': 'Subscriptions',
#                     'excluded': not getattr(sub, 'include_in_calculations', True)
#                 })
#             current_date += timedelta(days=interval_days)
    
#     # Add loan payments
#     for loan in loans:
#         current_date = loan.next_payment_date
#         while current_date <= end_date:
#             if current_date >= start_date:
#                 timeline.append({
#                     'date': current_date,
#                     'type': 'expense',
#                     'description': f"{loan.name} Payment",
#                     'amount': -loan.monthly_payment,
#                     'category': 'Loans',
#                     'excluded': not getattr(loan, 'include_in_calculations', True)
#                 })
            
#             # Move to next month using safe helper function
#             current_date = add_months(current_date, 1)
    
#     # Add credit card minimum payments
#     for card in credit_cards:
#         if card.minimum_payment:
#             current_date = card.payment_due_date
#             while current_date <= end_date:
#                 if current_date >= start_date:
#                     timeline.append({
#                         'date': current_date,
#                         'type': 'expense',
#                         'description': f"{card.name} Min Payment",
#                         'amount': -card.minimum_payment,
#                         'category': 'Credit Cards',
#                         'excluded': not getattr(card, 'include_in_calculations', True)
#                     })
                
#                 # Move to next month using safe helper function
#                 current_date = add_months(current_date, 1)
    
#     # Sort timeline by date
#     timeline.sort(key=lambda x: x['date'])
    
#     # Calculate running balance (only for non-excluded items unless include_excluded is True)
#     running_balance = 0
#     for item in timeline:
#         if include_excluded or not item.get('excluded', False):
#             running_balance += item['amount']
#         item['running_balance'] = running_balance
    
#     # Calculate summary stats
#     if include_excluded:
#         total_income = sum(item['amount'] for item in timeline if item['type'] == 'income')
#         total_expenses = sum(-item['amount'] for item in timeline if item['type'] == 'expense')
#     else:
#         total_income = sum(item['amount'] for item in timeline if item['type'] == 'income')
#         total_expenses = sum(-item['amount'] for item in timeline if item['type'] == 'expense' and not item.get('excluded', False))
    
#     net_income = total_income - total_expenses
    
#     # Calculate excluded amounts for display
#     excluded_expenses = sum(-item['amount'] for item in timeline if item['type'] == 'expense' and item.get('excluded', False))
    
#     return render_template('overview.html',
#                          timeline=timeline,
#                          start_date=start_date,
#                          end_date=end_date,
#                          total_income=total_income,
#                          total_expenses=total_expenses,
#                          net_income=net_income,
#                          excluded_expenses=excluded_expenses,
#                          include_excluded=include_excluded,
#                          current_page='overview')

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
        include_in_calculations = 'include_in_calculations' in request.form  # NEW FIELD
        
        new_bill = Bill(
            name=name,
            amount=amount,
            due_date=due_date,
            category=category,
            recurring=recurring,
            include_in_calculations=include_in_calculations,  # NEW FIELD
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
    
    return render_template('bills.html', bills=user_bills, subscriptions=user_subscriptions, loans=user_loans, current_page='bills')

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
    return render_template('subscriptions.html', subscriptions=user_subscriptions, current_page='subscriptions')

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

        # NEW: Exclude from calculations checkbox
        include_in_calculations = 'exclude_from_calculations' not in request.form

        new_loan = Loan(
            name=name,
            loan_type=loan_type,
            principal_amount=principal_amount,
            current_balance=current_balance,
            monthly_payment=monthly_payment,
            interest_rate=interest_rate,
            next_payment_date=next_payment_date,
            term_months=term_months,
            include_in_calculations=include_in_calculations,
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
        pass 
    
    # Option: toggle inclusion via query param or session
    include_student_loans = request.args.get('include_student_loans', 'false').lower() == 'true'

    all_loans = Loan.query.filter_by(user_id=session['user_id'], is_paid_off=False).order_by(Loan.next_payment_date).all()
    student_loans = [loan for loan in all_loans if loan.loan_type.lower() == 'student']
    other_loans = [loan for loan in all_loans if loan.loan_type.lower() != 'student']

    # Only include student loans in main table if requested
    loans_for_table = other_loans + student_loans if include_student_loans else other_loans

    return render_template(
        'loans.html',
        loans=loans_for_table,
        student_loans=student_loans,
        include_student_loans=include_student_loans,
        current_page='loans'
    )

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
        
        # Calculate minimum payment automatically
        minimum_payment = calculate_minimum_payment(
            current_balance=current_balance,
            interest_rate=interest_rate,
            credit_limit=limit,
            min_percentage=2.0,  # 2% of balance
            min_amount=25.0      # $25 minimum
        )
        
        new_card = CreditCard(
            name=name,
            last_four=last_four,
            limit=limit,
            current_balance=current_balance,
            payment_due_date=payment_due_date,
            interest_rate=interest_rate,
            minimum_payment=minimum_payment,  # Use calculated minimum payment
            auto_pay_minimum=auto_pay_minimum,
            auto_payment_amount=auto_payment_amount,
            user_id=session['user_id']
        )
        
        try:
            db.session.add(new_card)
            db.session.commit()
            flash('Credit card added successfully with calculated minimum payment!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error adding credit card. Please try again.', 'danger')
            print(f"Error adding credit card: {e}")
            
        return redirect(url_for('credit_cards'))
    
    user_cards = CreditCard.query.filter_by(user_id=session['user_id']).all()
    
    # Update minimum payments for all cards before displaying
    update_minimum_payments_for_user(session['user_id'])
    
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
                         overall_utilization=overall_utilization,
                         current_page='credit-cards')

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
        return redirect(url_for('loans'))
    
    if request.method == 'POST':
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
            # Support editing exclusion
            loan.include_in_calculations = 'exclude_from_calculations' not in request.form
            db.session.commit()
            flash('Loan updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating loan. Please try again.', 'danger')
            print(f"Error editing loan: {e}")
    return redirect(url_for('loans'))

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
            current_balance = float(request.form.get('current_balance'))
            card.current_balance = current_balance
            card.interest_rate = float(request.form.get('interest_rate')) if request.form.get('interest_rate') else None
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
            
            # Recalculate minimum payment with updated values
            card.minimum_payment = calculate_minimum_payment(
                current_balance=current_balance,
                interest_rate=card.interest_rate,
                credit_limit=card.limit,
                min_percentage=2.0,  # 2% of balance
                min_amount=25.0      # $25 minimum
            )
            
            db.session.commit()
            flash('Credit card updated successfully with recalculated minimum payment!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating credit card. Please try again.', 'danger')
            print(f"Error editing credit card: {e}")
        
    return redirect(url_for('credit_cards'))

# Add this route after your existing edit routes, around line 1200-1300

@app.route('/delete/income/<int:income_id>')
def delete_income(income_id):
    """Delete an income source"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    income = IncomeSource.query.get_or_404(income_id)
    if income.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('income'))
    
    # Backup before deleting
    backup_database()
    
    try:
        income_name = income.name
        db.session.delete(income)
        db.session.commit()
        flash(f'Income source "{income_name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting income source. Please try again.', 'danger')
        print(f"Error deleting income source: {e}")
    
    return redirect(url_for('income'))

# Add this route after the existing edit routes

@app.route('/edit/income/<int:income_id>', methods=['POST'])
def edit_income(income_id):
    """Edit an income source"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    income = IncomeSource.query.get_or_404(income_id)
    if income.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('income'))
    
    if request.method == 'POST':
        # Backup before editing
        backup_database()
        
        try:
            income.name = request.form.get('name')
            income.amount = float(request.form.get('amount'))
            income.frequency = request.form.get('frequency')
            income.is_active = 'is_active' in request.form
            
            # Clear frequency-specific fields first
            income.payment_day_1 = None
            income.payment_day_2 = None
            income.next_payment_date = None
            income.day_of_week = None
            income.one_time_date = None  # Clear one-time date
            
            # Handle different frequency types
            frequency = income.frequency
            if frequency == 'weekly':
                income.day_of_week = request.form.get('day_of_week')
                income.next_payment_date = datetime.strptime(request.form.get('next_payment_date'), '%Y-%m-%d').date()
            elif frequency == 'biweekly':
                income.next_payment_date = datetime.strptime(request.form.get('next_payment_date'), '%Y-%m-%d').date()
            elif frequency == 'monthly':
                income.payment_day_1 = int(request.form.get('payment_day_1'))
            elif frequency == 'bimonthly':
                income.payment_day_1 = int(request.form.get('payment_day_1'))
                income.payment_day_2 = int(request.form.get('payment_day_2'))
            elif frequency in ['quarterly', 'annually']:
                income.next_payment_date = datetime.strptime(request.form.get('next_payment_date'), '%Y-%m-%d').date()
            elif frequency == 'onetime':
                income.one_time_date = datetime.strptime(request.form.get('one_time_date'), '%Y-%m-%d').date()
            
            db.session.commit()
            flash('Income source updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating income source. Please try again.', 'danger')
            print(f"Error editing income source: {e}")
        
    return redirect(url_for('income'))

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
                'day_of_week': income.day_of_week,
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
                        day_of_week=income_data.get('day_of_week'),
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

# Make sure these routes are in your file (they should be after your utility functions but before the main block)

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
            return redirect(url_for('login'))
            
    except Exception as e:
        flash(f'Demo setup error: {str(e)}', 'danger')
        return redirect(url_for('login'))

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

@app.route('/wiki')
def wiki():
    """Project documentation and wiki"""
    return render_template('wiki.html', current_page='wiki')

@app.route('/wiki/<section>')
def wiki_section(section):
    """Specific wiki section"""
    valid_sections = [
        'overview', 'features', 'installation', 'configuration', 
        'database', 'api', 'user-guide', 'development', 'deployment',
        'security', 'backup', 'troubleshooting'
    ]
    
    if section not in valid_sections:
        flash('Wiki section not found', 'warning')
        return redirect(url_for('wiki'))
    
    return render_template('wiki.html', active_section=section)

@app.route('/health')
def health_check():
    """Health check endpoint for Nginx"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

# Add these utility functions for budget calculations

def get_budget_summary(user_id, period_id=None):
    """Get comprehensive budget summary for a user and period"""
    if period_id:
        period = BudgetPeriod.query.filter_by(id=period_id, user_id=user_id).first()
    else:
        # Get current active period
        today = datetime.now().date()
        period = BudgetPeriod.query.filter(
            BudgetPeriod.user_id == user_id,
            BudgetPeriod.start_date <= today,
            BudgetPeriod.end_date >= today,
            BudgetPeriod.is_active == True
        ).first()
    
    if not period:
        return None
    
    # Get all budget items for this period
    budget_items = BudgetItem.query.filter_by(period_id=period.id, user_id=user_id).all()
    
    # Calculate totals
    total_planned_income = 0
    total_planned_expenses = 0
    total_actual_income = 0
    total_actual_expenses = 0
    
    categories_summary = []
    
    for item in budget_items:
        # Update actual amount from transactions
        actual = db.session.query(db.func.sum(BudgetTransaction.amount)).filter_by(
            category_id=item.category_id,
            period_id=period.id,
            user_id=user_id
        ).scalar() or 0.0
        
        item.actual_amount = actual
        
        if item.category.is_income:
            total_planned_income += item.planned_amount
            total_actual_income += actual
        else:
            total_planned_expenses += item.planned_amount
            total_actual_expenses += actual
        
        # Calculate variance and percentage
        variance = actual - item.planned_amount
        percentage = (actual / item.planned_amount * 100) if item.planned_amount > 0 else 0
        
        categories_summary.append({
            'item': item,
            'category': item.category,
            'variance': variance,
            'percentage': percentage,
            'status': get_budget_status(percentage, item.category.is_income)
        })
    
    # Calculate overall metrics
    planned_surplus = total_planned_income - total_planned_expenses
    actual_surplus = total_actual_income - total_actual_expenses
    
    return {
        'period': period,
        'total_planned_income': total_planned_income,
        'total_planned_expenses': total_planned_expenses,
        'total_actual_income': total_actual_income,
        'total_actual_expenses': total_actual_expenses,
        'planned_surplus': planned_surplus,
        'actual_surplus': actual_surplus,
        'categories': categories_summary,
        'savings_rate': (actual_surplus / total_actual_income * 100) if total_actual_income > 0 else 0
    }

def get_budget_status(percentage, is_income=False):
    """Determine budget status based on percentage spent/earned"""
    if is_income:
        if percentage >= 100:
            return 'excellent'
        elif percentage >= 80:
            return 'good'
        elif percentage >= 60:
            return 'warning'
        else:
            return 'danger'
    else:  # Expense categories
        if percentage <= 80:
            return 'excellent'
        elif percentage <= 95:
            return 'good'
        elif percentage <= 105:
            return 'warning'
        else:
            return 'danger'

def create_default_budget_categories(user_id):
    """Create default budget categories for a new user"""
    default_categories = [
        # Income Categories
        {'name': 'Salary', 'description': 'Primary employment income', 'color': '#28a745', 'icon': 'bi-cash-stack', 'is_income': True, 'sort_order': 1},
        {'name': 'Side Income', 'description': 'Freelance, side jobs, other income', 'color': '#20c997', 'icon': 'bi-briefcase', 'is_income': True, 'sort_order': 2},
        {'name': 'Investment Income', 'description': 'Dividends, interest, capital gains', 'color': '#17a2b8', 'icon': 'bi-graph-up', 'is_income': True, 'sort_order': 3},
        
        # Essential Expense Categories
        {'name': 'Housing', 'description': 'Rent, mortgage, utilities', 'color': '#dc3545', 'icon': 'bi-house', 'is_income': False, 'sort_order': 10},
        {'name': 'Transportation', 'description': 'Car payment, gas, insurance, public transit', 'color': '#fd7e14', 'icon': 'bi-car-front', 'is_income': False, 'sort_order': 11},
        {'name': 'Food & Groceries', 'description': 'Groceries, dining out, meal delivery', 'color': '#ffc107', 'icon': 'bi-cart', 'is_income': False, 'sort_order': 12},
        {'name': 'Healthcare', 'description': 'Insurance, medical bills, prescriptions', 'color': '#e83e8c', 'icon': 'bi-heart-pulse', 'is_income': False, 'sort_order': 13},
        {'name': 'Insurance', 'description': 'Life, health, auto, home insurance', 'color': '#6610f2', 'icon': 'bi-shield-check', 'is_income': False, 'sort_order': 14},
        
        # Lifestyle Categories
        {'name': 'Entertainment', 'description': 'Movies, concerts, hobbies, subscriptions', 'color': '#6f42c1', 'icon': 'bi-play-circle', 'is_income': False, 'sort_order': 20},
        {'name': 'Shopping', 'description': 'Clothing, electronics, personal items', 'color': '#d63384', 'icon': 'bi-bag', 'is_income': False, 'sort_order': 21},
        {'name': 'Travel', 'description': 'Vacations, flights, hotels', 'color': '#0dcaf0', 'icon': 'bi-airplane', 'is_income': False, 'sort_order': 22},
        {'name': 'Personal Care', 'description': 'Haircuts, gym, spa, personal services', 'color': '#198754', 'icon': 'bi-person', 'is_income': False, 'sort_order': 23},
        
        # Financial Categories
        {'name': 'Savings', 'description': 'Emergency fund, general savings', 'color': '#0d6efd', 'icon': 'bi-piggy-bank', 'is_income': False, 'sort_order': 30},
        {'name': 'Investments', 'description': '401k, IRA, stocks, retirement', 'color': '#198754', 'icon': 'bi-graph-up-arrow', 'is_income': False, 'sort_order': 31},
        {'name': 'Debt Payments', 'description': 'Credit cards, loans, debt payoff', 'color': '#dc3545', 'icon': 'bi-credit-card', 'is_income': False, 'sort_order': 32},
        
        # Other
        {'name': 'Miscellaneous', 'description': 'Other expenses not categorized', 'color': '#6c757d', 'icon': 'bi-three-dots', 'is_income': False, 'sort_order': 99},
    ]
    
    for cat_data in default_categories:
        category = BudgetCategory(
            user_id=user_id,
            **cat_data
        )
        db.session.add(category)
    
    db.session.commit()

def create_current_budget_period(user_id):
    """Create current month budget period"""
    today = datetime.now().date()
    start_date = today.replace(day=1)
    
    # Calculate end of month - FIX THIS LINE:
    if start_date.month == 12:
        end_date = start_date.replace(year=start_date.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_date = start_date.replace(month=start_date.month + 1, day=1) - timedelta(days=1)
    
    period_name = start_date.strftime("%B %Y")
    
    period = BudgetPeriod(
        user_id=user_id,
        name=period_name,
        period_type='monthly',
        start_date=start_date,
        end_date=end_date,
        is_active=True,
        auto_rollover=True
    )
    
    db.session.add(period)
    db.session.commit()
    return period

# Add these routes after your existing routes

@app.route('/budget')
def budget():
    """Main budget dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Check if user has budget categories, if not create defaults
    categories_count = BudgetCategory.query.filter_by(user_id=user_id).count()
    if categories_count == 0:
        create_default_budget_categories(user_id)
    
    # Check if user has current period, if not create one
    today = datetime.now().date()
    current_period = BudgetPeriod.query.filter(
        BudgetPeriod.user_id == user_id,
        BudgetPeriod.start_date <= today,
        BudgetPeriod.end_date >= today,
        BudgetPeriod.is_active == True
    ).first()
    
    if not current_period:
        current_period = create_current_budget_period(user_id)
    
    # Get budget summary
    budget_summary = get_budget_summary(user_id, current_period.id)
    
    # Get recent transactions
    recent_transactions = BudgetTransaction.query.filter_by(
        user_id=user_id, 
        period_id=current_period.id
    ).order_by(BudgetTransaction.transaction_date.desc()).limit(10).all()
    
    # Get budget goals
    active_goals = BudgetGoal.query.filter_by(user_id=user_id, is_active=True).order_by(BudgetGoal.priority.desc()).all()
    
    # Get all periods for dropdown
    all_periods = BudgetPeriod.query.filter_by(user_id=user_id).order_by(BudgetPeriod.start_date.desc()).all()
    
    return render_template('budget.html',
                         budget_summary=budget_summary,
                         recent_transactions=recent_transactions,
                         active_goals=active_goals,
                         all_periods=all_periods,
                         current_period=current_period,
                         current_page='budget')

@app.route('/budget/categories', methods=['GET', 'POST'])
def budget_categories():
    """Manage budget categories"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        backup_database()
        
        name = request.form.get('name')
        description = request.form.get('description', '')
        color = request.form.get('color', '#667eea')
        icon = request.form.get('icon', 'bi-wallet2')
        is_income = 'is_income' in request.form
        
        new_category = BudgetCategory(
            name=name,
            description=description,
            color=color,
            icon=icon,
            is_income=is_income,
            user_id=session['user_id']
        )
        
        try:
            db.session.add(new_category)
            db.session.commit()
            flash('Budget category added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error adding category. Please try again.', 'danger')
            print(f"Error adding budget category: {e}")
        
        return redirect(url_for('budget_categories'))
    
    # Get all categories for user
    income_categories = BudgetCategory.query.filter_by(
        user_id=session['user_id'], 
        is_income=True, 
        is_active=True
    ).order_by(BudgetCategory.sort_order).all()
    
    expense_categories = BudgetCategory.query.filter_by(
        user_id=session['user_id'], 
        is_income=False, 
        is_active=True
    ).order_by(BudgetCategory.sort_order).all()
    
    return render_template('budget_categories.html',
                         income_categories=income_categories,
                         expense_categories=expense_categories)

@app.route('/budget/transactions', methods=['GET', 'POST'])
def budget_transactions():
    """Manage budget transactions"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        backup_database()
        
        category_id = int(request.form.get('category_id'))
        description = request.form.get('description')
        amount = float(request.form.get('amount'))
        transaction_date = datetime.strptime(request.form.get('transaction_date'), '%Y-%m-%d').date()
        notes = request.form.get('notes', '')
        tags = request.form.get('tags', '')
        
        # Find appropriate period for this transaction
        period = BudgetPeriod.query.filter(
            BudgetPeriod.user_id == session['user_id'],
            BudgetPeriod.start_date <= transaction_date,
            BudgetPeriod.end_date >= transaction_date
        ).first()
        
        if not period:
            flash('No budget period found for this date. Please create a budget period first.', 'warning')
            return redirect(url_for('budget_transactions'))
        
        new_transaction = BudgetTransaction(
            category_id=category_id,
            period_id=period.id,
            description=description,
            amount=amount,
            transaction_date=transaction_date,
            notes=notes,
            tags=tags,
            user_id=session['user_id']
        )
        
        try:
            db.session.add(new_transaction)
            db.session.commit()
            flash('Transaction added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error adding transaction. Please try again.', 'danger')
            print(f"Error adding budget transaction: {e}")
        
        return redirect(url_for('budget_transactions'))
    
    # Get transactions for current period
    today = datetime.now().date()
    current_period = BudgetPeriod.query.filter(
        BudgetPeriod.user_id == session['user_id'],
        BudgetPeriod.start_date <= today,
        BudgetPeriod.end_date >= today,
        BudgetPeriod.is_active == True
    ).first()
    
    transactions = []
    if current_period:
        transactions = BudgetTransaction.query.filter_by(
            user_id=session['user_id'],
            period_id=current_period.id
        ).order_by(BudgetTransaction.transaction_date.desc()).all()
    
    # Get categories for dropdown
    categories = BudgetCategory.query.filter_by(
        user_id=session['user_id'], 
        is_active=True
    ).order_by(BudgetCategory.is_income.desc(), BudgetCategory.name).all()
    
    return render_template('budget_transactions.html',
                         transactions=transactions,
                         categories=categories,
                         current_period=current_period)

@app.route('/budget/goals', methods=['GET', 'POST'])
def budget_goals():
    """Manage budget goals"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        backup_database()
        
        title = request.form.get('title')
        description = request.form.get('description', '')
        target_amount = float(request.form.get('target_amount'))
        target_date = datetime.strptime(request.form.get('target_date'), '%Y-%m-%d').date() if request.form.get('target_date') else None
        category = request.form.get('category', '')
        priority = request.form.get('priority', 'medium')
        auto_contribute = float(request.form.get('auto_contribute', 0.0))
        
        new_goal = BudgetGoal(
            title=title,
            description=description,
            target_amount=target_amount,
            target_date=target_date,
            category=category,
            priority=priority,
            auto_contribute=auto_contribute,
            user_id=session['user_id']
        )
        
        try:
            db.session.add(new_goal)
            db.session.commit()
            flash('Budget goal added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error adding goal. Please try again.', 'danger')
            print(f"Error adding budget goal: {e}")
        
        return redirect(url_for('budget_goals'))
    
    # Get all goals for user
    active_goals = BudgetGoal.query.filter_by(user_id=session['user_id'], is_active=True).order_by(BudgetGoal.priority.desc()).all()
    achieved_goals = BudgetGoal.query.filter_by(user_id=session['user_id'], is_achieved=True).order_by(BudgetGoal.target_date.desc()).all()
    
    return render_template('budget_goals.html',
                         active_goals=active_goals,
                         achieved_goals=achieved_goals)

@app.route('/budget/periods', methods=['GET', 'POST'])
def budget_periods():
    """Manage budget periods"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        backup_database()
        
        name = request.form.get('name')
        period_type = request.form.get('period_type')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        auto_rollover = 'auto_rollover' in request.form
        notes = request.form.get('notes', '')
        
        new_period = BudgetPeriod(
            name=name,
            period_type=period_type,
            start_date=start_date,
            end_date=end_date,
            auto_rollover=auto_rollover,
            notes=notes,
            user_id=session['user_id']
        )
        
        try:
            db.session.add(new_period)
            db.session.commit()
            flash('Budget period added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error adding period. Please try again.', 'danger')
            print(f"Error adding budget period: {e}")
        
        return redirect(url_for('budget_periods'))
    
    # Get all periods for user
    periods = BudgetPeriod.query.filter_by(user_id=session['user_id']).order_by(BudgetPeriod.start_date.desc()).all()
    
    return render_template('budget_periods.html', periods=periods)

@app.route('/budget/items', methods=['GET', 'POST'])
def budget_items():
    """Manage budget items"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        backup_database()
        
        category_id = int(request.form.get('category_id'))
        period_id = int(request.form.get('period_id'))
        planned_amount = float(request.form.get('planned_amount'))
        notes = request.form.get('notes', '')
        alert_threshold = float(request.form.get('alert_threshold', 0.0))
        is_rollover = 'is_rollover' in request.form
        
        new_item = BudgetItem(
            category_id=category_id,
            period_id=period_id,
            planned_amount=planned_amount,
            notes=notes,
            alert_threshold=alert_threshold,
            is_rollover=is_rollover,
            user_id=session['user_id']
        )
        
        try:
            db.session.add(new_item)
            db.session.commit()
            flash('Budget item added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error adding item. Please try again.', 'danger')
            print(f"Error adding budget item: {e}")
        
        return redirect(url_for('budget_items'))
    
@app.route('/budget/setup/<int:period_id>')
def budget_setup(period_id):
    """Set up budget for a specific period"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    period = BudgetPeriod.query.filter_by(id=period_id, user_id=session['user_id']).first_or_404()
    
    # Get all categories
    categories = BudgetCategory.query.filter_by(
        user_id=session['user_id'], 
        is_active=True
    ).order_by(BudgetCategory.is_income.desc(), BudgetCategory.sort_order).all()
    
    # Get existing budget items for this period
    budget_items = {}
    existing_items = BudgetItem.query.filter_by(period_id=period_id, user_id=session['user_id']).all()
    for item in existing_items:
        budget_items[item.category_id] = item
    
    return render_template('budget_setup.html',
                         period=period,
                         categories=categories,
                         budget_items=budget_items)

@app.route('/budget/save_setup', methods=['POST'])
def save_budget_setup():
    """Save budget setup for a period"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    backup_database()
    
    period_id = int(request.form.get('period_id'))
    period = BudgetPeriod.query.filter_by(id=period_id, user_id=session['user_id']).first_or_404()
    
    try:
        # Process each category
        for key, value in request.form.items():
            if key.startswith('planned_'):
                category_id = int(key.replace('planned_', ''))
                planned_amount = float(value) if value else 0.0
                
                # Get or create budget item
                budget_item = BudgetItem.query.filter_by(
                    category_id=category_id,
                    period_id=period_id,
                    user_id=session['user_id']
                ).first()
                
                if budget_item:
                    budget_item.planned_amount = planned_amount
                    budget_item.updated_at = datetime.utcnow()
                else:
                    budget_item = BudgetItem(
                        category_id=category_id,
                        period_id=period_id,
                        planned_amount=planned_amount,
                        user_id=session['user_id']
                    )
                    db.session.add(budget_item)
        
        db.session.commit()
        flash('Budget setup saved successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error saving budget setup. Please try again.', 'danger')
        print(f"Error saving budget setup: {e}")
    
    return redirect(url_for('budget'))

    # Get all items for current period
    today = datetime.now().date()
    current_period = BudgetPeriod.query.filter(
        BudgetPeriod.user_id == session['user_id'],
        BudgetPeriod.start_date <= today,
        BudgetPeriod.end_date >= today,
        BudgetPeriod.is_active == True
    ).first()
    
    items = []
    if current_period:
        items = BudgetItem.query.filter_by(
            user_id=session['user_id'],
            period_id=current_period.id
        ).order_by(BudgetItem.category_id).all()
    
    # Get categories and periods for dropdowns
    categories = BudgetCategory.query.filter_by(
        user_id=session['user_id'], 
        is_active=True
    ).order_by(BudgetCategory.is_income.desc(), BudgetCategory.name).all()
    
    periods = BudgetPeriod.query.filter_by(user_id=session['user_id']).order_by(BudgetPeriod.start_date.desc()).all()
    
    return render_template('budget_items.html',
                         items=items,
                         categories=categories,
                         periods=periods,
                         current_period=current_period)

def calculate_minimum_payment(current_balance, interest_rate=None, credit_limit=None, min_percentage=2.0, min_amount=25.0):
    """
    Calculate minimum payment for a credit card based on various methods.
    
    Args:
        current_balance (float): Current outstanding balance
        interest_rate (float, optional): Annual interest rate as percentage
        credit_limit (float, optional): Credit limit for percentage calculations
        min_percentage (float): Minimum percentage of balance (default 2%)
        min_amount (float): Absolute minimum payment amount (default $25)
    
    Returns:
        float: Calculated minimum payment
    """
    if not current_balance or current_balance <= 0:
        return 0.0
    
    # Method 1: Percentage of balance (most common)
    percentage_payment = current_balance * (min_percentage / 100)
    
    # Method 2: Interest + principal (more accurate)
    if interest_rate and interest_rate > 0:
        monthly_interest_rate = interest_rate / 100 / 12
        monthly_interest = current_balance * monthly_interest_rate
        # Principal payment (typically 1% of balance)
        principal_payment = current_balance * 0.01
        interest_plus_principal = monthly_interest + principal_payment
        
        # Use the higher of percentage or interest+principal method
        calculated_payment = max(percentage_payment, interest_plus_principal)
    else:
        calculated_payment = percentage_payment
    
    # Ensure minimum payment meets absolute minimum
    final_payment = max(calculated_payment, min_amount)
    
    # Don't require payment higher than the balance
    final_payment = min(final_payment, current_balance)
    
    return round(final_payment, 2)

def update_minimum_payments_for_user(user_id):
    """Update minimum payments for all credit cards belonging to a user"""
    credit_cards = CreditCard.query.filter_by(user_id=user_id).all()
    
    for card in credit_cards:
        if card.current_balance and card.current_balance > 0:
            # Calculate minimum payment
            min_payment = calculate_minimum_payment(
                current_balance=card.current_balance,
                interest_rate=card.interest_rate,
                credit_limit=card.limit,
                min_percentage=2.0,  # 2% of balance
                min_amount=25.0      # $25 minimum
            )
            
            # Update the card's minimum payment
            card.minimum_payment = min_payment
        else:
            # No balance = no minimum payment
            card.minimum_payment = 0.0
    
    try:
        db.session.commit()
        print(f"Updated minimum payments for {len(credit_cards)} credit cards")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error updating minimum payments: {e}")
        return False

@app.route('/budget/plan/<int:period_id>')
def plan_budget(period_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    period = BudgetPeriod.query.filter_by(id=period_id, user_id=user_id).first_or_404()

    # Get recommendations
    recommendations = plan_budget_framework(user_id, period_type=period.period_type)

    # Apply recommendations to BudgetItem records
    for rec in recommendations['categories']:
        category = rec['category']
        planned_amount = rec['planned_amount']

        # Get or create BudgetItem for this category/period
        budget_item = BudgetItem.query.filter_by(
            category_id=category.id,
            period_id=period.id,
            user_id=user_id
        ).first()
        if budget_item:
            budget_item.planned_amount = planned_amount
            budget_item.updated_at = datetime.utcnow()
        else:
            budget_item = BudgetItem(
                category_id=category.id,
                period_id=period.id,
                planned_amount=planned_amount,
                user_id=user_id
            )
            db.session.add(budget_item)

    db.session.commit()
    flash('Budget fields have been auto-populated with recommended amounts!', 'success')
    return redirect(url_for('budget_setup', period_id=period.id))

@app.route('/credit-cards/recalculate-minimums')
def recalculate_minimum_payments():
    """Manually recalculate minimum payments for all credit cards"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    success = update_minimum_payments_for_user(session['user_id'])
    
    if success:
        flash('Minimum payments recalculated successfully for all credit cards!', 'success')
    else:
        flash('Error recalculating minimum payments. Please try again.', 'danger')
    
    return redirect(url_for('credit_cards'))

@app.route('/delete/credit_card/<int:card_id>')
def delete_credit_card(card_id):
    """Delete a credit card"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    card = CreditCard.query.get_or_404(card_id)
    if card.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('credit_cards'))
    
    # Backup before deleting
    backup_database()
    
    try:
        card_name = card.name
        db.session.delete(card)
        db.session.commit()
        flash(f'Credit card "{card_name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting credit card. Please try again.', 'danger')
        print(f"Error deleting credit card: {e}")
    
    return redirect(url_for('credit_cards'))

@app.route('/delete/bill/<int:bill_id>')
def delete_bill(bill_id):
    """Delete a bill"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    bill = Bill.query.get_or_404(bill_id)
    if bill.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('bills'))
    
    # Backup before deleting
    backup_database()
    
    try:
        bill_name = bill.name
        db.session.delete(bill)
        db.session.commit()
        flash(f'Bill "{bill_name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting bill. Please try again.', 'danger')
        print(f"Error deleting bill: {e}")
    
    return redirect(url_for('bills'))

@app.route('/delete/subscription/<int:subscription_id>')
def delete_subscription(subscription_id):
    """Delete a subscription"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    subscription = Subscription.query.get_or_404(subscription_id)
    if subscription.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('subscriptions'))
    
    # Backup before deleting
    backup_database()
    
    try:
        subscription_name = subscription.name
        db.session.delete(subscription)
        db.session.commit()
        flash(f'Subscription "{subscription_name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting subscription. Please try again.', 'danger')
        print(f"Error deleting subscription: {e}")
    
    return redirect(url_for('subscriptions'))

@app.route('/delete/loan/<int:loan_id>')
def delete_loan(loan_id):
    """Delete a loan"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    loan = Loan.query.get_or_404(loan_id)
    if loan.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('loans'))
    
    # Backup before deleting
    backup_database()
    
    try:
        loan_name = loan.name
        db.session.delete(loan)
        db.session.commit()
        flash(f'Loan "{loan_name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting loan. Please try again.', 'danger')
        print(f"Error deleting loan: {e}")
    
    return redirect(url_for('loans'))

@app.route('/toggle/<string:item_type>/<int:item_id>')
def toggle_item_inclusion(item_type, item_id):
    """Toggle include_in_calculations for any item type"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    backup_database()
    
    try:
        item = None
        redirect_route = 'dashboard'
        
        if item_type == 'bill':
            item = Bill.query.get_or_404(item_id)
            redirect_route = 'bills'
        elif item_type == 'subscription':
            item = Subscription.query.get_or_404(item_id)
            redirect_route = 'subscriptions'
        elif item_type == 'loan':
            item = Loan.query.get_or_404(item_id)
            redirect_route = 'loans'
        elif item_type == 'credit_card':
            item = CreditCard.query.get_or_404(item_id)
            redirect_route = 'credit_cards'
        
        if item and item.user_id == session['user_id']:
            # Toggle the include_in_calculations field
            item.include_in_calculations = not getattr(item, 'include_in_calculations', True)
            db.session.commit()
            
            status = "included in" if item.include_in_calculations else "excluded from"
            flash(f'{item.name} is now {status} calculations', 'info')
        else:
            flash('Unauthorized access or item not found', 'danger')
            
    except Exception as e:
        db.session.rollback()
        flash('Error updating item. Please try again.', 'danger')
        print(f"Error toggling inclusion: {e}")
    
    return redirect(url_for(redirect_route))

@app.route('/payment_planner', methods=['GET', 'POST'])
def payment_planner():
    # Separate loans
    all_loans = Loan.query.filter_by(user_id=session.get('user_id'), is_paid_off=False, include_in_calculations=True).all()
    student_loans = [loan for loan in all_loans if loan.loan_type.lower() == 'student']
    other_loans = [loan for loan in all_loans if loan.loan_type.lower() != 'student']

    credit_cards = get_user_credit_cards()
    total_student_loan_min = sum(loan.monthly_payment for loan in student_loans)
    total_other_loan_min = sum(loan.monthly_payment for loan in other_loans)
    total_card_min = sum(card['min_payment'] for card in credit_cards)
    suggestion = None

    if request.method == 'POST':
        monthly_amount = float(request.form['monthly_amount'])
        required = total_student_loan_min + total_other_loan_min + total_card_min
        leftover = monthly_amount - required

        allocation = []
        # Always pay minimums
        for loan in other_loans:
            allocation.append({'type': 'Other Loan', 'name': loan.name, 'amount': loan.monthly_payment})
        for loan in student_loans:
            allocation.append({'type': 'Student Loan', 'name': loan.name, 'amount': loan.monthly_payment})
        for card in credit_cards:
            allocation.append({'type': 'Credit Card', 'name': card['name'], 'amount': card['min_payment']})

        # Custom logic: prioritize extra payments to student loans if leftover exists
        if leftover > 0:
            # Example: apply leftover to student loan with highest balance
            if student_loans:
                target_loan = max(student_loans, key=lambda l: l.current_balance)
                for alloc in allocation:
                    if alloc['type'] == 'Student Loan' and alloc['name'] == target_loan.name:
                        alloc['amount'] += leftover
                        break
            else:
                # If no student loans, apply to highest balance credit card
                if credit_cards:
                    target_card = max(credit_cards, key=lambda c: c['balance'])
                    for alloc in allocation:
                        if alloc['type'] == 'Credit Card' and alloc['name'] == target_card['name']:
                            alloc['amount'] += leftover
                            break

        suggestion = {
            'required': required,
            'leftover': leftover if leftover > 0 else 0,
            'allocation': allocation
        }

    return render_template(
        'payment_planner.html',
        student_loans=student_loans,
        other_loans=other_loans,
        credit_cards=credit_cards,
        total_student_loan_min=total_student_loan_min,
        total_other_loan_min=total_other_loan_min,
        total_card_min=total_card_min,
        suggestion=suggestion,
        csrf_token=generate_csrf(),
        current_page='payment_planner'
    )


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    print(f"[ERROR 404] {request.path} | {error}")
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    print(f"[ERROR 500] {request.path} | {error}")
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    print(f"[ERROR 403] {request.path} | {error}")
    return render_template('errors/403.html'), 403

# Context processors for global template variables
@app.context_processor
def inject_demo_mode():
    """Make demo_mode available to all templates"""
    return dict(demo_mode='demo_mode' in session)

@app.context_processor
def inject_config():
    """Make config available to all templates"""
    return dict(config=app.config)

# Development and production startup
if __name__ == '__main__':
    run_safe_migrations()

    # Print startup information
    print("=== Vance Finance Starting ===")
    print(f"Environment: {'Development' if app.config['DEVELOPMENT_MODE'] else 'Production'}")
    print(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"Secret Key: {'Set' if app.config['SECRET_KEY'] else 'Not Set'}")

    # Check if any users exist
    with app.app_context():
        user_count = db.session.query(db.func.count(User.id)).scalar()
        print(f"Users in database: {user_count}")
        if user_count == 0:
            print("No users found. New users can register or try the demo.")
        print("================================")

    # Run the application
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config['DEVELOPMENT_MODE'],
        threaded=True
    )

