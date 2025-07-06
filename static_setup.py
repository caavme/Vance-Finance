import os

def create_static_structure():
    """Create the static folder structure"""
    
    # Define the structure
    static_dirs = [
        'static',
        'static/css',
        'static/js', 
        'static/images'
    ]
    
    # Create directories
    for directory in static_dirs:
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory: {directory}")
    
    # Create basic CSS file if it doesn't exist
    css_file = 'static/css/style.css'
    if not os.path.exists(css_file):
        with open(css_file, 'w') as f:
            f.write("""/* Vance Finance Custom Styles */
.navbar-brand {
    font-weight: bold;
}

.card {
    border: none;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.btn {
    border-radius: 5px;
}

.alert {
    border-radius: 5px;
}
""")
        print(f"Created file: {css_file}")
    
    # Create basic JavaScript file if it doesn't exist
    js_file = 'static/js/script.js'
    if not os.path.exists(js_file):
        with open(js_file, 'w') as f:
            f.write("""// Vance Finance JavaScript
console.log('Vance Finance loaded');

// Auto-hide alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            alert.style.opacity = '0';
            setTimeout(function() {
                alert.remove();
            }, 300);
        }, 5000);
    });
});
""")
        print(f"Created file: {js_file}")
    
    # Create wiki CSS file
    wiki_css_file = 'static/css/wiki.css'
    if not os.path.exists(wiki_css_file):
        print(f"Wiki CSS file will be created separately: {wiki_css_file}")
    
    print("Static structure setup complete!")

if __name__ == '__main__':
    create_static_structure()