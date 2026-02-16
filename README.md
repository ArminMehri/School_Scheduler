School Timetable Scheduler

Automated timetable generator for schools with teacher availability, lesson priorities, and weekly hours. Generates conflict-free schedules and provides detailed logs.
--------------------------------------------------------------------------------------
Features:

Automatically generates class schedules

Considers teacher availability and weekly hours

Prioritizes lessons based on difficulty

Avoids conflicts in classes and teachers

Interactive web interface for viewing, printing, and clearing logs

Supports right-to-left languages (Persian)

Export Timetable Schedule To Excel 

You can Check the logs (The Errors in the logs page)
--------------------------------------------------------------------------------------
Installation:

git clone https://github.com/ArminMehri/School_Scheduler.git

cd REPOSITORY

python -m venv venv

source venv/bin/activate  # Linux/macOS

venv\Scripts\activate     # Windows

pip install -r requirements.txt

python manage.py migrate

python manage.py runserver
--------------------------------------------------------------------------------------
Usage:

Go to Admin panel

Add Teachers(All of requireds is Here), Classes, Lessons, Grades,Day periods,School days

Click Build Schedule to generate

View Timetable in main page 

View logs in Schedule Logs page

Print or clear logs as needed
--------------------------------------------------------------------------------------

License

MIT License
