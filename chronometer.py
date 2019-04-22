#!/usr/bin/python3
import datetime
import time
import os
import sys
import string
import ephem
import threading
import subprocess
import re
import xml.etree.ElementTree as ET
from myColors import colors
from pytz import timezone

STATIC = 0
RELATIVE = 1
time_zone_list = []

config_file = os.path.dirname(os.path.realpath(__file__))
config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.xml")
tree = ET.parse(config_file)
root = tree.getroot()
for child in root:
    if child.tag == "location":
        city = ephem.city(child.text)

    if child.tag == "timezones":
        for tz in child:
            time_zone_list.append([tz.text, timezone(tz.get("code"))])


def get_relative_date(ordinal, weekday, month, year):
    firstday = (datetime.datetime(year, month, 1).weekday() + 1) % 7
    first_sunday = (7 - firstday) % 7 + 1
    return datetime.datetime(year, month, first_sunday + weekday + 7 * (ordinal - 1))


def solartime(observer, sun=ephem.Sun()):
    sun.compute(observer)
    # sidereal time == ra (right ascension) is the highest point (noon)
    hour_angle = observer.sidereal_time() - sun.ra
    return ephem.hours(hour_angle + ephem.hours('12:00')).norm  # norm for 24h

themes = [colors.bg.black, colors.fg.white, colors.fg.lightblue, colors.bg.black, colors.bg.lightblue]

SECOND = 0
MINUTE = 1
HOUR = 2
DAY = 3
MONTH = 4
YEAR = 5
CENTURY = 6

LABEL = 0
VALUE = 1
PRECISION = 2

NTPOFF = 0
NTPDLY = 0
NTPSTR = "-"
NTPID = "---"

#             Label, value, precision
time_table = [["Second",    0,    6],
             ["Minute",    0,    8],
             ["Hour",    0,    10],
             ["Day",        0,    10],
             ["Month",    0,    10],
             ["Year",    0,    10],
             ["Century",    0,    10]]


def reset_cursor():
    print("\033[0;0H", end="")


def color(bg, fg):
    return "\x1b[48;5;" + str(bg) + ";38;5;" + str(fg) + "m"


def draw_progress_bar(width, min, max, value):
    level = int(width * (value - min) / (max - min) + .999999999999)
    return (chr(0x2550) * level + colors.fg.darkgray + (chr(0x2500) * (width - level)))

os.system("clear")
os.system("setterm -cursor off")


