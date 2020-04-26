#!/usr/bin/python

from collections import deque
import os
import subprocess
import time
import threading

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

from gi.repository import GLib

MAXCOLS = 50
MAXROWS = 30
NOTIFICATION_HEIGHT = 200
MAX_HEIGHT = 2400

COMMAND = [
    "xcowsay",
    "--font", "FiraCode Nerd Font 10",
    "--left",
    "--image", os.path.join(os.path.dirname(__file__), "cow_small_left.png")
]

AT_FORMAT = "--at=10000,{:d}"
NOTIFICATION_QUEUE = deque()
NOTIFICATION_QUEUE_LOCK = threading.Lock()
BLOCKED_HEIGHT = [False] * MAX_HEIGHT


def find_and_reserve_free_space(height):
    # TODO: Optimize using KMP algorithm
    for i in range(len(BLOCKED_HEIGHT)):
        flag = True
        for j in range(height):
            if i + j >= len(BLOCKED_HEIGHT) or BLOCKED_HEIGHT[i + j]:
                flag = False
                break
        if flag:
            for j in range(height):
                BLOCKED_HEIGHT[i + j] = True
            return i
    return -1


def add_message(notification):
    with NOTIFICATION_QUEUE_LOCK:
        NOTIFICATION_QUEUE.append(notification)


def consume_messages():
    active_notification_processes = list()

    while True:
        notification = None
        if NOTIFICATION_QUEUE:
            y_position = find_and_reserve_free_space(NOTIFICATION_HEIGHT)
            if y_position != -1:  # Free space exists
                with NOTIFICATION_QUEUE_LOCK:
                    notification = NOTIFICATION_QUEUE.popleft()

        if notification:
            _, message = notification

            location = AT_FORMAT.format(200 + y_position)
            command = COMMAND + [location, message]

            process = subprocess.Popen(command)
            active_notification_processes.append([process, y_position])

        active_notification_processes_new = []
        for process, y_position in active_notification_processes:
            if process.poll() == 0:
                for i in range(NOTIFICATION_HEIGHT):
                    BLOCKED_HEIGHT[y_position + i] = False
            else:
                active_notification_processes_new.append([process, y_position])
        active_notification_processes = active_notification_processes_new

        time.sleep(0.1)


class XCowsayNotifications(dbus.service.Object):
    _id = 0

    def __init__(self, bus_name, object_path):
        """Initialize the DBUS service object."""
        dbus.service.Object.__init__(self, bus_name, object_path)

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature='susssasa{ss}i',
                         out_signature='u')
    def Notify(self, app_name, notification_id, app_icon,
               summary, body, actions, hints, expire_timeout):

        if not notification_id:
            self._id += 1
            notification_id = self._id

        message = "{:s}\n\n{:s}".format(summary, body)
        pruned_message = []
        rows = 0
        for line in message.splitlines():
            if len(line) > MAXCOLS:
                pruned_message.append(line[:MAXCOLS] + "...")
            else:
                pruned_message.append(line)
            rows += 1
            if rows > MAXROWS:
                pruned_message.append("")
                pruned_message.append("... More ...")
                break

        NOTIFICATION_QUEUE.append([
            notification_id,
            '\n'.join(pruned_message)
        ])

        return notification_id

    @dbus.service.method("org.freedesktop.Notifications", in_signature='', out_signature='as')
    def GetCapabilities(self):
        return ""

    @dbus.service.signal('org.freedesktop.Notifications', signature='uu')
    def NotificationClosed(self, id_in, reason_in):
        pass

    @dbus.service.method("org.freedesktop.Notifications", in_signature='u', out_signature='')
    def CloseNotification(self, id_):
        pass

    @dbus.service.method("org.freedesktop.Notifications", in_signature='', out_signature='ssss')
    def GetServerInformation(self):
        return ("", "", "", "")


def main():
    DBusGMainLoop(set_as_default=True)
    bus_name = dbus.service.BusName(
        "org.freedesktop.Notifications",
        bus=dbus.SessionBus()
    )

    XCowsayNotifications(bus_name, '/org/freedesktop/Notifications')

    consume_messages_thread = threading.Thread(target=consume_messages)
    consume_messages_thread.start()

    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
