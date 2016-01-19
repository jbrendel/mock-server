#!/usr/bin/env python

# Copyright (c) 2016 Juergen Brendel
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
mock-server.py

A configurable HTTP server for testing code, which needs to interact with HTTP
servers.

In a config file the acceptable requests and responses can be defined.

A single invocation of mock-server can provide multiple HTTP servers, listening
on different ports.

"""

import sys
import json
import time
import threading

from datetime       import datetime
from Queue          import Queue
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer


CONF         = None
LOG_FILENAME = None
SERVERS      = []
LOG_QUEUE    = Queue()
EXIT_MSG     = "@@@EXIT@@@"
LOGFILE      = None
LOGGER       = None


class Conf(object):
    """
    Holds the configuration specified via command line.

    """
    def __init__(self):
        # Currently just some simple reading from the command line.
        if len(sys.argv) != 2:
            usage("Need to provide the server config file name.")

        self.conf_filename = sys.argv[1]
        self.server_conf   = None

        with open(self.conf_filename, "r") as f:
            try:
                self.server_conf = json.load(f)
            except Exception as e:
                exit("Malformed server config file: %s" % str(e))


class Logger(threading.Thread):
    """
    The logger thread is used to ensure that log messages from different
    threads don't end up garbling each other. So, instead of writing to the log
    file directly, the server threads instead send log messages via a queue to
    this thread here, which then sequentially writes them to the log file.

    """
    def stop_it(self):
        """
        Called to signal to this thread that it should stop.

        Sends a message to itself through the queue.

        """
        LOG_QUEUE.put(EXIT_MSG)

    def run(self):
        """
        Continues reading from the queue, until the specified 'exit' message is
        received.

        """
        while True:
            msg = LOG_QUEUE.get()
            if msg == EXIT_MSG:
                return
            else:
                LOGFILE.write(msg + "\n")
                print "@@@: " + msg


class MyHandler(BaseHTTPRequestHandler):

    protocol_version = 'HTTP/1.1'

    def _process_request(self):
        """
        All the processing takes place in the server object. We need to package
        up the information we have right now about the client request and send
        it to the server object and the output the result.

        All requests, independent of method, are handled in the same way here.

        """
        self.protocol_version = "HTTP/1.1"
        code, headers, body = self.server_obj.req_handler(
            self.command, self.path, self.request_version, self.headers,
            self.rfile)
        # The server name is not set as a normal header, it is set by the
        # standard BaseHTTPRequestHandler class via special variables.
        # Therefore, some special handling of the 'server' header (if defined)
        # is needed.
        server_name = "mock-server"
        if headers:
            for hdr_name, hdr_value in headers:
                if hdr_name.lower() == "server":
                    server_name = hdr_value
                    break

        self.server_version = server_name
        self.sys_version = ""
        self.send_response(code)
        # The headers need to be returned as a list of tuples
        if headers:
            for hdr_name, hdr_value in headers:
                if hdr_name.lower() != "server":
                    self.send_header(hdr_name, hdr_value)
        self.end_headers()
        # The body needs to be returned either as a list of strings
        if body:
            for line in body:
                self.wfile.write(line)
        return

    def do_GET(self):
        return self._process_request()

    def do_POST(self):
        return self._process_request()

    def do_PUT(self):
        return self._process_request()

    def do_DELETE(self):
        return self._process_request()

    def do_HEAD(self):
        return self._process_request()

    def log_message(self, format, *args):
        """
        Silence the normal logging.

        """
        pass


class MockServer(threading.Thread):
    """
    A thread for a mock server.

    """
    def __init__(self, config):
        threading.Thread.__init__(self)

        self.name      = config['name']
        self.port      = config['port']
        self.schema    = config.get('schema', "http")
        self.address   = config.get('address', "127.0.0.1")
        self.full_addr = (self.address, self.port)
        self.requests  = config['requests']
        self.requests_in_order = config.get('requests_in_order', False)
        self.server    = None
        self.is_closed = False

    def run(self):
        """
        Run the server thread.

        """
        log("'%s': Server started. Listening on %s." % \
            (self.name, self.full_addr))
        # We create a brand new handler class. Even though it has the same name
        # every time this function is called, these will actually be different
        # class objects. That way, we can embed a reference to this specific
        # server here in the handler class.
        class LocalHandler(MyHandler):
            server_obj = self

        self.server = HTTPServer(self.full_addr, LocalHandler)
        try:
            self.server.serve_forever()
        except Exception as e:
            # Sever threads are closed by brutally closing their socket from
            # the outside. This typically results in a few nasty exceptions. We
            # can ignore those exceptions if we are just closing those sockets
            # on purpose for shutdown. We indicate that with the 'is_closed'
            # flag. If it's set the exception can be ignored.
            if not self.is_closed:
                # Re-raise the exception: This server wasn't closed yet, so we
                # should not have gotten an exception.
                raise e

    def close(self):
        """
        Closing this server.

        We force the end of the server thread by closing the server socket,
        which will cause an exception.

        Setting the is_closed flag will prevent us from reporting that
        exception, since this is expected behaviour.

        """
        log("'%s': Closing socket." % self.name)
        self.is_closed = True
        self.server.socket.close()
        log("'%s': Terminated." % self.name)

    def return_error(self, msg):
        """
        Return a 400 with error message.

        Used if the request is not as expected or specified.

        """
        log("*** Error: %s" % msg)
        return 400, None, [ msg, "\n" ]

    def req_handler(self, method, path, version, headers, req_body_file):
        """
        Check whether this request is acceptable, then produce the specified
        output.

        Return: <status_code, headers, body>

        status_code: integer
        headers:     list of tuples
        body:        list of strings

        """
        req_str = "%s %s" % (method.upper().strip(), path.strip())

        # Check if the client requested to close this server. This is done by
        # sending a "DELETE <server-name>" request to the server in question.
        cmp_str = "DELETE " + self.name
        if req_str == cmp_str:
            self.close()
            return 200, None, None

        # Read the request body. This requires the presence of a content-length
        # header.
        cl = headers.getheader('content-length')
        if cl is None:
            l = 0
        else:
            l = int(cl)
        rbody = req_body_file.read(l)

        # Find the request in our request list of this server.
        # Needs to be handled a little different, depending on whether
        # we ask for strict order of requests or not.
        if self.requests_in_order:
            if self.requests[0]['request']['req'] != req_str:
                return self.return_error(
                    "'%s': [%s] Not the expected next request!" % \
                        (self.name, req_str))
            else:
                req_index = 0
        else:
            for i, r in enumerate(self.requests):
                if r['request']['req'] == req_str:
                    req_index = i
                    break
            else:
                return self.return_error(
                    "'%s': [%s] Not an acceptable request!" % \
                        (self.name, req_str))

        # We found the request in our list. Now let's process it.
        resp = self.requests[req_index]['response']
        # Translate headers into tuple list.
        hdrs = []
        if resp.get('headers'):
            for h in resp['headers']:
                hdr_name, hdr_value = h.split(":", 1)
                hdr_name  = hdr_name.strip()
                hdr_value = hdr_value.strip()
                hdrs.append((hdr_name, hdr_value))
        if resp.get('body'):
            body = '\n'.join([ l for l in resp['body'] ])
        else:
            body = ""
        log("'%s': [%s] - Resp: %s (%d)" % \
            (self.name, req_str, resp['status'], len(body)))

        if self.requests_in_order:
            # When requests are supposed to be processed in order, we take the
            # handled ones out of the list. Once the list is empty the server
            # process can exit.
            self.requests.pop(req_index)
            if not self.requests:
                # We processed the last request!
                log("'%s': All requests processed." % self.name)
                self.close()
        return resp['status'], hdrs, [ body ]


def log(msg):
    """
    This log function formats the message and sends it to the logging thread.

    """
    msg = "%s %s" % (str(datetime.now()), msg)
    LOG_QUEUE.put(msg)


def exit(msg, code=1):
    """
    Standardized exit function.

    """
    log(msg)
    sys.exit(code)


def usage(msg=None):
    """
    Print usage instructions and optional error message.

    """
    print "Usage: ./mock-server.py <config-file>"
    exit("Please provide a server config file name.")


def _create_servers(servers):
    """
    Create individual server processes.

    Takes the list of server definitions from the server config file as input.

    """
    for server in servers:
        SERVERS.append(MockServer(server))

    for ms in SERVERS:
        ms.start()


def create_logger():
    """
    Create and start the logging thread.

    """
    global LOGGER
    global LOGFILE

    LOG_FILENAME = CONF.server_conf['logfile']
    try:
        LOGFILE = open(LOG_FILENAME, "a")
    except Exception as e:
        exit("Cannot open logfile '%s': %s" % (LOG_FILENAME, str(e)))

    LOGGER = Logger()
    LOGGER.start()
    log("*** Starting log for server mock-server run...")


def create_servers_from_config():
    """
    Read the specified config file and create servers.

    """
    if "servers" not in CONF.server_conf:
        exit("Missing 'servers' list in server config file.")

    _create_servers(CONF.server_conf['servers'])

def wait_for_servers_to_finish():
    """
    Wait for keyboard interrupt or all servers being finished.

    """
    try:
        # Wait for all servers to be marked as closed
        while any([s.is_closed == False for s in SERVERS]):
            time.sleep(1)
        log("All servers have finished...")
    except KeyboardInterrupt:
        log("Shutting down...")
        # The server processes are tough to kill, since they may be waiting on
        # a socket for activity. We solve the problem by reaching into those
        # threads and closing the socket for them, immediately causing them to
        # exit with an exception...
        for ms in SERVERS:
            if not ms.is_closed:
                ms.close()


if __name__ == "__main__":
    CONF = Conf()
    create_logger()
    create_servers_from_config()
    wait_for_servers_to_finish()
    log("Done!")
    # We also need to tell the logger thread to exit now
    LOGGER.stop_it()