def main():
    while True:
        ntp_id_str = str(NTPID)
        try:

            time.sleep(0.0167)

            rows = os.get_terminal_size().lines
            columns = os.get_terminal_size().columns

            now = datetime.datetime.now()
            utcnow = datetime.datetime.utcnow()
            screen = ""
            output = ""
            reset_cursor()

            u_second = now.microsecond / 1000000

            highlight = [themes[3], themes[4]]
            print(themes[0], end="")

            v_bar = themes[2] + chr(0x2551) + themes[1]
            v_bar1 = themes[2] + chr(0x2502) + themes[1]
            h_bar = themes[2] + chr(0x2550) + themes[1]
            v_bar_up = themes[2] + chr(0x00af) + themes[1]
            v_bar_down = themes[2] + "_" + themes[1]

            binary0 = chr(0x25cf)
            binary1 = chr(0x25cb)

            hour_binary0 = "{:>04b}".format(int(now.hour / 10))
            hour_binary1 = "{:>04b}".format(int(now.hour % 10))
            minute_binary0 = "{:>04b}".format(int(now.minute / 10))
            minute_binary1 = "{:>04b}".format(int(now.minute % 10))
            second_binary0 = "{:>04b}".format(int(now.second / 10))
            second_binary1 = "{:>04b}".format(int(now.second % 10))

            b_clock_mat = [hour_binary0, hour_binary1, minute_binary0, minute_binary1, second_binary0, second_binary1]
            b_clock_matT = [*zip(*b_clock_mat)]
            b_clockdisp = ['', '', '', '']

            for i, row in enumerate(b_clock_matT):
                b_clockdisp[i] = ''.join(row).replace("0", " " + binary0).replace("1", " " + binary1)

            if (now.month == 12):
                days_this_month = 31
            else:
                days_this_month = (datetime.datetime(now.year, now.month + 1, 1) -
                                 datetime.datetime(now.year, now.month, 1)).days

            day_of_year = (now - datetime.datetime(now.year, 1, 1)).days
            days_this_year = (datetime.datetime(now.year + 1, 1, 1) - datetime.datetime(now.year, 1, 1)).days

            time_table[SECOND][VALUE] = now.second + u_second
            time_table[MINUTE][VALUE] = now.minute + time_table[SECOND][VALUE] / 60
            time_table[HOUR][VALUE] = now.hour + time_table[MINUTE][VALUE] / 60
            time_table[DAY][VALUE] = now.day + time_table[HOUR][VALUE] / 24
            time_table[MONTH][VALUE] = now.month + (time_table[DAY][VALUE] - 1) / days_this_month
            time_table[YEAR][VALUE] = now.year + (day_of_year + time_table[DAY][VALUE] - int(
                                                 time_table[DAY][VALUE])) / days_this_year
            time_table[CENTURY][VALUE] = (time_table[YEAR][VALUE] - 1) / 100 + 1

            screen += themes[4]
            screen += ("{: ^" + str(columns - 1) + "}\n").format(now.strftime("%I:%M:%S %p - %A %B %d, %Y"))

            screen += v_bar_down * (columns - 1) + themes[0] + themes[1] + "\n"

            for i in range(7):
                percent_value = int(100 * (time_table[i][VALUE] - int(time_table[i][VALUE])))
                screen += (" {0:>7} " + v_bar + " {1:>15." + str(time_table[i][PRECISION]) + "f}" + v_bar1 + "{2:}" + v_bar1 + "{3:02}% \n").format(
                    time_table[i][LABEL], time_table[i][VALUE], draw_progress_bar(
                        columns - 32, 0, 100, percent_value), percent_value)

            screen += v_bar_up * columns + "\n"

            DST = [["DST Begins", get_relative_date(2, 0, 3, now.year).replace(hour=2)],
                   ["DST Ends", get_relative_date(1, 0, 11, now.year).replace(hour=2)]]

            if ((now - (DST[0][1])).total_seconds() > 0) & (((DST[1][1]) - now).total_seconds() > 0):
                is_daylight_savings = True
                next_date = DST[1][1].replace(hour=2)
            else:
                is_daylight_savings = False
                if ((now - DST[0][1]).total_seconds() < 0):
                    next_date = get_relative_date(2, 0, 3, now.year).replace(hour=2)
                else:
                    next_date = get_relative_date(2, 0, 3, now.year + 1).replace(hour=2)

            dst_str = " " + DST[is_daylight_savings][0] + " " + next_date.strftime("%a %b %d") + \
                     " (" + str(next_date - now).split(".")[0] + ")"

            unix_int = int(datetime.datetime.utcnow().timestamp())
            unix_exact = unix_int + u_second
            unix_str = ("UNIX: {0}").format(unix_int)

            day_percent_complete = time_table[DAY][VALUE] - int(time_table[DAY][VALUE])
            day_percent_completeUTC = (utcnow.hour * 3600 + utcnow.minute * 60 + utcnow.second + utcnow.microsecond / 1000000) / 86400
            metric_hour = int(day_percent_complete * 10)
            metric_minute = int(day_percent_complete * 1000) % 100
            metric_second = (day_percent_complete * 100000) % 100
            metricu_second = int(day_percent_complete * 10000000000000) % 100
            metric_str = (" Metric: {0:02.0f}:{1:02.0f}:{2:02}").format(metric_hour, metric_minute, int(metric_second))

            solar_str_tmp = str(solartime(city)).split(".")[0]
            solar_str = "  Solar: {0:>08}".format(solar_str_tmp)

            lst_str_tmp = str(city.sidereal_time()).split(".")[0]
            lst_str = "    LST: {0:>08}".format(lst_str_tmp)

            hex_str_tmp = "{:>04}: ".format(hex(int(65536 * day_percent_complete)).split("x")[1]).upper()
            hex_str = " Hex: " + hex_str_tmp[0] + "_" + hex_str_tmp[1:3] + "_" + hex_str_tmp[3]

            net_value = 1296000 * day_percent_completeUTC
            net_hour = int(net_value / 3600)
            net_minute = int((net_value % 3600) / 60)
            net_second = int(net_value % 60)

            net_str = " NET: {0:>02}°{1:>02}\'{2:>02}\"".format(net_hour, net_minute, net_second)
            screen += dst_str + " " * (columns - len(dst_str + b_clockdisp[0]) - 4) + b_clockdisp[0] + "    \n"
            screen += metric_str + " " + v_bar + " " + unix_str + " " * (columns - len(metric_str + unix_str + b_clockdisp[1]) - 7) + b_clockdisp[1] + "    \n"
            screen += solar_str + " " + v_bar + " " + net_str + " " * (columns - len(solar_str + net_str + b_clockdisp[2]) - 7) + b_clockdisp[2] + "    \n"
            screen += lst_str + " " + v_bar + " " + hex_str + " " * (columns - (len(lst_str + hex_str + b_clockdisp[3]) + 7)) + b_clockdisp[3] + "    \n"
            screen += v_bar_down * columns + ""

            for i in range(0, len(time_zone_list), 2):
                time0 = datetime.datetime.now(time_zone_list[i][1])
                time1 = datetime.datetime.now(time_zone_list[i + 1][1])
                flash0 = False
                flash1 = False

                if (time0.weekday() < 5):
                    if (time0.hour > 8 and time0.hour < 17):
                        flash0 = True
                    elif (time0.hour == 8 or time0.hour == 17):
                        flash0 = (int(u_second * 10) < 5)

                if (time1.weekday() < 5):
                    if (time1.hour > 8 and time1.hour < 17):
                        flash1 = True
                    elif (time1.hour == 8 or time1.hour == 17):
                        flash1 = (int(u_second * 10) < 5)

                time_str0 = time0.strftime("%I:%M %p %b %d")
                time_str1 = time1.strftime("%I:%M %p %b %d")
                screen += highlight[flash0] + (" {0:>9}: {1:15}  ").format(time_zone_list[i][0], time_str0) + highlight[0] + v_bar
                screen += highlight[flash1] + (" {0:>9}: {1:15}  ").format(time_zone_list[i + 1][0], time_str1) + highlight[0]
                # Each Timezone column is 29 chars, and the bar is 1 = 59
                spacer = " " * (columns - 59)
                screen += spacer + "\n"

            half_cols = int(((columns - 1) / 2) // 1)
            NTPID_max_width = half_cols - 7
            NTPID_temp = ntp_id_str
            # Calculate NTP server scrolling if string is too large
            if(len(ntp_id_str) > NTPID_max_width):

                stages = 16 + len(ntp_id_str) - NTPID_max_width
                current_stage = int(unix_exact / .25) % stages

                if(current_stage < 8):
                    NTPID_temp = ntp_id_str[0:NTPID_max_width]
                elif(current_stage >= (stages - 8)):
                    NTPID_temp = ntp_id_str[(len(NTPID) - NTPID_max_width):]
                else:
                    NTPID_temp = ntp_id_str[(current_stage - 8):(current_stage - 8 + NTPID_max_width)]

            sign = "-" if (NTPOFF < 0) else "+"

            NTPStrL = "NTP:" + NTPID_temp
            NTPStrR = ("STR:{0:1}/DLY:{1:6.3f}/OFF:{2:" + sign + "6.3f}").format(NTPSTR, NTPDLY, round(NTPOFF, 4))
            screen += themes[4] + NTPStrL + ((columns - len(NTPStrL + NTPStrR) - 1) * " ") + NTPStrR

            # Switch to the header color theme
            screen += themes[3]

            # Append blank lines to fill out the bottom of the screen
            for i in range(22, rows):
                screen += " " * columns

            print(screen, end="")

        except KeyboardInterrupt:
            return


def ntp_daemon():

    global NTPDLY
    global NTPOFF
    global NTPSTR
    global NTPID

    pattern = re.compile(
        "\*([\w+\-\.(): ]+)\s+([\w\.]+)\s+(\d+)\s+(\w+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d\.]+)\s+([-\d\.]+)\s+([\d\.]+)")

    while(True):
        try:
            ntpq = subprocess.run(['ntpq', '-pw'], stdout=subprocess.PIPE)
            ntpq = ntpq.stdout.decode('utf-8')
            current_server = re.search(r"\*.+", ntpq)
            current_server = pattern.search(ntpq)

            if(current_server):
                ntp_stats = re.split("\s+", current_server.group())

                NTPOFF = float(current_server.group(9))
                NTPDLY = float(current_server.group(8))
                NTPSTR = current_server.group(3)
                NTPID = current_server.group(1)
        except Exception as e:
            NTPID = e

        time.sleep(15)
if __name__ == "__main__":
    t = threading.Thread(target=ntp_daemon)
    t.set_daemon(True)
    t.start()
    main()
    os.system("clear")
    os.system("setterm -cursor on")
    print(colors.reset.all, end="")
