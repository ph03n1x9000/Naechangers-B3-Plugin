# Namechanger Detector Plugin for BigBrotherBot(B3) (www.bigbrotherbot.net)
# Copyright (C) 2011 at ZeroAlpha - www.ZeroAlpha.us
# Coded/Modified by NRP|pyr0 for ZeroAlpha
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
# CHANGELOG
#
# 12-18-2011 - 0.1 - NRP|pyr0
#   * Initial programming started. Using Freelanders code as a base.
# 12-19-2011 - 0.2 - NRP|pyr0
#   * Using a simpler design versus original plan. Code from scratch.
# 12-20-2011 - 0.3 - NRP|pyr0
#   * Modified a few lines to make it function
# 12-22-2011 - 0.4 - NRP|pyr0
#   * Added in Ignore Feature
# 12-23-2011 - 0.5 - NRP|pyr0
#   * Fixed IgnoreFeature, added reset on death option.
# 12-23-2011 - 0.6 - NRP|pyr0
#   * Added Notify feature, it didnt work.
# 12-24-2011 - 0.7 - NRP|pyr0
#   * Fixed Notify feature, changed kick/ban method a bit. Kick/ban was busted.
# 12-25-2011 - 0.8 - NRP|pyr0
#   * Fixed Kick/Ban again and fixed logging.
# 12-26-2011 - 0.9 - NRP|pyr0
#   * Modified some lines, fixed some bugs
# 12-31-2011 - 0.91 - NRP|pyr0
#	* Added a few extra bits to try and get in line with B3 standards
#	  Should work, but needs testing. Still yet to test Perm Ban though.
# 02-08-2012 - 0.99 - NRP|pyr0
#   * All SHOULD be functional. Unable to test tonight.
# 02-19-2012 - 1.00 - NRP|pyr0
#   * I've run this live on {zA} NY Dom for a week and some change now with no issue.
# 09-08-2015 - 1.0.1 - ph03n1x
#   * rewrote entire code for better detection. Only works with b3 1.10 and later
#   * Credit given to NPR|pyr0 because I used his idea
# 09-09-2015 - 1.0.2 - ph03n1x
#   * Added backward compatibility to v1.9.2


__author__ = 'NRP|pyr0, ph03n1x'
__version__ = '1.0.1'

import b3
import b3.events
import b3.plugin
from b3 import functions


