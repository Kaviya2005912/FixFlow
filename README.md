# FixFlow

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=32&pause=1000&color=2563EB&center=true&vCenter=true&width=500&lines=FixFlow;Campus+Maintenance+Made+Simple" alt="FixFlow — Campus Maintenance Made Simple" />
</p>

<p align="center">
  A web-based campus maintenance and complaint tracking system built with Flask.
</p>

## Features

- Submit and track facility complaints, with optional image uploads.
- Role-based dashboards for users, maintenance staff, and administrators.
- Assign complaints to staff and manage their status and priority.
- Add comments, view complaint history, and receive notifications.
- View administrative reports and complaint summaries.

## Tech stack

- Python and Flask
- Flask-SQLAlchemy with SQLite
- Flask-Login and Flask-WTF
- Jinja templates, CSS, and JavaScript

## Run locally

1. Clone the repository and enter the project directory:

   ```bash
   git clone https://github.com/Kaviya2005912/FixFlow.git
   cd FixFlow
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   ```

   Windows PowerShell:

   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

   macOS/Linux:

   ```bash
   source venv/bin/activate
   ```

3. Install dependencies and create your local environment file:

   ```bash
   pip install -r requirements.txt
   ```

   Copy `.env.example` to `.env` and set a unique `SECRET_KEY`.

4. Start the development server:

   ```bash
   python app.py
   ```

   Open [http://localhost:5000](http://localhost:5000). The app creates its SQLite
   database in `instance/` and seeds demo data when the database is empty.

> This project runs Flask with debug mode enabled for local development. Do not
> use the development server or seeded demo accounts in production.

## Repository

[github.com/Kaviya2005912/FixFlow](https://github.com/Kaviya2005912/FixFlow)
