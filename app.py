from flask import Flask, request, send_file, render_template, after_this_request
from pymongo import MongoClient
from gridfs import GridFS
from dotenv import load_dotenv
import os, uuid, datetime, random

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# MongoDB connection
mongo_client = MongoClient(os.getenv('MONGO_URI'))
db = mongo_client.secure_files_db
fs = GridFS(db)

# Upload route
@app.route('/', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files['file']
        file_id = str(uuid.uuid4())
        otp = str(random.randint(100000, 999999))
        # Store PDF in GridFS
        gridfs_id = fs.put(file, filename=file.filename)
        # Store metadata in a separate collection
        db.filemeta.insert_one({
            'gridfs_id': gridfs_id,
            'filename': file.filename,
            'otp': otp,
            'downloaded': False,
            'upload_time': datetime.datetime.utcnow()
        })

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
    filemeta = db.filemeta.find_one({'gridfs_id': file_id})
    if not filemeta:
        return "❌ Invalid file ID."

    if request.method == 'POST':
        entered_otp = request.form['otp']
        if entered_otp == filemeta['otp'] and not filemeta['downloaded']:
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
    filemeta = db.filemeta.find_one({'gridfs_id': file_id})
    if not filemeta or filemeta['downloaded']:
        return "❌ Link expired or file not found."

    # Mark file as downloaded
    db.filemeta.update_one(
        {'gridfs_id': file_id},
        {'$set': {
            'downloaded': True,
            'download_ip': request.remote_addr,
            'download_time': datetime.datetime.utcnow()
        }}
    )

    # Stream file from GridFS
    gridout = fs.get(filemeta['gridfs_id'])

    @after_this_request
    def remove_file(response):
        fs.delete(filemeta['gridfs_id'])
        db.filemeta.delete_one({'gridfs_id': file_id})
        return response

    return send_file(gridout, as_attachment=True, download_name=filemeta['filename'])

# Ensure upload folder exists
if __name__ == '__main__':
    app.run(debug=True)
