import datetime
import hashlib
import io
import mimetypes
import os
import random
import secrets

from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file, url_for
from gridfs import GridFS
from pymongo import MongoClient, ReturnDocument


load_dotenv()

app = Flask(__name__)

# Vercel Functions have a 4.5 MB payload limit.
# Keep this slightly lower to leave room for multipart/form-data overhead.
MAX_FILE_SIZE_MB = 4
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_MB * 1024 * 1024

mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    raise RuntimeError("MONGO_URI environment variable is missing.")

mongo_client = MongoClient(mongo_uri)
db = mongo_client.secure_files_db
fs = GridFS(db)


def error_page(title, message, status_code=400):
    return (
        render_template(
            "message.html",
            title=title,
            message=message,
            success=False,
            home=True,
        ),
        status_code,
    )


@app.errorhandler(413)
def file_too_large(_error):
    return error_page(
        "File Too Large",
        f"Please upload a file smaller than {MAX_FILE_SIZE_MB} MB. "
        "Vercel serverless uploads cannot handle larger files.",
        413,
    )


@app.route("/", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("upload.html", max_file_size_mb=MAX_FILE_SIZE_MB)

    uploaded_file = request.files.get("file")

    if not uploaded_file or uploaded_file.filename == "":
        return error_page("No File Selected", "Please choose a file before uploading.")

    try:
        file_bytes = uploaded_file.read()

        if not file_bytes:
            return error_page("Empty File", "The uploaded file is empty.")

        otp = str(random.randint(100000, 999999))
        checksum = hashlib.sha256(file_bytes).hexdigest()

        content_type = uploaded_file.mimetype or mimetypes.guess_type(uploaded_file.filename)[0]
        if not content_type:
            content_type = "application/octet-stream"

        gridfs_id = fs.put(
            file_bytes,
            filename=uploaded_file.filename,
            content_type=content_type,
            metadata={"checksum": checksum},
        )

        db.filemeta.insert_one(
            {
                "gridfs_id": gridfs_id,
                "filename": uploaded_file.filename,
                "content_type": content_type,
                "otp": otp,
                "downloaded": False,
                "download_token": None,
                "upload_time": datetime.datetime.now(datetime.UTC),
                "checksum": checksum,
            }
        )

        verify_url = url_for("verify", file_id=str(gridfs_id), _external=True)

        return render_template(
            "uploaded.html",
            verify_url=verify_url,
            otp=otp,
        )

    except Exception as exc:
        print(f"Upload error: {exc}")
        return error_page(
            "Upload Failed",
            "The file could not be uploaded. Check your MongoDB connection and Vercel logs.",
            500,
        )


@app.route("/verify/<file_id>", methods=["GET", "POST"])
def verify(file_id):
    try:
        gridfs_id = ObjectId(file_id)
    except Exception:
        return error_page("Invalid Link", "This download link is malformed.", 400)

    filemeta = db.filemeta.find_one({"gridfs_id": gridfs_id})

    if not filemeta or filemeta.get("downloaded"):
        return error_page(
            "File Not Found",
            "This file does not exist or has already been downloaded.",
            404,
        )

    if request.method == "GET":
        return render_template("verify.html")

    entered_otp = request.form.get("otp", "").strip()

    if entered_otp != filemeta["otp"]:
        return error_page("Access Denied", "The OTP is incorrect.", 403)

    token = secrets.token_urlsafe(32)

    updated_meta = db.filemeta.find_one_and_update(
        {
            "gridfs_id": gridfs_id,
            "downloaded": False,
        },
        {
            "$set": {
                "download_token": token,
                "verified_time": datetime.datetime.now(datetime.UTC),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if not updated_meta:
        return error_page(
            "File Not Found",
            "This file has already been downloaded.",
            404,
        )

    download_url = url_for("download", file_id=file_id, token=token)

    return render_template("verified.html", download_url=download_url)


@app.route("/download/<file_id>")
def download(file_id):
    token = request.args.get("token", "")

    if not token:
        return error_page("Access Denied", "Please verify the OTP before downloading.", 403)

    try:
        gridfs_id = ObjectId(file_id)
    except Exception:
        return error_page("Invalid Link", "This download link is malformed.", 400)

    filemeta = db.filemeta.find_one_and_update(
        {
            "gridfs_id": gridfs_id,
            "download_token": token,
            "downloaded": False,
        },
        {
            "$set": {
                "downloaded": True,
                "downloaded_time": datetime.datetime.now(datetime.UTC),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if not filemeta:
        return error_page(
            "File Not Found",
            "This file does not exist, has already been downloaded, or the OTP was not verified.",
            404,
        )

    try:
        file_obj = fs.get(gridfs_id)
        file_bytes = file_obj.read()

        db.filemeta.delete_one({"gridfs_id": gridfs_id})
        fs.delete(gridfs_id)

        return send_file(
            io.BytesIO(file_bytes),
            mimetype=filemeta.get("content_type", "application/octet-stream"),
            download_name=filemeta["filename"],
            as_attachment=True,
        )

    except Exception as exc:
        print(f"Download error: {exc}")
        return error_page(
            "Download Failed",
            "The file could not be downloaded. It may have already been removed.",
            500,
        )


if __name__ == "__main__":
    app.run(debug=True)
