import os
import sys

def create_static_structure():
    # Define the base directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define paths
    static_dir = os.path.join(base_dir, 'static')
    css_dir = os.path.join(static_dir, 'css')
    js_dir = os.path.join(static_dir, 'js')
    
    # Create directories if they don't exist
    for directory in [static_dir, css_dir, js_dir]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")
        else:
            print(f"Directory already exists: {directory}")
    
    # Create basic CSS file
    css_file = os.path.join(css_dir, 'style.css')
    if not os.path.exists(css_file):
        with open(css_file, 'w') as f:
            f.write("""/* Vance Finance Custom Styles */

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: #f8f9fa;
}

.card {
    border-radius: 10px;
    overflow: hidden;
}

.card-header {
    font-weight: 500;
}

footer {
    border-top: 1px solid #e3e3e3;
}

/* Custom table styling */
.table-hover tbody tr:hover {
    background-color: rgba(0, 123, 255, 0.05);
}

/* Dashboard stats cards */
.stats-card {
    transition: transform 0.3s;
}

.stats-card:hover {
    transform: translateY(-5px);
}
""")
        print(f"Created file: {css_file}")
    else:
        print(f"File already exists: {css_file}")
    
    # Create basic JavaScript file
    js_file = os.path.join(js_dir, 'script.js')
    if not os.path.exists(js_file):
        with open(js_file, 'w') as f:
            f.write("""// Vance Finance Scripts

// Initialize Bootstrap tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // Set today's date as the default for date inputs
    var today = new Date().toISOString().split('T')[0];
    var dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(function(input) {
        if (!input.value) {
            input.value = today;
        }
    });
});
""")
        print(f"Created file: {js_file}")
    else:
        print(f"File already exists: {js_file}")
    
    print("\nStatic folder structure setup complete!")
    print("\nFolder structure created:")
    print("- static/")
    print("  ├── css/")
    print("  │   └── style.css")
    print("  └── js/")
    print("      └── script.js")

if __name__ == "__main__":
    create_static_structure()