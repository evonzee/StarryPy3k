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
from data_parser import PlayerWarp
from pparser import build_packet
from utilities import Command, send_message, WarpWorldType


class InstanceGuard(StorageCommandPlugin):
    name = "instance_guard"
    depends = ["player_manager", "command_dispatcher"]
    default_config = {
        "timeout": 60,
    }


    def __init__(self):
        super().__init__()
        self.active_worlds = {}
        self.cooldown_worlds = {}

    def activate(self):
        super().activate()
        config = self.config.get_plugin_config(self.name)
        self.default_timeout = config["timeout"]
        if "tracked_worlds" not in self.storage:
            self.storage["tracked_worlds"] = {}

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
        if destination in self.storage["tracked_worlds"]:
            return self.arrive(request, connection)

        return True

    def check_departure(self, connection, destination):
        uuid = connection.player.uuid
        
        #self.logger.debug("Player {} warped to {}".format(uuid, destination))

        # Look at the active worlds we're tracking
        for world, players in dict(self.active_worlds).items():
            # If the player was on this one and isn't beaming somewhere else on the same instance
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
        self.cooldown_worlds[world] = datetime.now() + timedelta(seconds=self.storage["tracked_worlds"][world])
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


    @Command("guards",
             perm="guard.list_guards",
             doc="Lists plants with guards enabled.",
             syntax="")
    def _list_guards(self, data, connection):
        send_message(connection, "Worlds with guards: {}".format(self.storage["tracked_worlds"]))
        send_message(connection, "Worlds with cooldown active: {}".format(self.cooldown_worlds.keys()))

    @Command("guard",
             perm="guard.add_guard",
             doc="Set the mission you're on as a guarded world.  Once empty, players won't be allowed to return until timeout.",
             syntax="[\"](timeout)[\"]")
    def _set_guard(self, data, connection):
        location = str(connection.player.location)
        
        if not location.startswith("InstanceWorld"):
            send_message(connection, "This location cannot be guarded.  Please try again on an instance world.")
            return
        
        #self.logger.debug("Adding guard to {}".format(location))

        map = location.split(":")[1]
        timeout = self.default_timeout
        if len(data) != 0:
            timeout = data[0]
        self.storage["tracked_worlds"][map] = timeout
        send_message(connection, "Added guard on {} of {} seconds.  Please leave the map to enable tracking.".format(map, timeout))

    @Command("unguard",
             perm="guard.del_guard",
             doc="Removes guarding from the current mission.",
             syntax="")
    def _del_guard(self, data, connection):
        location = str(connection.player.location)

        if not location.startswith("InstanceWorld"):
            send_message(connection, "This location cannot be guarded.  Please try again on an instance world.")
            return
        
        #self.logger.debug("Removing guard from {}".format(location))

        map = location.split(":")[1]
        if map in self.storage["tracked_worlds"]:
            del self.storage["tracked_worlds"][map]
            send_message(connection, "Removed guard on {}".format(map))
        else:
            send_message(connection, "This world is already unguarded.")    
        self._list_guards(data, connection)
