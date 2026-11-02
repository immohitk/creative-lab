from system_monitor import __name__ as package_name


def test_system_monitor_package_is_importable():
    assert package_name == "system_monitor"
