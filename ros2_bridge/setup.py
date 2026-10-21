from setuptools import setup

package_name = "battery_ros2_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name.replace("-", "_").replace("battery_ros2_bridge", "ros2_bridge")],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/battery_ros2_bridge"]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/bridge.launch.py"]),
        ("share/" + package_name + "/config", ["config/bridge_params.yaml"]),
    ],
    install_requires=["setuptools", "websockets"],
    zip_safe=True,
    entry_points={
        "console_scripts": [
            "battery_bridge = ros2_bridge.battery_bridge_node:main",
        ],
    },
)
