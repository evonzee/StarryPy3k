"""
StarryPy Instance Guard Plugin

Tracks users locations.  When an instanced world becomes abandoned, 
locks other users out for enough time that the instance resets.

Author: evonzee
"""

import asyncio
import packets

from base_plugin import StorageCommandPlugin
from data_parser import PlayerWarp, PlayerWarpResult
from pparser import build_packet
from utilities import Command, send_message, link_plugin_if_available, WarpWorldType


class InstanceGuard(StorageCommandPlugin):
    name = "instance_guard"
    depends = ["player_manager", "command_dispatcher"]
    default_config = {"enabled": False}


    def __init__(self):
        super().__init__()

    def activate(self):
        super().activate()

    def on_player_warp(self, data, connection):
        """
        Requests that the player warp somewhere

        :param data: The packet containing the world information.
        :param connection: The connection from which the packet came.
        :return: Boolean: True. Must be true, so that packet get passed on.
        """
        #self.logger.debug("On Warp: {} on {}".format(data, connection))

        player = connection.player
        request = data["parsed"]["warp_action"]
        
        if request["world_id"] == WarpWorldType.MISSION_WORLD or request["world_id"] == WarpWorldType.UNIQUE_WORLD:
            # debug; reject all instance warps for now
            return self.reject(request, connection)

        return True

    def reject(self, request, connection):
        send_message(connection, "Sorry, this world is locked for restart.  Try again in a little while.")

        # Send the user back to their ship
        wp = PlayerWarp.build({"warp_action": {"warp_type": 3, "alias_id": 2}})
        full = build_packet(packets.packets['player_warp'], wp)
        self.logger.debug("Sending user back to home with {}".format(wp))
        yield from connection.client_raw_write(full)
        
        return False