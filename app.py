from flask import Flask, request, send_file, render_template, after_this_request
from flask_sqlalchemy import SQLAlchemy
import os, uuid, datetime, random

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database model
class File(db.Model):
    id = db.Column(db.String, primary_key=True)
    filename = db.Column(db.String)
    downloaded = db.Column(db.Boolean, default=False)
    access_ip = db.Column(db.String)
    access_time = db.Column(db.DateTime)
    otp = db.Column(db.String)

# Initialize DB
with app.app_context():
    db.create_all()

# Upload route
@app.route('/', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files['file']
        file_id = str(uuid.uuid4())
        otp = str(random.randint(100000, 999999))
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id + '_' + file.filename)
        file.save(save_path)

        new_file = File(id=file_id, filename=file.filename, otp=otp)
        db.session.add(new_file)
        db.session.commit()

        return f"""
        <!DOCTYPE html>
        <html lang='en'>
        <head>
            <meta charset='UTF-8'>
            <meta name='viewport' content='width=device-width, initial-scale=1'>
            <link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css' rel='stylesheet'>
        </head>
        <body style='background: linear-gradient(135deg, #2ecc71, #20c997); min-height:100vh;'>
            <div class='container d-flex align-items-center justify-content-center' style='min-height:100vh;'>
                <div class='card p-4' style='border-radius:18px; box-shadow:0 8px 25px rgba(0,0,0,0.13);'>
                    <h3 class='text-success mb-3'>✅ File uploaded successfully</h3>
                    <div class='mb-2'><span class='fw-bold'>🔗 Share this link:</span> <a href='/verify/{file_id}' class='link-success'>/verify/{file_id}</a></div>
                    <div class='mb-2'><span class='fw-bold'>🔐 OTP:</span> <span class='badge bg-success fs-5'>{otp}</span></div>
                    <div class='text-warning mb-2'>⚠️ File will auto-delete after download</div>
                    <a href='/' class='btn btn-outline-success mt-2'>Upload Another File</a>
                </div>
            </div>
            <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js'></script>
        </body>
        </html>
        """
    return render_template('upload.html')

# OTP verification
@app.route('/verify/<file_id>', methods=['GET', 'POST'])
def verify(file_id):
    file = File.query.get(file_id)
    if not file:
        return "❌ Invalid file ID."

    if request.method == 'POST':
        entered_otp = request.form['otp']
        if entered_otp == file.otp and not file.downloaded:
                        return f"""
                        <!DOCTYPE html>
                        <html lang='en'>
                        <head>
                            <meta charset='UTF-8'>
                            <meta name='viewport' content='width=device-width, initial-scale=1'>
                            <link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css' rel='stylesheet'>
                        </head>
                        <body style='background: linear-gradient(135deg, #2ecc71, #20c997); min-height:100vh;'>
                            <div class='container d-flex align-items-center justify-content-center' style='min-height:100vh;'>
                                <div class='card p-4' style='border-radius:18px; box-shadow:0 8px 25px rgba(0,0,0,0.13);'>
                                    <h4 class='mb-3 text-success'>✅ OTP Verified</h4>
                                    <a href='/download/{file_id}' class='btn btn-success w-100'>Download File</a>
                                    <div class='mt-2 text-warning'>⚠️ File will auto-delete after download</div>
                                </div>
                            </div>
                            <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js'></script>
                        </body>
                        </html>
                        """
        return "❌ Invalid OTP or file already downloaded."

        return '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body style="background: linear-gradient(135deg, #2ecc71, #20c997); min-height:100vh;">
            <div class="container d-flex align-items-center justify-content-center" style="min-height:100vh;">
                <div class="card p-4" style="border-radius:18px; box-shadow:0 8px 25px rgba(0,0,0,0.13);">
                    <h3 class="mb-3 text-success">🔐 Enter OTP to download your file</h3>
                    <form method="POST">
                        <div class="mb-3">
                            <input type="text" name="otp" class="form-control" placeholder="Enter OTP" required>
                        </div>
                        <button type="submit" class="btn btn-success w-100">Verify</button>
                    </form>
                </div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
        </body>
        </html>
        '''

# Download route
@app.route('/download/<file_id>')
def download(file_id):
    file = File.query.get(file_id)
    if not file or file.downloaded:
        return "❌ Link expired or file not found."

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.id + '_' + file.filename)

    if not os.path.exists(file_path):
        return "❌ File no longer available."

    # Mark file as downloaded
    file.downloaded = True
    file.access_ip = request.remote_addr
    file.access_time = datetime.datetime.utcnow()
    db.session.commit()

    @after_this_request
    def remove_file(response):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file: {e}")
        return response

    return send_file(file_path, as_attachment=True)

# Ensure upload folder exists
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
