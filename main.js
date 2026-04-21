/**
 * Main JavaScript file for DEnode - Database Schema Optimization Tool
 */

document.addEventListener('DOMContentLoaded', function() {
    // Toggle column details in schema view
    document.querySelectorAll('.toggle-columns-btn').forEach(button => {
        button.addEventListener('click', function() {
            const targetClass = this.getAttribute('data-target');
            const columnRows = document.querySelectorAll(`.${targetClass}-columns`);
            
            columnRows.forEach(row => {
                row.classList.toggle('d-none');
            });
            
            if (this.textContent.trim() === 'Show Columns') {
                this.textContent = 'Hide Columns';
                this.classList.replace('btn-outline-info', 'btn-info');
            } else {
                this.textContent = 'Show Columns';
                this.classList.replace('btn-info', 'btn-outline-info');
            }
        });
    });
    
    // Copy SQL buttons
    document.querySelectorAll('.copy-sql-btn').forEach(button => {
        button.addEventListener('click', function() {
            const sqlContainer = this.closest('.sql-statement').querySelector('pre code');
            const sqlText = sqlContainer.textContent;
            
            navigator.clipboard.writeText(sqlText).then(() => {
                // Show success message
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-check me-1"></i> Copied!';
                this.classList.replace('btn-outline-secondary', 'btn-success');
                
                // Reset after 2 seconds
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.classList.replace('btn-success', 'btn-outline-secondary');
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy SQL: ', err);
            });
        });
    });
    
    // Form validation on extraction and analysis pages
    const extractForm = document.querySelector('form[action*="extract"]');
    if (extractForm) {
        extractForm.addEventListener('submit', function(e) {
            const dbUrlInput = this.querySelector('#db_url');
            const dbNameInput = this.querySelector('#db_name');
            
            if (!dbUrlInput.value.trim()) {
                e.preventDefault();
                dbUrlInput.classList.add('is-invalid');
                return false;
            }
            
            if (!dbNameInput.value.trim()) {
                e.preventDefault();
                dbNameInput.classList.add('is-invalid');
                return false;
            }
            
            // Show loading indicator
            const submitBtn = this.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Extracting...';
        });
    }
    
    // Database type selector helper
    const dbTypeSelect = document.getElementById('db-type');
    const dbUrlInput = document.getElementById('db_url');
    
    if (dbTypeSelect && dbUrlInput) {
        dbTypeSelect.addEventListener('change', function() {
            const dbType = this.value;
            let template = '';
            
            switch(dbType) {
                case 'postgresql':
                    template = 'postgresql://username:password@localhost:5432/database';
                    break;
                case 'mysql':
                    template = 'mysql://username:password@localhost:3306/database';
                    break;
                case 'sqlite':
                    template = 'sqlite:///path/to/database.db';
                    break;
                case 'mssql':
                    template = 'mssql+pyodbc://username:password@server/database?driver=ODBC+Driver+17+for+SQL+Server';
                    break;
            }
            
            if (template && !dbUrlInput.value) {
                dbUrlInput.value = template;
                dbUrlInput.select();
            }
        });
    }
    
    // Handle log file upload preview
    const logFileInput = document.getElementById('log_file');
    if (logFileInput) {
        logFileInput.addEventListener('change', function() {
            const fileNameDisplay = document.getElementById('file-name-display');
            if (fileNameDisplay) {
                if (this.files && this.files.length > 0) {
                    fileNameDisplay.textContent = this.files[0].name;
                    fileNameDisplay.classList.remove('text-muted');
                    fileNameDisplay.classList.add('text-success');
                } else {
                    fileNameDisplay.textContent = 'No file selected';
                    fileNameDisplay.classList.remove('text-success');
                    fileNameDisplay.classList.add('text-muted');
                }
            }
        });
    }
    
    // Enable Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});