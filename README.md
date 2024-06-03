You can find the class definitions for chat objects in `/chat_model/chat_app/chat.py` for an incomplete IRC chat parser.
The parser uses regular expressions to isolate usernames, validate commands, and parse chat logs into lines with separate timestamps.

To test the server:

```$python3 /server/server.py```

To test the IRC parser:

```$python3 /chat_parser/chat.py```

The server includes the Redis queue which can be run separately as another process.
To use Redis Queue you must start a worker in a background tab, and the worker runs the queued actions:

```$rq worker --with-scheduler```

It's also possible to embed the Redis queue server into a Flask backend if it cannot run separately.

Right now the folder /server/templates/ has empty .html files. That should get replaced with a responsive frontend.