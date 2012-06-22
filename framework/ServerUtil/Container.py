#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       Container.py
#       
#       This file is part of the RoboEarth Cloud Engine framework.
#       
#       This file was originally created for RoboEearth
#       http://www.roboearth.org/
#       
#       The research leading to these results has received funding from
#       the European Union Seventh Framework Programme FP7/2007-2013 under
#       grant agreement no248942 RoboEarth.
#       
#       Copyright 2012 RoboEarth
#       
#       Licensed under the Apache License, Version 2.0 (the "License");
#       you may not use this file except in compliance with the License.
#       You may obtain a copy of the License at
#       
#       http://www.apache.org/licenses/LICENSE-2.0
#       
#       Unless required by applicable law or agreed to in writing, software
#       distributed under the License is distributed on an "AS IS" BASIS,
#       WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#       See the License for the specific language governing permissions and
#       limitations under the License.
#       
#       \author/s: Dominique Hunziker 
#       
#       

# ROS specific imports
import rosgraph.names

# twisted specific imports
from twisted.python import log

# Custom imports
from Exceptions import InternalError, InvalidRequest
from Comm.Message import MsgDef
from Comm.Message import MsgTypes
from Comm.Message.Base import Message

from Interface import Interface

from ROSComponents import ComponentDefinition
from ROSComponents.Node import Node
from ROSComponents.Parameter import IntParam, StrParam, FloatParam, BoolParam, FileParam

