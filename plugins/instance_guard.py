"""
StarryPy Instance Guard Plugin

Tracks users locations.  When an instanced world becomes abandoned, 
locks other users out for enough time that the instance resets.

Author: evonzee
"""

import asyncio
import packets
from datetime import datetime, timedelta

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
        config = self.config.get_plugin_config(self.name)
        self.tracked_worlds = self.init_tracking(config)
        self.active_worlds = {}
        self.cooldown_worlds = {}

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

        request = data["parsed"]["warp_action"]

        # If the user is heading out, check if they are leaving somewhere we care about
        destination = ""
        if "world_name" in request:
            destination = request["world_name"]
        
        self.check_departure(connection, destination)
        if destination in self.tracked_worlds:
            return self.arrive(request, connection)

        return True

    def init_tracking(self, config):
        return [
            "operation_gunnerscarrier_0"
        ]

    def check_departure(self, connection, destination):
        uuid = connection.player.uuid
        
        #self.logger.debug("Player {} warped to {}".format(uuid, destination))

        # Look at the active worlds we're tracking
        for world, players in dict(self.active_worlds).items():
            # If the player was on this one
            if uuid in players and destination != world:
                # Remove them
                #self.logger.debug("Player {} has left {}".format(uuid, world))
                players.remove(uuid)
                #self.logger.debug("Remaining players on {}: {}".format(world, players))
                # and if there were no players left
                if not players:
                    # Stop tracking and start cooldown
                    del self.active_worlds[world]
                    self.start_cooldown(world)

    
    def start_cooldown(self, world):
        #self.logger.debug("Starting cooldown on world {}".format(world))
        self.cooldown_worlds[world] = datetime.now() + timedelta(minutes=1)
        #self.logger.debug("Cooldowns are {}".format(self.cooldown_worlds))

    def arrive(self, request, connection):

        world = request["world_name"]
        #self.logger.debug("Arrival on {} by {}".format(world, connection.player.uuid))
        
        # If we are cooling down on this world
        if world in list(self.cooldown_worlds):
            # and if the time is still in the future
            if datetime.now() < self.cooldown_worlds[world]:
                # Sorry, no go for you
                return self.reject(request, connection, self.cooldown_worlds[world])
            else:
                # Else, we've finished cooldown.
                del self.cooldown_worlds[world]
        
        # If we get here, then the user is allowed in.  Track them
        if world not in self.active_worlds:
            self.active_worlds[world] = []

        self.active_worlds[world].append(connection.player.uuid)
        return True

    def reject(self, request, connection, unlock):
        send_message(connection, "Sorry, this world is locked for restart for {} seconds.  Try again in a little while.".format((unlock - datetime.now()).seconds))

        # Send the user back to their ship
        wp = PlayerWarp.build({"warp_action": {"warp_type": 3, "alias_id": 2}})
        full = build_packet(packets.packets['player_warp'], wp)
        #self.logger.debug("Sending user back to home with {}".format(wp))
        yield from connection.client_raw_write(full)
        
        return False