
# Secure One-Time Download Files

## Overview
A Flask-based secure file sharing system with OTP verification, one-time download enforcement, and auto-delete logic. Files are stored in MongoDB Atlas using GridFS, making it fully compatible with Vercel and other serverless platforms.

## Features
- Upload PDF files securely
- Each file is protected by a randomly generated OTP
- One-time download: file is deleted from the database after download
- Beautiful Bootstrap UI for all states (success, error, invalid OTP, file not found)
- No local file storage required (uses MongoDB GridFS)
- Works with MongoDB Atlas free tier
- Ready for deployment on Vercel

## How It Works
1. User uploads a PDF file
2. System generates a unique OTP and stores the file in GridFS
3. User receives a link and OTP
4. User enters OTP to verify and download the file
5. File is deleted from GridFS after download

## Setup & Local Testing
1. Clone the repo
2. Create a `.env` file with your MongoDB Atlas connection string:
	```
	MONGO_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
	```
3. Install dependencies:
	```
	py -m pip install -r requirements.txt
	```
4. Run the app:
	```
	py app.py
	```
5. (Optional) Use ngrok to expose your local server:
	```
	ngrok http 5000
	```

## Deployment
- Push to GitHub and connect to Vercel
- Set your `MONGO_URI` in Vercel environment variables
- Vercel will auto-deploy and serve your app

## Technologies Used
- Flask
- MongoDB Atlas (GridFS)
- Bootstrap 5
- Vercel

## Screenshots
![Upload Success](screenshots/upload-success.png)
![OTP Error](screenshots/otp-error.png)
![File Not Found](screenshots/file-not-found.png)

## License
MIT
