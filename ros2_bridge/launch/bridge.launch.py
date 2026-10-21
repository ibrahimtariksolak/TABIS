import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("battery_ros2_bridge")
    params_file = os.path.join(pkg_dir, "config", "bridge_params.yaml")

    return LaunchDescription([
        Node(
            package="battery_ros2_bridge",
            executable="battery_bridge",
            name="battery_bridge",
            parameters=[params_file],
            output="screen",
        ),
    ])
