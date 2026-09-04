#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' '=== running system services ==='
systemctl list-units --type=service --state=running --no-legend --no-pager
printf '%s\n' '=== running user services ==='
systemctl --user list-units --type=service --state=running --no-legend --no-pager
printf '%s\n' '=== ROS-related system units (all states) ==='
systemctl list-units --type=service --all --no-legend --no-pager | grep -Ei 'ros|orin_stack' || true
printf '%s\n' '=== ROS-related user units (all states) ==='
systemctl --user list-units --type=service --all --no-legend --no-pager | grep -Ei 'ros|orin_stack' || true
printf '%s\n' '=== ROS-related processes ==='
pgrep -af 'ros2|roscore|rosmaster|rviz|gazebo|nav2|robot_state_publisher|component_container' || true
printf '%s\n' '=== listeners ==='
ss -lntp