class NamechangersPlugin(b3.plugin.Plugin):
    _bc = False  # Informs event functioning that we are to use old dispatch system. So that we don't have double events
    _storedClients = {}
    _default_messages = {'kick': 'Player $name Kicked for too many namechanges (GUID: $guid)',
                         'tempban': 'Player $name Temp Banned for too many namechanges (GUID: $guid)',
                         'permban': 'Player $name PermBanned for too many namechanges (GUID: $guid)'
                         }

    def onStartup(self):
        try:
            # Register events using new dispatch system
            self.registerEvent('EVT_CLIENT_NAME_CHANGE', self.nameChangeOccurred)
            self.registerEvent('EVT_CLIENT_KICK', self.onPenalty)
            self.registerEvent('EVT_CLIENT_BAN_TEMP', self.onPenalty)
            self.registerEvent('EVT_CLIENT_BAN', self.onPenalty)
        except:
            # Keep backwards compatibility
            self._bc = True
            self.registerEvent(b3.events.EVT_CLIENT_NAME_CHANGE)
            self.registerEvent(b3.events.EVT_CLIENT_KICK)
            self.registerEvent(b3.events.EVT_CLIENT_BAN_TEMP)
            self.registerEvent(b3.events.EVT_CLIENT_BAN)

    def onLoadConfig(self):
        try:
            self.logLocation = self.config.get('settings', 'log_location')
            if self.logLocation:
                self.logLocation = b3.getAbsolutePath(self.logLocation)
            elif not self.logLocation:
                self.verbose('Log disabled in config')
        except:
            self.logLocation = None

        try:
            self.maxnames = self.config.getint('settings', 'maxnames')
        except:
            self.maxnames = 5
            self.debug('No Config Value Set. Using Default Max Names of 5.')

        try:
            self.action = self.config.get('settings', 'action')
        except:
            self.action = 'kick'
            self.debug('No Config Value Set. Using Kick As Default Action')

        if self.action == 'tempban':
            try:
                self.duration = self.config.get('settings', 'tempban_duration')
                self.duration = functions.time2minutes(self.duration)
                self.debug('Tempban duration set to %s' % self.duration)
            except:
                self.duration = '2h'
                self.debug('No Config Value set for tempban_duration, using 2 hours')

        try:
            self.ignoreLevel = self.config.getint('settings', 'ignore_level')
        except:
            self.ignoreLevel = 100
            self.debug('No Config Value Set. Only superadmin is ignored')

        try:
            self.notify = self.config.getint('settings', 'notify')
        except:
            self.notify = None
            self.debug('Notifications disabled in config.')

        if self.config.has_section('messages'):
            for (penalty, message) in self.config.items('messages'):
                self._default_messages[penalty] = message

    ########################### BACKWARD COMPATIBILITY SECTION #####################
    def onEvent(self, event):
        if self._bc:
            if event.type == b3.events.EVT_CLIENT_NAME_CHANGE:
                self.nameChangeOccurred(event)
            elif event.type == b3.events.EVT_CLIENT_KICK or \
                event.type == b3.events.EVT_CLIENT_BAN_TEMP or \
                event.type == b3.events.EVT_CLIENT_BAN:
                self.onPenalty(event)


    ########################### EVENT HANDLING #####################################
    def nameChangeOccurred(self, event):
        """\
        Handle EVT_CLIENT_NAME_CHANGE
        """
        #Client has changed name. Store his info in case he changes again
        client = event.client

        # Check if client level is to be ignored
        if client.maxLevel >= self.ignoreLevel:
            self.verbose('Client is at ignore level. Cancelling')
            return

        # Check if client has changed name before. If not, initialize client name storage.
        if client.guid not in self._storedClients:
            self._storedClients[client.guid] = list()

        # Save client info
        self._storedClients[client.guid].append(client.name)

        # Write to log if needed
        n = 'Client with GUID: %s has changed name. Used names: %s' % (client.guid, self._storedClients[client.guid])
        self.callLog(n)

        # Check if client change names has reached tolerated limit
        if len(self._storedClients[client.guid]) >= self.maxnames:
            self.penalize(client)
        elif len(self._storedClients[client.guid]) < self.maxnames:
            self.notifyAdmins(client)

    def onPenalty(self, event):
        """\
        Handle EVT_CLIENT_BAN_TEMP, EVT_CLIENT_BAN and EVT_CLIENT_KICK
        We do it this way so that we know if client is manually penalized by admin
        """
        c = event.client
        # Check if client in this event is being watched. If so remove from stored clients
        if c.guid in self._storedClients:
            self._storedClients.pop(c.guid)

    ####################################### FUNCTIONING ##################################
    def penalize(self, client):
        self.debug('Too many name changes performed by GUID: %s. Penalizing' % client.guid)
        if self.action == 'kick':
            client.kick(reason='Too many name changes', keyword='NameChanger', data='%s Namechanges' % len(self._storedClients[client.guid]))
        elif self.action == 'tempban':
            client.tempban(reason='Too many name changes', keyword='NameChanger', duration=self.duration, data='%s NameChanges' % len(self._storedClients[client.guid]))
        elif self.action == 'permban':
            client.ban(reason='Too many name changes', keyword='NameChanger', data='%s Namechanges' % len(self._storedClients[client.guid]))
        self.callLog('%s penalized for too many name changes. Penalty: %s' % (client.guid, self.action))
        param = {'name': client.name,
                 'guid': client.guid}
        self.console.say(self.getMessage(self.action, param))

    def callLog(self, data):
            if self.logLocation:
                try:
                    filelog = ('%s' % self.logLocation)
                    f = open(filelog, "a")
                    f.write(data + '\n')
                    f.close()
                except:
                    self.info(data)

    def notifyAdmins(self, player):
        if self.notify:
            for c in self.console.clients.getList():
                if c.maxLevel >= self.notify:
                    c.message('^1ALERT!^7 Player ^3%s ^7has changed their name ^3%s ^7times' % (player.id, len(self._storedClients[player.guid])))



