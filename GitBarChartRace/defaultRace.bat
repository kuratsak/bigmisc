rem @echo off
call startvenv.bat

rem feel free to copy/use this for your own data
rem sample is simply "line per value" which we count, we can also use lines with weight/score to make it smarter
listToBars.py sample.csv out/data.csv
race.py out/data.csv
ffmpeg -y -i out/video.mp4 -i "Heaven and Hell - Jeremy Blake.mp3" -c:v copy -c:a copy -strict experimental -map 0:v:0 -map 1:a:0 -shortest out/output_video.mp4
start out/output_video.mp4