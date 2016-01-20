# Mock-server

A flexible, easily configured server, suitable to use as a stand in for any
HTTP server - or multiple servers - during test runs.

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
mock-server.py. This little utility can be a stand-in for a actual HTTP
server(s) during tests. It is easily configured via a single JSON file, or at
runtime via REST requests. It can spin up multiple server threads (listening on
different ports) and can reply with specified status, headers and body, based
on a client request.

Ideal for service testing in a micro-services architecture, for example.

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

An initial list of expected request/response pairs is specified via the JSON
file. However, it is possible to instead define this list (or modify the list)
via REST requests at run time. This enables more complex test cases where the
test suite programmatically determines test requests.

Usage:

```
   ./mock-server.py server-config.json
```

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
                            "Server: Blahblah",
                            "X-some-header-I-made-up: Hi!"
                        ]
                    }
                }
            ]
        },
        {
            "name"              : "No-requests-server",
            "port"              : 5555,
            "schema"            : "http",
            "req_config_url"    : "/reqs/and/resps/",
            "requests" : [
            ]
        }

    ]
}
```

After specifying the log file location, this file defines three servers
("Foobar", listening on port 12345, "Blahblah", listening on port 54321 and
"No-requests-server", listening on port 5555).

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

## Programmatic addition of request/response pairs

Note that for the "No-requests-server" we have not defined any requests at all.
It is assumed that test cases will add request/response pairs programmatically
at run time. Please note also that it is possible to add or modify already
existing requests, whether they came from the initial JSON file or whether they
were specified later on at run time via the API.

For the "No-requests-server" we have defined the "req_config_url" property.
The server will maintain a list of the defined req/resp pairs at that
collection URL.

You can see the list of current req/resp pairs via a GET request to that URL.
You can update a single request with a PUT to that URL (with the appended list
index of the entry you wish to change). So, in this example "/reqs/and/resps/0"
is the URL of the first req/resp pair. You can also create a brand new req/resp
entry via a POST to the URL. Finally, you can delete an existing req/resp pair
with a DELETE. Note that after a DELETE the index of any subsequent entries is
changed.

To create or update a new request response pair, simply POST or PUT a JSON
definition to the specified URL. The JSON definition is exactly what you would
write into the JSON config file. So, for example, you could POST:

```
POST /reqs/and/resps/ HTTP/1.1
Content-length: 159

{
    "request" : {
        "req" : "GET /bla/baz"
    },
    "response" : {
        "status" : 200,
        "body" : [
            "Hallo!"
        ]
    }
}
```

As response you would receive:

```
HTTP/1.1 201 Created
Server: mock-server 
Date: Wed, 20 Jan 2016 02:51:38 GMT
location: /reqs/and/resps/0
```

## TODO

* Define request headers and body for checking.
* Allow wildcards in request matching.
* Option to specify files or executables for headers and request bodies.
* Option to specify imported Python code for request handling.
* Support SSL.