class Container(object):
    """ Class which represents a container. It is associated with a robot.
        A container can have multiple interfaces.
    """
    def __init__(self, commMngr, serverMngr, user, tag, commID):
        """ Initialize the Container.
            
            @param commMngr:    CommManager which should be used to communicate.
            @type  commMngr:    CommManager
            
            @param serverMngr:   ServerManager which is used in this node.
            @type  serverMngr:   ServerManager
            
            @param user:        User instance to which this container belongs.
            @type  user:        User
            
            @param tag:         Tag which is used by the robot to identify this container.
            @type  tag:         str
            
            @param commID:      CommID which is used for the environment node inside the
                                container and which is used to identify the container.
            @type  commID:      str
        """
        self._commManager = commMngr
        self._serverManager = serverMngr
        self._user = user
        self._tag = tag
        self._commID = commID
        
        self._interfaces = {}
        self._rosAddrs = set()
        
        self._running = False
        self._connected = False
    
    @property
    def tag(self):
        """ Tag of the container used by the robot. """
        return self._tag
    
    @property
    def commID(self):
        """ Communication ID of the container. """
        return self._commID
    
    def setConnectedFlag(self, flag):
        """ Set the 'connected' flag for the container.
            
            @param flag:    Flag which should be set. True for connected and False for
                            not connected.
            @type  flag:    bool
            
            @raise:         InvalidRequest if the container is already registered as connected.
        """
        if not self._running:
            raise InvalidRequest('Tried to manipulate "connected" flag of container which is not running.')
        
        if flag:
            if self._connected:
                raise InvalidRequest('Tried to set container to connected which already is registered as connected.')
            
            self._connected = True
            self._user.sendContainerUpdate(self._tag, True)
        else:
            self._connected = False
            self._user.sendContainerUpdate(self._tag, False)
    
    def start(self):
        """ Send a Request to start the container.
        """
        if self._running:
            raise InternalError('Container can be started only once.')
        
        msg = Message()
        msg.msgType = MsgTypes.CONTAINER_START
        msg.dest = MsgDef.PREFIX_PRIV_ADDR + self._commManager.commID[MsgDef.PREFIX_LENGTH_ADDR:]
        msg.content = { 'commID' : self._commID }
        
        log.msg('Start container "{0}".'.format(self._commID))
        self._commManager.sendMessage(msg)
        self._running = True
    
    def stop(self):
        """ Send a Request to stop the container.
        """
        if not self._running:
            raise InternalError('Container has to be started before it can be stopped.')
        
        msg = Message()
        msg.msgType = MsgTypes.CONTAINER_STOP
        msg.dest = MsgDef.PREFIX_PRIV_ADDR + self._commManager.commID[MsgDef.PREFIX_LENGTH_ADDR:]
        msg.content = { 'commID' : self._commID }
        
        log.msg('Stop container "{0}".'.format(self._commID))
        self._commManager.sendMessage(msg)
        self._running = False
    
    def addNode(self, tag, pkg, exe, namespace):
        """ Add a node to the ROS environment in the container.
            
            @param tag:     Tag which is used to identify the ROS node which
                            should added.
            @type  tag:     str

            @param pkg:     Package name where the node can be found.
            @type  pkg:     str

            @param exe:     Name of executable which should be launched.
            @type  exe:     str
            
            @param namespace:   Namespace in which the node should use be launched.
            @type  namespace:   str
            
            @raise:     InvalidRequest if the name is not a valid ROS name.
        """
        # First make sure, that the received strings are str objects and not unicode
        if isinstance(pkg, unicode):
            try:
                pkg = str(pkg)
            except UnicodeEncodeError:
                raise InternalError('The package "{0}" is not valid.'.format(pkg))
        
        if isinstance(exe, unicode):
            try:
                exe = str(exe)
            except UnicodeEncodeError:
                raise InternalError('The executable "{0}" is not valid.'.format(exe))
        
        if isinstance(namespace, unicode):
            try:
                namespace = str(namespace)
            except UnicodeEncodeError:
                raise InternalError('The namespace "{0}" is not valid.'.format(namespace))
        
        if not rosgraph.names.is_legal_name(namespace):
            raise InvalidRequest('The namespace "{0}" is not valid.'.format(namespace))
        
        log.msg('Start node "{0}/{1}" (tag: "{2}") in container "{3}".'.format(pkg, exe, tag, self._commID))
        msg = Message()
        msg.msgType = MsgTypes.ROS_ADD
        msg.content = Node(tag, pkg, exe, namespace)
        self.send(msg)
    
    def removeNode(self, tag):
        """ Remove a node from the ROS environment in the container.
            
            @param tag:     Tag which is used to identify the ROS node which should
                            be removed.
            @type  tag:     str
        """
        log.msg('Remove node (tag: "{0}") from container "{1}".'.format(tag, self._commID))
        msg = Message()
        msg.msgType = MsgTypes.ROS_REMOVE
        msg.content = { 'type' : ComponentDefinition.RM_NODE,
                        'tag'  : tag }
        self.send(msg)
    
    def addParameter(self, name, value, paramType):
        """ Add a parameter to the parameter server in the container.
            
            @param name:    Name of the parameter which should be added.
            @type  name:    str
            
            @param value:   Value of the parameter which should be added.
            @type  value:   Depends on @param paramType
            
            @param paramType:   Type of the parameter to add. Valid options are:
                                    int, str, float, bool, file
            @type  paramType:   str
            
            @raise:     InvalidRequest if the name is not a valid ROS name.
        """
        if not rosgraph.names.is_legal_name(name):
            raise InvalidRequest('The name "{0}" is not valid.'.format(name))
        
        if paramType == 'int':
            content = IntParam(name, value)
        elif paramType == 'str':
            content = StrParam(name, value)
        elif paramType == 'float':
            content = FloatParam(name, value)
        elif paramType == 'bool':
            content = BoolParam(name, value)
        elif paramType == 'file':
            content = FileParam(name, value)
        
        log.msg('Add parameter "{0}" to container "{1}".'.format(name, self._commID))
        msg = Message()
        msg.msgType = MsgTypes.ROS_ADD
        msg.content = content
        self.send(msg)
    
    def removeParameter(self, name):
        """ Remove a parameter from the parameter server in the container.
            
            @param name:    Name of the parameter which should be removed.
            @type  name:    str
        """
        log.msg('Remove parameter "{0}" from container "{1}".'.format(name, self._commID))
        msg = Message()
        msg.msgType = MsgTypes.ROS_REMOVE
        msg.content = { 'type' : ComponentDefinition.RM_PARAMETER,
                        'tag'  : name }
        self.send(msg)
    
    def reserveAddr(self, addr):
        """ Callback method for Interface to reserve the ROS address.
            
            @param addr:    ROS address which should be reserved.
            @type  adrr:    str
            
            @raise:     ValueError if the address is already in use.
        """
        if addr in self._rosAddrs:
            raise ValueError('Address already is in use.')
        
        self._rosAddrs.add(addr)
    
    def freeAddr(self, addr):
        """ Callback method for Interface to free the ROS address.
            
            @param addr:    ROS address which should be freed.
            @type  addr:    str
        """
        if addr not in self._rosAddrs:
            log.msg('Tried to free an address which was not reserved.')
        else:
            self._rosAddrs.remove(addr)
    
    def addInterface(self, interfaceTag, rosAddr, msgType, interfaceType):
        """ Add an interface to the container.
            
            @param interfaceTag:    Tag which is used to identify the interface to add.
            @type  interfaceTag:    str
            
            @param rosAddr:     ROS name/address which the interface should use.
            @type  rosAddr:     str
            
            @param msgType:     Message type/Service type consisting of the package and the name
                                of the message/service, i.e. 'std_msgs/Int32'.
            @type  msgType:     str
            
            @param interfaceType:   Type of the interface. Valid types are 'service', 'publisher',
                                    and 'subscriber'.
            @type  interfaceType:   str
        """
        if interfaceTag in self._interfaces:
            if not self._interfaces[interfaceTag].validate(interfaceTag, rosAddr, msgType, interfaceType):
                raise InvalidRequest('Another interface with the same tag already exists.')
            
            log.msg('Tried to add the same interface (tag: "{0}") twice to container "{1}".'.format(
                interfaceTag, 
                self._commID
            ))
        else:
            log.msg('Add interface "{0}" (type: "{1}"; tag: "{2}") to container "{3}".'.format(
                rosAddr,
                interfaceType,
                interfaceTag,
                self._commID
            ))
            self._interfaces[interfaceTag] = Interface( self._serverManager,
                                                        self,
                                                        interfaceTag,
                                                        rosAddr,
                                                        msgType,
                                                        interfaceType )
    
    def removeInterface(self, interfaceTag):
        """ Remove an interface to the container.
            
            @param interfaceTag:    Tag which is used to identify the interface to remove.
            @type  interfaceTag:    str
        """
        if interfaceTag not in self._interfaces:
            raise InvalidRequest('Can not remove the interface. Tag does not exist.')
        
        log.msg('Remove interface (tag: "{0}") from container "{1}".'.format(interfaceTag, self._commID))
        del self._interfaces[interfaceTag]
    
    def activateInterface(self, interfaceTag, target, commID):
        """ Activate an interface for a user.
            
            @param interfaceTag:    Tag which is used to identify the interface which
                                    should be activated for a user.
            @type  interfaceTag:    str
            
            @param target:      Tag which is used to identify the user/interface for
                                which the interface should be activated.
            @type  target:      str
            
            @param commID:      Communication ID where the target is coming from.
            @type  commID:      str
        """
        if not self._connected:
            raise InternalError('Container has to be connected before an interface can be activated.')
        
        try:
            self._interfaces[interfaceTag].registerUser(target, commID)
            log.msg('Activate interface (tag: "{0}") for user "({1}, {2})" in container "{3}".'.format(
                interfaceTag,
                commID,
                target,
                self._commID
            ))
        except KeyError:
            raise InternalError('Can not activate an interface which does not exist.')
    
    def deactivateInterface(self, interfaceTag, target, commID):
        """ Deactivate an interface for a user.
            
            @param interfaceTag:    Tag which is used to identify the interface which
                                    should be deactivated for a user.
            @type  interfaceTag:    str
            
            @param target:      Tag which is used to identify the user/interface for
                                which the interface should be deactivated.
            @type  target:      str
            
            @param commID:      Communication ID where the target is coming from.
            @type  commID:      str
        """
        if not self._connected:
            raise InternalError('Container has to be connected before an interface can be deactivated.')
        
        try:
            self._interfaces[interfaceTag].unregisterUser(target, commID)
            log.msg('Deactivate interface (tag: "{0}") for user "({1}, {2})" in container "{3}".'.format(
                interfaceTag,
                commID,
                target,
                self._commID
            ))
        except KeyError:
            raise InternalError('Can not deactivate an interface which does not exist.')
    
    def send(self, msg):
        """ Send a message to the container. (Called by Interface)
            
            @param msg:     Message which should be sent to the container. The message
                            has to be a Message instance which contains all data
                            except the destination which are necessary to send the message.
            @type  msg:     Message
        """
        if not isinstance(msg, Message):
            raise InternalError('Can not send an object which is not of type "Message".')
        
        msg.dest = self._commID
        self._commManager.sendMessage(msg)
    
    def receive(self, msg):
        """ Process a received ROS message. (Called by Manager)
            
            @param msg:     Received message.
            @type  msg:     Message
        """
        msg = msg.content
        
        try:
            self._commManager.reactor.callInThread(
                self._interfaces[msg['tag']].receive,
                msg
            )
        except KeyError:
            raise InternalError('Can not process received message. Interface does not exist.')
    
    def sendToInterface(self, robotID, msg):
        """ Send a message to the interface matching the given tag. (Called by User)
            
            @param robotID:     ID which is used to identify the sender of the message.
            @type  robotID:     str
            
            @param msg:     Corresponds to the dictionary of the field 'data' of the received
                            message. (Necessary keys: type, msgID, interfaceTag, msg)
            @type  msg:     { str : ... }
        """
        try:
            self._commManager.reactor.callInThread(
                self._interfaces[msg['interfaceTag']].send,
                msg,
                robotID
            )
        except KeyError:
            raise InternalError('Can not send message. Interface does not exist.')
    
    def receivedFromInterface(self, robotID, msg):
        """ Received a message from an interface and should now be processed.
            (Called by Interface)
            
            @param robotID:     ID which is used to identify the receiving robot.
            @type  robotID:     str
            
            @param msg:     Message which was received in form of a dictionary matching
                            the structure of the ROS message.
            @type  msg:     { str : ... }
        """
        self._user.sendROSMsgToRobot(self._tag, robotID, msg)

