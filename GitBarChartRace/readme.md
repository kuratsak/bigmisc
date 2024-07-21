For tutorial or advanced usage, see https://github.com/kuratsak/bar_chart_race

Instructions here:
copy startvenv.bat.example to startvenv.bat
copy repoRace.bat.example to repoRace.bat

edit all lines that might be different for your machine, such as:
ffmpeg
python
venv creation
repos you want to run the race on

Bring a song and place it in the folder - update repoRace.bat or defaultRace.bat to use it
You can also comment out the song adding command if you want just a silent video

Edit utils.py and race.py for the parameters you want:

How long the movie is - period_length [in milliseconds] * maximumLines.
Currently 0.5 seconds * 600 = 300 seconds, 5 minutes)

Formatting of text/titles to fit number of top bars you want in your chart (n_bars)

Edit makeBarCharts as you want - to fix/cleanup author data

After that - run defaultRace.bat to check it works