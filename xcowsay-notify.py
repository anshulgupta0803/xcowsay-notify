#!/usr/bin/python

from collections import deque
import random
import subprocess
import time
import threading

from gi.repository import GObject
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

from gi.repository import GLib

MAXLEN = 50

COMMAND = [
    "xcowsay",
    "--font=FiraCode Nerd Font",
    "--left",
    "--think",
    "--image", "cow_small_left.png",
    "--cow-size=small"
]

AT_FORMAT = "--at=3500,{:d}"

NOTIFICATION_QUEUE = deque()
NOTIFICATION_QUEUE_LOCK = threading.Lock()


def poll(process): return process.poll() != 0


def add_message(notification):
    with NOTIFICATION_QUEUE_LOCK:
        NOTIFICATION_QUEUE.append(notification)


def consume_messages():
    ACTIVE_NOTIFICATION_PROCESS = set()

    while True:
        notification = None
        if NOTIFICATION_QUEUE:
            with NOTIFICATION_QUEUE_LOCK:
                notification = NOTIFICATION_QUEUE.popleft()

        if notification:
            _, message = notification

            location = AT_FORMAT.format(
                200 * (len(ACTIVE_NOTIFICATION_PROCESS) + 1))
            command = COMMAND + [location, message]

            p = subprocess.Popen(command)
            ACTIVE_NOTIFICATION_PROCESS.add(p)

        ACTIVE_NOTIFICATION_PROCESS = set(
            filter(poll, ACTIVE_NOTIFICATION_PROCESS))

        time.sleep(0.1)


class XCowsayNotifications(dbus.service.Object):
    _id = 0

    def __init__(self, bus_name, object_path):
        """Initialize the DBUS service object."""
        dbus.service.Object.__init__(self, bus_name, object_path)
        # self.loop = loop

    @dbus.service.method("org.freedesktop.Notifications",
                         in_signature='susssasa{ss}i',
                         out_signature='u')
    def Notify(self, app_name, notification_id, app_icon,
               summary, body, actions, hints, expire_timeout):

        if not notification_id:
            self._id += 1
            notification_id = self._id

        message = "{:s} {:s}".format(summary, body)
        if len(message) > MAXLEN:
            message = message[:MAXLEN] + "..."

        NOTIFICATION_QUEUE.append([
            notification_id,
            message
        ])

        return notification_id

    @dbus.service.method("org.freedesktop.Notifications", in_signature='', out_signature='as')
    def GetCapabilities(self):
        return ("body")

    @dbus.service.signal('org.freedesktop.Notifications', signature='uu')
    def NotificationClosed(self, id_in, reason_in):
        print("Notification Closed")

    @dbus.service.method("org.freedesktop.Notifications", in_signature='u', out_signature='')
    def CloseNotification(self, id):
        pass

    @dbus.service.method("org.freedesktop.Notifications", in_signature='', out_signature='ssss')
    def GetServerInformation(self):
        return ("", "", "", "")


if __name__ == "__main__":
    DBusGMainLoop(set_as_default=True)
    bus_name = dbus.service.BusName(
        "org.freedesktop.Notifications",
        bus=dbus.SessionBus()
    )

    XCowsayNotifications(bus_name, '/org/freedesktop/Notifications')

    consume_messages_thread = threading.Thread(target=consume_messages)
    consume_messages_thread.start()

    GLib.MainLoop().run()
