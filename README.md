# Mock-server

A flexible, easily configured server, suitable to use as a stand in for any
HTTP server during test runs.

## Introduction

Writing tests for code which requires access to external servers is not always
straight forward. To keep the tests as self-contained as possible, the usual
strategy is to mock out the access calls to the external server. However, if
this access is hidden several layers deep down in some library (which otherwise
you would like to use in your test code and therefore cannot just mock out),
the test can become quite complex.

It is sometimes esier to actually run the external server, but pre-load it with
some test data. However, this in itself can also be a challenge, depending on
the server you need to run.

To make this as easy as possible - at least for HTTP based servers - I wrote
mock-server.py. This little utility can be a stand-in for an actual HTTP server
during tests. It is easily configured via a single JSON file, can spin up
multiple server threads (listening on different ports) and can reply with
specified status, headers and body, based on a client request.

## How to use

In a test case, start mock-server.py as an external process with the JSON
server configuration file as the single parameter.

mock-server starts up, reads the config file, spins up server threads on the
specified ports and starts to listen.

A server-thread will automatically terminate after the last specified request
has been processed. However, if 'requests_in_order' has been set to False (see
below) then it will not automatically terminate. In that case, you can send a
"DELETE <server-name>" request to the server-thread to kill it.

If your test case sends an unexpected request to mock-server, a "400 Bad
Request" will be returned.

Usage:

   ./mock-server.py server-config.json

## The server-config file

The behaviour of the mocked servers is defined in the server-config JSON file.
Here is an example:

```json
{
    "logfile" : "/var/tmp/mock-server.log",
    "servers" : [
        {
            "name"              : "Foobar",
            "address"           : "0.0.0.0",
            "port"              : 12345,
            "schema"            : "http",
            "requests_in_order" : true,
            "requests" : [
                {
                    "request" : {
                        "req" : "GET /foo/bar?blah=123"
                    },
                    "response" : {
                        "status" : 200,
                        "headers" : [
                            "Date: Sat, 28 Nov 2099 00:45:59 GMT",
                            "Server: Mock-server",
                            "Connection: close",
                            "Etag: \"pub555111222;\"",
                            "Cache-Control: max-age=3600, public",
                            "Content-Type: text/html; charset=UTF-8",
                            "Vary: Accept-Encoding, Cookie, User-Agent"
                        ],
                        "body" : [
                            "Hello!"
                        ]
                    }
                },
                {
                    "request" : {
                        "req" : "GET /foo/bar?blah=456"
                    },
                    "response" : {
                        "status" : 200,
                        "body" : [
                            "Hello there, a second time!"
                        ]
                    }
                }
            ]
        },
        {
            "name"              : "Blahblah",
            "port"              : 54321,
            "schema"            : "http",
            "requests_in_order" : true,
            "requests" : [
                {
                    "request" : {
                        "req" : "GET /bla/baz"
                    },
                    "response" : {
                        "status" : 200,
                        "headers" : [
                            "Server: Blahblah"
                        ],
                        "body" : [
                            "Hallo!"
                        ]
                    }
                },
                {
                    "request" : {
                        "req" : "GET /bla/baz"
                    },
                    "response" : {
                        "status" : 200,
                        "headers" : [
                            "Server: Blahblah"
                        ],
                        "body" : [
                            "Zweite Antwort!"
                        ]
                    }
                },
                {
                    "request" : {
                        "req" : "POST /bla/baz"
                    },
                    "response" : {
                        "status" : 201,
                        "headers" : [
                            "Server: Blahblah"
                        ]
                    }
                }
            ]
        }
    ]
}
```

After specifying the log file location, this file defines two servers
("Foobar", listening on port 12345 and "Blahblah", listening on port 54321).
For each server the 'schema' is defined. It has to be "http" for now.
Furthermore, for one of the servers we have defined "requests_in_order", which
defaults to False. If it is set then the subsequently defined requests are
expected to arrive in exactly the specified order, with each request only being
able to appear once. Otherwise, any of the defined requests may appear in any
order and multiple times.

For each server a list of requests is defined. You can see the request method
and path under 'request -> req'. Under 'response' we define the status code,
the headers (if any) and the request body (if any), which should be returned.

Please note: All client requests should be of type HTTP/1.1, so a sent request
line should look like: GET /foo/bar/ HTTP/1.1

## TODO

* Define request headers and body for checking.
* Option to specify files or executables for headers and request bodies.
* Support SSL.


