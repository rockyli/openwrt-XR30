#!/bin/sh

LM63_HWMON=$(grep -Fx -l lm63 /sys/class/hwmon/hwmon*/name) || exit 0
LM63_HWMON=${LM63_HWMON%/name}

PSU_TEMP=$(cat "$LM63_HWMON/temp1_input")
FAN_CTRL="$LM63_HWMON/pwm1"

PSU_THRESH=51000

if [ "$PSU_TEMP" -ge "$PSU_THRESH" ];then
	echo "250" > $FAN_CTRL
else
	echo "156" > $FAN_CTRL
fi
