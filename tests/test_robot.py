from datetime import datetime, time

import pytest
import pytz
from pylitterbot import Robot
from pylitterbot.enums import LitterBoxCommand, LitterBoxStatus
from pylitterbot.exceptions import InvalidCommandException, LitterRobotException

from .common import ROBOT_DATA, ROBOT_ID, ROBOT_NAME, ROBOT_SERIAL, get_robot

pytestmark = pytest.mark.asyncio


def test_robot_setup():
    """Tests that robot setup is successful and parses as expected."""
    robot = Robot(data=ROBOT_DATA)
    assert robot
    assert str(robot) == f"Name: {ROBOT_NAME}, Serial: {ROBOT_SERIAL}, id: {ROBOT_ID}"
    assert robot.auto_offline_disabled
    assert robot.clean_cycle_wait_time_minutes == 7
    assert robot.cycle_capacity == 30
    assert robot.cycle_count == 15
    assert robot.cycles_after_drawer_full == 0
    assert robot.device_type == "udp"
    assert not robot.did_notify_offline
    assert robot.drawer_full_indicator_cycle_count == 0
    assert not robot.is_drawer_full_indicator_triggered
    assert robot.is_onboarded
    assert robot.is_sleeping
    assert not robot.is_waste_drawer_full
    assert robot.last_seen == datetime(
        year=2021, month=2, day=1, minute=30, tzinfo=pytz.UTC
    )
    assert robot.model == "Litter-Robot 3 Connect"
    assert robot.name == ROBOT_NAME
    assert robot.night_light_mode_enabled
    assert not robot.panel_lock_enabled
    assert robot.power_status == "AC"
    assert robot.setup_date == datetime(year=2021, month=1, day=1, tzinfo=pytz.UTC)
    assert robot.sleep_mode_enabled
    assert robot.sleep_mode_start_time.timetz() == time(
        hour=22, minute=30, tzinfo=pytz.UTC
    )
    assert robot.sleep_mode_end_time.timetz() == time(
        hour=6, minute=30, tzinfo=pytz.UTC
    )
    assert robot.status == LitterBoxStatus.READY
    assert robot.status.label == LitterBoxStatus.READY.label
    assert robot.status_code == LitterBoxStatus.READY.value
    assert robot.waste_drawer_level == 50


def test_robot_with_sleepModeTime():
    """Tests that robot with `sleepModeTime` is setup correctly."""
    robot = Robot(data={**ROBOT_DATA, "sleepModeTime": 1612218600})
    assert robot.sleep_mode_start_time.timetz() == time(
        hour=22, minute=30, tzinfo=pytz.UTC
    )


def test_robot_with_unknown_status():
    """Tests that a robot with an unknown `unitStatus` is setup correctly."""
    import random
    import string

    random_status = "_" + "".join(random.sample(string.ascii_letters, 3))

    robot = Robot(data={**ROBOT_DATA, "unitStatus": random_status})
    assert robot.status_code == random_status
    assert robot.status == LitterBoxStatus.UNKNOWN
    assert robot.status.value is None
    assert robot.status.label == "Unknown"


def test_robot_creation_fails():
    """Tests that robot creation fails if missing information."""
    with pytest.raises(LitterRobotException):
        Robot()


@pytest.mark.parametrize(
    "method_call,dispatch_command,args",
    [
        (Robot.reset_settings, LitterBoxCommand.DEFAULT_SETTINGS, {}),
        (Robot.start_cleaning, LitterBoxCommand.CLEAN, {}),
        (Robot.set_night_light, LitterBoxCommand.NIGHT_LIGHT_ON, {True}),
        (Robot.set_night_light, LitterBoxCommand.NIGHT_LIGHT_OFF, {False}),
        (Robot.set_panel_lockout, LitterBoxCommand.LOCK_ON, {True}),
        (Robot.set_panel_lockout, LitterBoxCommand.LOCK_OFF, {False}),
        (Robot.set_power_status, LitterBoxCommand.POWER_ON, {True}),
        (Robot.set_power_status, LitterBoxCommand.POWER_OFF, {False}),
        (Robot.set_wait_time, LitterBoxCommand.WAIT_TIME + "3", {3}),
        (Robot.set_wait_time, LitterBoxCommand.WAIT_TIME + "7", {7}),
        (Robot.set_wait_time, LitterBoxCommand.WAIT_TIME + "F", {15}),
    ],
)
async def test_dispatch_commands(mock_client, method_call, dispatch_command, args):
    """Tests that the dispatch commands are sent as expected."""
    robot = await get_robot(mock_client)

    await getattr(robot, method_call.__name__)(*args)
    assert mock_client.post.call_args.kwargs.get("json") == {
        "command": f"{LitterBoxCommand._PREFIX}{dispatch_command}"
    }


async def test_other_commands(mock_client):
    """Tests that other various robot commands call as expected."""
    robot = await get_robot(mock_client)

    mock_client.get.reset_mock()
    await robot.refresh()
    mock_client.get.assert_called_once()

    NEW_NAME = "New Name"
    await robot.set_name(NEW_NAME)
    assert robot.name == NEW_NAME

    await robot.set_sleep_mode(False)
    assert mock_client.patch.call_args.kwargs.get("json") == {"sleepModeEnable": False}

    await robot.set_sleep_mode(True)
    assert mock_client.patch.call_args.kwargs.get("json") == {
        "sleepModeEnable": True,
        "sleepModeTime": 1614637800,
    }

    assert robot.cycle_count > 0
    await robot.reset_waste_drawer()
    assert robot.cycle_count == 0

    history = await robot.get_activity_history(2)
    assert history
    assert len(history) == 2
    assert str(history[0]) == "2021-03-01T00:01:00+00:00: Ready - 1 cycle"

    insight = await robot.get_insight(2)
    assert insight
    assert len(insight.cycle_history) == 2
    assert (
        str(insight)
        == "Completed 3 cycles averaging 1.5 cycles per day over the last 2 days"
    )


async def test_invalid_commands(mock_client):
    """Tests expected exceptions/responses for invalid commands."""
    robot = await get_robot(mock_client)

    with pytest.raises(InvalidCommandException):
        await robot.set_wait_time(12)

    assert await robot._dispatch_command("W12") is False
    assert mock_client.post.call_args.kwargs.get("json") == {
        "command": f"{LitterBoxCommand._PREFIX}W12"
    }

    with pytest.raises(InvalidCommandException):
        await robot.set_sleep_mode(True, 12)
