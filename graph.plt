#!/usr/bin/gnuplot --persist
set title 'Объем потребляемой памяти, Кб'
set style data linespoints

print "script name : ", ARG0
print "input file : ", ARG1

plot ARG1
pause -1
