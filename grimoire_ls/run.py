from .logging import log
from .server import GrimoireServer

if __name__ == "__main__":
    try:
        server = GrimoireServer.from_config()
        server.start_io()
    except Exception as e:
        log(e)
        raise e
