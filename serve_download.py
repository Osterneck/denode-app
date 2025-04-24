from flask import Flask, send_file, render_template_string

app = Flask(__name__)

@app.route('/')
def index():
    # Read the HTML file
    with open('download_log.html', 'r') as f:
        html_content = f.read()
    return render_template_string(html_content)

@app.route('/sample_query_log.sql')
def download_sql():
    return send_file('sample_query_log.sql', 
                     mimetype='text/plain',
                     download_name='sample_query_log.sql',
                     as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)