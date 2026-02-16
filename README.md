School Timetable Scheduler

Automated timetable generator for schools with teacher availability, lesson priorities, and weekly hours. Generates conflict-free schedules and provides detailed logs.

Features

Automatically generates class schedules

Considers teacher availability and weekly hours

Prioritizes lessons based on difficulty

Avoids conflicts in classes and teachers

Interactive web interface for viewing, printing, and clearing logs

Supports right-to-left languages (Persian)

Installation
git clone https://github.com/ArminMehri/School_Scheduler.git
cd REPOSITORY
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

Usage

Go to Admin panel

Add Teachers, Classes, Lessons, and Availability

Click Build Schedule to generate

View logs in Schedule Logs page

Print or clear logs as needed

Contributing

Feel free to open issues or submit pull requests.

License

MIT License
