# Vance Financial Assistant

A web-based financial management application built with Flask that helps you track and visualize your bills and credit cards. This application focuses on providing a clean, flat design interface for managing your financial information without the complexity of payment tracking.

## Features

- **User Authentication**: Secure registration and login system with password hashing
- **Bill Management**: Add, view, and edit bills with categories and recurring payment options
- **Credit Card Tracking**: Manage credit card information including limits, balances, and due dates
- **Dashboard Overview**: Quick view of urgent bills and credit card summaries
- **Clickable Editing**: Edit bills and credit cards directly from the dashboard
- **Flat Design Interface**: Clean, modern UI with minimal visual clutter
- **Responsive Design**: Works well on desktop and mobile devices

## Quick Start Guide

1. Run `python static_setup.py`
2. Run `python Vance_Financial_Assistant.py`
3. Open `http://localhost:5001`
4. Register a new account
5. Start adding your bills and credit cards
6. Use the dashboard for quick overviews and editing

Your financial data is stored locally in the SQLite database file.

## Technology Stack

- **Backend**: Python Flask
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: HTML5, CSS3, JavaScript
- **Styling**: Bootstrap 5 with custom flat design CSS
- **Icons**: Bootstrap Icons

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Setup Instructions

1. **Clone or download the project files**

2. **Install required dependencies**
   pip install flask flask-sqlalchemy werkzeug

3. **Run the setup script to create static folder structure**
   python static_setup.py

4. **Start the application**
   python Vance_Financial_Assistant.py

5. **Access the application**:
   Open your web browser and navigate to `http://localhost:5001`


## Usage

### Getting Started

1. **Register an Account**: Visit the registration page to create your user account
2. **Login**: Use your credentials to access the application
3. **Add Bills**: Navigate to the Bills page to add your recurring and one-time bills
4. **Add Credit Cards**: Use the Credit Cards page to track your credit card information
5. **View Dashboard**: Monitor urgent bills and credit card summaries from the main dashboard

### Dashboard Features

- **Urgent Bills**: Shows bills due within the next 7 days
- **Credit Card Summary**: Overview of your credit cards and balances
- **All Upcoming Bills**: Complete list of your upcoming bills
- **Clickable Rows**: Click on any bill or credit card to edit it directly

### Bill Management

- Add bills with categories (Utilities, Housing, Insurance, Subscription, Other)
- Set recurring payment flags
- Track due dates and amounts
- Edit bills by clicking on them in the dashboard or bills page

### Credit Card Management

- Track card name/issuer and last 4 digits
- Monitor credit limits and current balances
- Set interest rates and payment due dates
- Edit card information directly from the dashboard or credit cards page

## File Details

### Main Application (`Vance_Financial_Assistant.py`)
- Flask application setup and configuration
- Database models and relationships
- User authentication routes
- Bill and credit card management routes
- Edit functionality for dashboard interaction

### Templates
- **`base.html`**: Common layout with navigation and Bootstrap setup
- **`login.html`**: User authentication form
- **`register.html`**: New user registration form
- **`dashboard.html`**: Main overview with clickable editing
- **`bills.html`**: Bill management interface
- **`credit_cards.html`**: Credit card management interface

### Static Files
- **`style.css`**: Custom flat design styles
- **`script.js`**: JavaScript for enhanced interactions

## Troubleshooting

### Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Bootstrap 5 compatibility requirements
- JavaScript ES6+ features used

## Development Notes

### Flask Routes
- `/` - Dashboard (redirects to login if not authenticated)
- `/login` - User authentication
- `/register` - User registration
- `/dashboard` - Main dashboard view
- `/bills` - Bill management
- `/credit-cards` - Credit card management
- `/edit/bill/<id>` - Edit bill (POST only)
- `/edit/card/<id>` - Edit credit card (POST only)
- `/logout` - User logout

### Database Relationships
- One-to-many: User → Bills
- One-to-many: User → Credit Cards
- Foreign key constraints ensure data integrity

## License

This project is for personal use. Modify and distribute as needed for personal financial management.

## Future Enhancements

Potential improvements could include:
- Data export functionality (CSV, PDF)
- Spending analytics and charts
- Bill payment reminders
- Mobile app development
- Cloud deployment options
- Enhanced security features
- Multi-currency support
- Bulk import/export capabilities
- Search and filtering options
- Data backup and restore


